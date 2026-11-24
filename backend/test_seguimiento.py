"""Seguimiento continuo: XGBoost recalculado cada mes y alerta inmediata de 5 faltas seguidas.

La prueba de API corre dentro de una transacción que se deshace al final: no deja registros en la base.
"""
import asyncio
import unittest
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import get_current_user
from database import engine, get_db
from main import app
from predictivo import seguimiento as sg
import models as m


class CalculosTests(unittest.TestCase):
    def test_variables_sin_fuga_ni_genero(self):
        self.assertFalse([v for v in sg.VARIABLES if v.startswith('POST_')])
        self.assertNotIn('genero_f', sg.VARIABLES)
        self.assertNotIn('edad_31marzo', sg.VARIABLES, 'La base no guarda fechas de nacimiento históricas.')
        self.assertEqual(set(sg.DESCRIPCION), set(sg.VARIABLES))

    def test_estado_del_dia(self):
        self.assertEqual(sg.codigo_dia('FALTA', ['PRESENTE']), 'F', 'La asistencia diaria manda.')
        self.assertEqual(sg.codigo_dia(None, ['FALTA', 'PRESENTE']), 'A')
        self.assertEqual(sg.codigo_dia(None, ['FALTA', 'ATRASO']), 'R')
        self.assertEqual(sg.codigo_dia(None, ['FALTA', 'FALTA']), 'F')
        self.assertEqual(sg.codigo_dia(None, ['FALTA', 'LICENCIA']), 'L')
        self.assertIsNone(sg.codigo_dia(None, []))

    def test_notas_por_area_y_calendario(self):
        prom, minima, bajas = sg.notas_trimestre([(1, 80), (1, 60), (2, 40)])
        self.assertEqual((prom, minima, bajas), (55.0, 40.0, 1))
        self.assertEqual(sg.notas_trimestre([]), (None, None, None))
        self.assertIsNone(sg.mes_modelo(date(2026, 1, 20)))
        self.assertEqual((sg.mes_modelo(date(2026, 6, 3)), sg.mes_modelo(date(2026, 11, 20))), (6, 10))
        self.assertEqual((sg.nivel(.85), sg.nivel(.5), sg.nivel(.49)), ('ALTO', 'MEDIO', 'BAJO'))

    def test_modelos_entrenados_y_validados(self):
        met = sg.metricas()
        self.assertIsNotNone(met, 'Falta artifacts/seguimiento_mensual_v2: ejecutar el entrenamiento.')
        self.assertEqual(met['variables'], sg.VARIABLES)
        self.assertEqual(set(met['cortes']), {'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct'})
        for mes, c in met['cortes'].items():
            self.assertIn('ic95', c['xgboost'], mes)
            self.assertTrue((sg.DIRECTORIO / f'modelo_{mes}.json').exists(), mes)
            self.assertTrue((sg.DIRECTORIO / f'modelo_{mes}_sin_2022.json').exists(), mes)


