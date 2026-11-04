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


if __name__ == '__main__':
    unittest.main()
