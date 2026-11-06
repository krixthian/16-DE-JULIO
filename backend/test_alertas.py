"""Modelo T1 real, generación de alertas e intervenciones sobre SQLite temporal con datos ficticios."""
import asyncio
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI
from sqlalchemy import select, func

import models as m
from api.alertas import router
from api.auth import get_current_user
from database import get_db
from predictivo import real_t1
from predictivo.source import register_model
import test_predictivo_api as base


def excel_fixture(path, rows=80, seed=3):
    """Dataset ficticio con el formato de DATOS_REAL; los positivos tienen notas más bajas."""
    rng = np.random.default_rng(seed)
    data = []
    for i in range(rows):
        positive = i % 8 == 0
        notes = rng.integers(40, 70 if positive else 96, size=9)
        row = dict(codigo_anonimo=f'FIC-{i // 2:03}', gestion=2023 + i % 2, grado=1 + i % 6, paralelo='Z', genero='MF'[i % 2],
            edad_31marzo=6 + i % 6, **{f'{a}_T1': int(n) for a, n in zip(real_t1.AREAS, notes)},
            promedio_T1=int(notes.mean()), nota_minima_T1=int(notes.min()), n_areas_bajo_51_T1=int((notes < 51).sum()),
            faltas_T1=int(rng.integers(3, 9) if positive else rng.integers(0, 3)), atrasos_T1=int(rng.integers(0, 3)),
            licencias_T1=int(rng.integers(0, 3)), dias_asistidos_T1=40, dias_lectivos_T1=50,
            POST_promedio_T2=0 if positive else 80, y_abandono_intra_anual=int(positive),
            y_no_continua_siguiente=float(i % 7 == 0) if i % 2 else np.nan)
        data.append(row)
    pd.DataFrame(data).to_excel(path, sheet_name='DATOS_REAL', index=False)


class RealT1Tests(unittest.TestCase):
    def test_post_columns_are_never_features(self):
        self.assertFalse([n for n in real_t1.FEATURE_NAMES if n.startswith('POST_') or n.startswith('y_')])
        with tempfile.TemporaryDirectory() as directory:
            excel_fixture(Path(directory) / 'd.xlsx')
            frame = real_t1.load(Path(directory) / 'd.xlsx')
            self.assertNotIn('POST_promedio_T2', frame.columns)
            self.assertTrue(frame['tasa_asistencia_T1'].between(0, 1).all())

    def test_folds_never_share_students(self):
        from sklearn.model_selection import StratifiedGroupKFold
        with tempfile.TemporaryDirectory() as directory:
            excel_fixture(Path(directory) / 'd.xlsx')
            frame = real_t1.load(Path(directory) / 'd.xlsx')
        y, groups = frame['y_abandono_intra_anual'], frame['codigo_anonimo']
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=1).split(frame, y, groups):
            self.assertFalse(set(groups.iloc[tr]) & set(groups.iloc[te]))

    def test_rule_threshold_uses_training_scores(self):
        self.assertEqual(real_t1.rule_threshold(np.array([1, 2, 3, 9]), np.array([0, 0, 0, 1])), 9)