class SeguimientoApiTests(unittest.TestCase):
    def test_riesgo_a_la_fecha_y_alerta_inmediata(self):
        async def run():
            with engine.connect() as conn:
                tx = conn.begin()
                db = Session(bind=conn, join_transaction_mode='create_savepoint')
                admin = db.scalar(select(m.Usuario).where(m.Usuario.rol == 'Admin'))
                year = m.Gestion(anio=1993, fecha_inicio=date(1993, 2, 1), fecha_fin=date(1993, 11, 30))
                db.add(year)
                db.flush()
                course = m.Curso(gestion_id=year.id, grado=3, paralelo='QS')
                db.add(course)
                db.flush()
                mats = []
                for codigo in ('EST-QS01', 'EST-QS02'):
                    e = m.Estudiante(nombre='ANONIMO', apellido=codigo, codigo_anonimo=codigo, fecha_nacimiento=date(1985, 6, 1))
                    db.add(e)
                    db.flush()
                    mat = m.Matricula(estudiante_id=e.id, curso_id=course.id, fecha_ingreso=date(1993, 2, 1), origen='SIMULADO', registrado_por=admin.id)
                    db.add(mat)
                    db.flush()
                    mats.append(mat)
                dias = [date(1993, 5, 3) + timedelta(days=i) for i in range(50) if (date(1993, 5, 3) + timedelta(days=i)).weekday() < 5]
                for i, d in enumerate(dias):
                    j = m.JornadaClase(curso_id=course.id, fecha=d, es_lectiva=True)
                    db.add(j)
                    db.flush()
                    # EST-QS01 asiste normal; EST-QS02 deja de venir en los últimos 6 días de clase.
                    for mat, estado in ((mats[0], 'PRESENTE'), (mats[1], 'FALTA' if i >= len(dias) - 6 else 'PRESENTE')):
                        db.add(m.Asistencia(matricula_id=mat.id, jornada_id=j.id, curso_id=course.id, estado=estado, registrado_por=admin.id))
                db.flush()
                app.dependency_overrides[get_db] = lambda: db
                app.dependency_overrides[get_current_user] = lambda: admin
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
                        r = await c.get('/alertas/seguimiento', params={'gestion': 1993, 'fecha': dias[-1].isoformat()})
                        self.assertEqual(r.status_code, 200, r.text)
                        d = r.json()
                        self.assertEqual((d['mes'], d['total']), ('jun', 2))
                        primero = d['alertas'][0]
                        self.assertEqual((primero['estudiante'], primero['racha_actual'], primero['alerta_inmediata'], primero['puesto']),
                            ('EST-QS02', 6, True, 1))
                        self.assertGreater(primero['probabilidad'], d['alertas'][1]['probabilidad'])
                        self.assertFalse(d['alertas'][1]['alerta_inmediata'])
                        self.assertIsNotNone(d['validacion_del_corte'])
                        self.assertIn('modelo final', d['modelo_usado'])
                        self.assertNotIn('ANONIMO', r.text, 'Nunca nombres de estudiantes.')
                        # Solo lo registrado hasta la fecha: antes de las faltas no hay alerta inmediata.
                        antes = (await c.get('/alertas/seguimiento', params={'gestion': 1993, 'fecha': dias[-7].isoformat()})).json()
                        self.assertFalse(any(a['alerta_inmediata'] for a in antes['alertas']))
                        # Enero: todavía no hay seguimiento.
                        self.assertEqual((await c.get('/alertas/seguimiento', params={'gestion': 1993, 'fecha': '1993-01-15'})).json()['total'], 0)
                        self.assertEqual((await c.get('/alertas/seguimiento', params={'gestion': 1800})).status_code, 404)
                        self.assertEqual((await c.get('/alertas/inasistencia')).json()['dias'], 5)
                        resumen = (await c.get('/alertas/seguimiento/gestiones')).json()
                        fila = next(g for g in resumen['gestiones'] if g['gestion'] == 1993)
                        self.assertEqual((fila['matriculas'], fila['alertas_inmediatas'], fila['en_curso'], fila['falsas_alarmas']), (2, 1, True, None),
                            'Gestión simulada: la alerta cuenta, pero no se califica como falsa alarma.')

                        # Casos: la alerta inmediata se abre como caso (sin duplicar) y usa toda la gestión de alertas.
                        calculo = sg.calcular(db, 1993, dias[-1])
                        self.assertEqual(sg.abrir_inmediatas(db, calculo), 1)
                        self.assertEqual(sg.abrir_inmediatas(db, calculo), 0, 'No duplica casos abiertos.')
                        db.flush()
                        caso_id = sg.casos_abiertos(db, [mats[1].id])[mats[1].id][0]
                        casos = (await c.get('/alertas', params={'gestion': 1993})).json()
                        self.assertEqual([(x['id'], x['estudiante'], x['nivel'], x['modelo']) for x in casos], [(caso_id, 'EST-QS02', 'ALTO', sg.VERSION)])
                        por_que = (await c.get(f'/alertas/{caso_id}/explicacion')).json()
                        self.assertIn('6 faltas seguidas', por_que['nivel']['motivo'])
                        self.assertTrue(por_que['coincide_con_guardado'])
                        recs = [r['codigo'] for r in (await c.get(f'/alertas/{caso_id}/recomendaciones')).json()['reglas']]
                        self.assertIn('RP00', recs)
                        visto = (await c.get('/alertas/seguimiento', params={'gestion': 1993, 'fecha': dias[-1].isoformat()})).json()
                        self.assertEqual(next(x for x in visto['alertas'] if x['estudiante'] == 'EST-QS02')['caso']['id'], caso_id)
                        r = await c.post('/alertas/seguimiento/abrir', json={'matricula_id': mats[0].id, 'gestion': 1993, 'fecha': dias[-1].isoformat()})
                        self.assertEqual(r.status_code, 422, 'Las gestiones pasadas son de consulta.')
                        self.assertEqual((await c.get('/modelo/resultados')).status_code, 200, 'Resultados sigue usando el modelo anterior.')

                        # Vista del docente: solo los cursos donde tiene asignación; sin puntajes.
                        otro = m.Curso(gestion_id=year.id, grado=4, paralelo='QT')
                        db.add(otro)
                        db.flush()
                        e3 = m.Estudiante(nombre='ANONIMO', apellido='EST-QT01', codigo_anonimo='EST-QT01')
                        db.add(e3)
                        db.flush()
                        mat3 = m.Matricula(estudiante_id=e3.id, curso_id=otro.id, fecha_ingreso=date(1993, 2, 1), origen='SIMULADO', registrado_por=admin.id)
                        db.add(mat3)
                        db.flush()
                        for i, dia in enumerate(dias):
                            j = m.JornadaClase(curso_id=otro.id, fecha=dia, es_lectiva=True)
                            db.add(j)
                            db.flush()
                            db.add(m.Asistencia(matricula_id=mat3.id, jornada_id=j.id, curso_id=otro.id, estado='FALTA' if i >= len(dias) - 6 else 'PRESENTE', registrado_por=admin.id))
                        docente = m.Usuario(nombre='Temporal', apellido='Docente', email='docente-seguimiento@example.invalid', rol='Docente', activo=True)
                        db.add(docente)
                        db.flush()
                        materia = db.scalar(select(m.Materia))
                        db.add(m.AsignacionDocente(curso_id=course.id, materia_id=materia.id, docente_id=docente.id, vigente_desde=date(1993, 2, 1)))
                        db.flush()
                        params = {'gestion': 1993, 'fecha': dias[-1].isoformat()}
                        todo = (await c.get('/docente/alertas', params=params)).json()
                        self.assertEqual({a['estudiante'] for a in todo['alertas']}, {'EST-QS02', 'EST-QT01'}, 'Admin ve todos los cursos.')
                        app.dependency_overrides[get_current_user] = lambda: docente
                        r = await c.get('/docente/alertas', params=params)
                        self.assertEqual(r.status_code, 200, r.text)
                        mio = r.json()
                        self.assertEqual(([a['estudiante'] for a in mio['alertas']], mio['mis_cursos']), (['EST-QS02'], 1))
                        self.assertTrue(mio['alertas'][0]['alerta_inmediata'])
                        self.assertNotIn('probabilidad', mio['alertas'][0], 'El docente no ve puntajes del modelo.')
                        self.assertEqual((await c.get('/alertas/seguimiento', params=params)).status_code, 403, 'El docente no entra a la gestión de alertas.')
                        orientador = m.Usuario(nombre='Temporal', apellido='Orientador', email='orientador-seguimiento@example.invalid', rol='Orientador', activo=True)
                        app.dependency_overrides[get_current_user] = lambda: orientador
                        self.assertEqual((await c.get('/docente/alertas', params=params)).status_code, 403)
                finally:
                    app.dependency_overrides.clear()
                    db.close()
                    tx.rollback()
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