class AlertasApiTests(unittest.TestCase):
    setUp = base.PredictivoApiTests.setUp
    tearDown = base.PredictivoApiTests.tearDown

    def prepare(self, directory):
        excel = Path(directory) / 'd.xlsx'
        excel_fixture(excel)
        frame = real_t1.load(excel)
        self.db.add(m.Gestion(id=2, anio=2024, fecha_inicio=date(2024, 2, 1), fecha_fin=date(2024, 11, 30)))
        enrollment = 100
        for (year, grade), _ in frame.groupby(['gestion', 'grado']):
            self.db.add(m.Curso(id=int(year * 10 + grade), gestion_id=int(year - 2022), grado=int(grade), paralelo='Z'))
        for code in frame['codigo_anonimo'].unique():
            self.db.add(m.Estudiante(codigo_anonimo=code, nombre='ANONIMO', apellido=code))
        self.db.flush()
        for row in frame.itertuples():
            student = self.db.scalar(select(m.Estudiante.id).where(m.Estudiante.codigo_anonimo == row.codigo_anonimo))
            enrollment += 1
            self.db.add(m.Matricula(id=enrollment, estudiante_id=student, curso_id=int(row.gestion * 10 + row.grado),
                fecha_ingreso=date(int(row.gestion), 2, 1), origen='REAL', registrado_por=1, creado_en=datetime(int(row.gestion), 2, 1)))
        self.db.commit()
        report = real_t1.train(excel, Path(directory) / 'modelo', repetitions=2)
        model_id = register_model(self.db, report, Path(directory) / 'modelo' / 'modelo_xgboost.json', .5, .8)
        return excel, model_id, len(frame)

    def test_generation_is_idempotent_and_workflow_respects_states(self):
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            counts = real_t1.generate(self.db, excel, model_id)
            self.db.commit()
            self.assertEqual((counts['cortes'], counts['predicciones']), (rows, rows))
            self.assertGreater(counts['alertas'], 0)
            again = real_t1.generate(self.db, excel, model_id)
            self.assertEqual(again, {'cortes': 0, 'predicciones': 0, 'alertas': 0})
            self.assertEqual(self.db.scalar(select(func.count()).select_from(m.Alerta)), counts['alertas'])
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                alerts = (await client.get('/alertas')).json()
                self.assertEqual(len(alerts), counts['alertas'])
                self.assertNotIn('nombre', alerts[0])
                self.assertIn(alerts[0]['nivel'], ('MEDIO', 'ALTO'))
                first = alerts[0]['id']
                self.assertEqual((await client.patch(f'/alertas/{first}', json={'estado': 'CERRADA'})).status_code, 422)
                created = await client.post(f'/alertas/{first}/intervenciones', json={'recomendacion': 'Citar a la familia'})
                self.assertEqual(created.status_code, 201, created.text)
                self.assertEqual(self.db.get(m.Alerta, first).estado, 'EN_SEGUIMIENTO')
                item = created.json()['id']
                self.assertEqual((await client.patch(f'/intervenciones/{item}', json={'estado': 'REALIZADA'})).status_code, 422)
                done = await client.patch(f'/intervenciones/{item}', json={'estado': 'REALIZADA', 'accion_realizada': 'Reunión'})
                self.assertEqual(done.json()['aprobada_por'], 1)
                closed = await client.patch(f'/alertas/{first}', json={'estado': 'CERRADA', 'motivo_cierre': 'Asiste con normalidad'})
                self.assertIsNotNone(closed.json()['cerrada_en'])
                self.assertEqual((await client.post(f'/alertas/{first}/intervenciones', json={'recomendacion': 'Otra'})).status_code, 409)
                reopened = await client.patch(f'/alertas/{first}', json={'estado': 'EN_REVISION'})
                self.assertIsNone(reopened.json()['cerrada_en'])
                summary = (await client.get('/alertas/resumen')).json()
                self.assertEqual(sum(summary['predicciones'].values()), rows)
                self.user.rol = 'Docente'
                self.assertEqual((await client.get('/alertas')).status_code, 403)
        asyncio.run(run())

    def test_filters_responsible_priority_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            real_t1.generate(self.db, excel, model_id)
            self.db.add_all([m.Usuario(id=2, nombre='Orientación', apellido='Prueba', email='o@example.invalid', rol='Orientador', activo=True),
                m.Usuario(id=3, nombre='Docente', apellido='Prueba', email='d@example.invalid', rol='Docente', activo=True)])
            self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                alerts = (await client.get('/alertas')).json()
                first = alerts[0]
                self.assertEqual(first['prioridad']['puesto'], 1)
                self.assertIn('ranking de prioridad', first['prioridad']['nota'])
                for nivel in ('MEDIO', 'ALTO'):
                    filtered = (await client.get('/alertas', params={'nivel': nivel})).json()
                    self.assertTrue(all(a['nivel'] == nivel for a in filtered))
                by_course = (await client.get('/alertas', params={'curso_id': first['curso_id'], 'gestion': first['gestion']})).json()
                self.assertTrue(by_course and all(a['curso_id'] == first['curso_id'] for a in by_course))
                self.assertEqual({u['id'] for u in (await client.get('/alertas/responsables')).json()}, {1, 2})
                self.assertEqual((await client.patch(f"/alertas/{first['id']}", json={'responsable_id': 3})).status_code, 422)
                self.assertEqual((await client.patch(f"/alertas/{first['id']}", json={})).status_code, 422)
                moved = await client.patch(f"/alertas/{first['id']}", json={'responsable_id': 2, 'estado': 'EN_REVISION'})
                self.assertEqual(moved.json()['responsable']['id'], 2)
                self.assertEqual(len((await client.get('/alertas', params={'responsable_id': 2})).json()), 1)
                await client.patch(f"/alertas/{first['id']}", json={'estado': 'CERRADA', 'motivo_cierre': 'Seguimiento concluido'})
                history = (await client.get(f"/alertas/{first['id']}/historial")).json()
                self.assertEqual([h['operacion'] for h in history], ['CORRECCION', 'CORRECCION'])
                self.assertEqual(history[0]['antes']['responsable_id'], 1)
                self.assertEqual(history[0]['despues'], {'estado': 'EN_REVISION', 'responsable_id': 2, 'cerrada_en': None, 'motivo_cierre': None})
                self.assertEqual(history[1]['despues']['estado'], 'CERRADA')
                unchanged = self.db.scalar(select(func.count()).select_from(m.AuditoriaCambio))
                await client.patch(f"/alertas/{first['id']}", json={'estado': 'CERRADA', 'motivo_cierre': 'Seguimiento concluido'})
                self.assertEqual(self.db.scalar(select(func.count()).select_from(m.AuditoriaCambio)), unchanged)
        asyncio.run(run())

    def test_recommendations_are_adopted_once_and_execution_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            real_t1.generate(self.db, excel, model_id)
            self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                alert = (await client.get('/alertas')).json()[0]
                rec = (await client.get(f"/alertas/{alert['id']}/recomendaciones")).json()
                self.assertIn('pendiente de validación', rec['validacion'])
                self.assertTrue(rec['reglas'])
                regla = rec['reglas'][0]
                self.assertIsNone(regla['intervencion_id'])
                created = await client.post(f"/alertas/{alert['id']}/recomendaciones/{regla['codigo']}")
                self.assertEqual(created.status_code, 201, created.text)
                self.assertEqual(created.json()['regla_version'], regla['regla_version'])
                self.assertIn(regla['dato'], created.json()['recomendacion'])
                self.assertEqual((await client.post(f"/alertas/{alert['id']}/recomendaciones/{regla['codigo']}")).status_code, 409)
                inactive = {'RP01', 'RP02', 'RP03', 'RP04', 'RP05'} - {r['codigo'] for r in rec['reglas']}
                if inactive:
                    self.assertEqual((await client.post(f"/alertas/{alert['id']}/recomendaciones/{inactive.pop()}")).status_code, 422)
                again = (await client.get(f"/alertas/{alert['id']}/recomendaciones")).json()['reglas'][0]
                self.assertEqual(again['intervencion_id'], created.json()['id'])
                item = created.json()['id']
                future = {'estado': 'REALIZADA', 'accion_realizada': 'Reunión', 'fecha_ejecucion': '2999-01-01'}
                self.assertEqual((await client.patch(f'/intervenciones/{item}', json=future)).status_code, 422)
                done = await client.patch(f'/intervenciones/{item}', json={'estado': 'REALIZADA', 'tipo_accion': 'CITACION',
                    'accion_realizada': 'Reunión con el apoderado', 'fecha_ejecucion': '2025-05-12', 'resultado': 'Acuerdo de asistencia'})
                self.assertEqual(done.status_code, 200, done.text)
                body = done.json()
                self.assertEqual(body['accion_realizada'], '[Citación al apoderado] Reunión con el apoderado')
                self.assertEqual(str(body['realizada_en'])[:10], '2025-05-12')
                self.assertEqual(body['resultado'], 'Acuerdo de asistencia')
        asyncio.run(run())


    def test_dashboard_aggregates_match_database(self):
        from api.dashboard import router as dashboard_router
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            counts = real_t1.generate(self.db, excel, model_id)
            self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.include_router(dashboard_router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                first = (await client.get('/alertas')).json()[0]
                item = (await client.post(f"/alertas/{first['id']}/intervenciones", json={'recomendacion': 'Citar'})).json()['id']
                await client.patch(f'/intervenciones/{item}', json={'estado': 'REALIZADA', 'accion_realizada': 'Reunión'})
                await client.post(f"/alertas/{first['id']}/intervenciones", json={'recomendacion': 'Tutoría'})
                panel = (await client.get('/dashboard')).json()
                self.assertEqual(panel['resumen']['predicciones'], rows)
                self.assertEqual(panel['resumen']['alertas'], counts['alertas'])
                self.assertEqual(panel['resumen']['alto'] + panel['resumen']['medio'], counts['alertas'])
                self.assertEqual(sum(c['ALTO'] + c['MEDIO'] for c in panel['alertas_por_curso']), counts['alertas'])
                self.assertEqual(sum(g['n'] for g in panel['promedio_por_grado']), rows)
                self.assertTrue(all(g['n'] == sum(g[b['codigo']] for b in panel['bandas']) for g in panel['promedio_por_grado']))
                self.assertEqual(sum(e['predicciones'] for e in panel['evolucion']), rows)
                self.assertEqual(panel['intervenciones'], {'PENDIENTE': 1, 'EJECUTADA': 1, 'CANCELADA': 0})
                year = first['gestion']
                filtered = (await client.get('/dashboard', params={'gestion': year})).json()
                self.assertTrue(all(c['gestion'] == year for c in filtered['alertas_por_curso']))
                self.assertEqual(len(filtered['evolucion']), len(panel['evolucion']))
                self.assertNotIn('codigo_anonimo', str(panel))
                self.user.rol = 'Docente'
                self.assertEqual((await client.get('/dashboard')).status_code, 403)
        asyncio.run(run())


    def test_reports_are_anonymized_and_filtered(self):
        import csv
        import io
        from api.reportes import router as reports_router, etiqueta
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            counts = real_t1.generate(self.db, excel, model_id)
            self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.include_router(reports_router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.assertEqual(etiqueta('EST-0042'), 'Estudiante 0042')
        self.assertEqual(etiqueta('EXT-0007'), 'Estudiante ext. 0007')

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                first = (await client.get('/alertas')).json()[0]
                item = (await client.post(f"/alertas/{first['id']}/intervenciones", json={'recomendacion': 'Citar a la familia'})).json()['id']
                await client.patch(f'/intervenciones/{item}', json={'estado': 'REALIZADA', 'tipo_accion': 'CITACION',
                    'accion_realizada': 'Reunión', 'fecha_ejecucion': '2024-05-02', 'resultado': 'Acuerdo'})
                year = first['gestion']
                expected = len((await client.get('/alertas', params={'gestion': year})).json())
                response = await client.get('/reportes/alertas.csv', params={'gestion': year})
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'reporte_alertas_{year}.csv', response.headers['content-disposition'])
                text = response.content.decode('utf-8-sig')
                self.assertIn('ranking de prioridad', text)
                self.assertIn('no sustituye', text)
                self.assertNotIn('ANONIMO', text)
                table = list(csv.DictReader(io.StringIO('\n'.join(l for l in text.splitlines() if not l.startswith('#')))))
                self.assertEqual(len(table), expected)
                self.assertTrue(all(r['estudiante'].startswith('Estudiante ') for r in table))
                row = next(r for r in table if 'Reunión' in r['intervenciones'])
                self.assertIn('[Citación al apoderado] Reunión', row['intervenciones'])
                self.assertIn('Resultado: Acuerdo', row['intervenciones'])
                by_course = (await client.get('/reportes/alertas.csv', params={'gestion': year, 'curso_id': first['curso_id']})).content.decode('utf-8-sig')
                self.assertIn(f"Curso {first['curso']}", by_course)
                pdf = await client.get('/reportes/alertas.pdf', params={'gestion': year, 'curso_id': first['curso_id']})
                self.assertEqual(pdf.headers['content-type'], 'application/pdf')
                self.assertTrue(pdf.content.startswith(b'%PDF'))
                self.assertEqual((await client.get('/reportes/alertas.pdf', params={'gestion': 1999})).status_code, 404)
                self.assertEqual((await client.get('/reportes/alertas.csv', params={'gestion': year, 'curso_id': 999999})).status_code, 404)
                self.user.rol = 'Docente'
                self.assertEqual((await client.get('/reportes/alertas.csv', params={'gestion': year})).status_code, 403)
        asyncio.run(run())


class ReglasRecomendacionTests(unittest.TestCase):
    def test_rules_fire_on_their_data_and_rp05_is_fallback(self):
        from predictivo import recomendaciones as rp
        base_ind = {f'{a}_T1': 75 for a in rp.AREAS} | {'promedio_T1': 75, 'faltas_T1': 0, 'atrasos_T1': 1, 'tasa_asistencia_T1': .95}
        self.assertEqual([r['codigo'] for r in rp.evaluar(base_ind, 'MEDIO')], ['RP05'])
        weak = base_ind | {'promedio_T1': 60, 'MAT_T1': 45, 'faltas_T1': 4, 'atrasos_T1': 4}
        result = {r['codigo']: r for r in rp.evaluar(weak, 'ALTO')}
        self.assertEqual(set(result), {'RP01', 'RP02', 'RP03', 'RP04', 'RP05'})
        self.assertIn('Matemática (45)', result['RP02']['dato'])
        self.assertEqual(result['RP01']['dato'], 'promedio_T1 = 60')
        self.assertNotIn('RP05', [r['codigo'] for r in rp.evaluar(weak, 'MEDIO')])
        self.assertTrue(all('pendiente de validación' in r['validacion'] for r in result.values()))


if __name__ == '__main__':
    unittest.main()
