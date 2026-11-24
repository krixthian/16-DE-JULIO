import asyncio
import unittest
from datetime import date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import get_current_user
from database import engine, get_db
from main import app
import models as m


class NotasDocenteTests(unittest.TestCase):
    """Notas desglosadas: por tipo, últimas 4 semanas, tareas seguidas sin entregar y permisos. Todo se revierte."""
    def test_desglose(self):
        async def run():
            with engine.connect() as conn:
                tx = conn.begin()
                db = Session(bind=conn, join_transaction_mode='create_savepoint')
                try:
                    admin = db.scalar(select(m.Usuario).where(m.Usuario.rol == 'Admin'))
                    doc, otro = (m.Usuario(nombre='Temporal', apellido='Notas', email=f'notas-qa{i}@example.invalid', rol='Docente', activo=True) for i in (1, 2))
                    db.add_all([doc, otro])
                    g = m.Gestion(anio=1993, fecha_inicio=date(1993, 2, 1), fecha_fin=date(1993, 11, 30))
                    db.add(g)
                    db.flush()
                    c = m.Curso(gestion_id=g.id, grado=2, paralelo='QA')
                    s = m.Materia(nombre='Materia desglose temporal')
                    p = m.Periodo(gestion_id=g.id, numero=1, fecha_inicio=date(1993, 2, 1), fecha_fin=date(1993, 11, 30))
                    db.add_all([c, s, p])
                    db.flush()
                    a = m.AsignacionDocente(curso_id=c.id, materia_id=s.id, docente_id=doc.id, vigente_desde=date(1993, 2, 1))
                    db.add(a)
                    ms = []
                    for i in range(3):
                        e = m.Estudiante(nombre='X', apellido='Y', codigo_anonimo=f'NOTAS-QA-{i}')
                        db.add(e)
                        db.flush()
                        ms.append(m.Matricula(estudiante_id=e.id, curso_id=c.id, fecha_ingreso=date(1993, 2, 1) if i < 2 else date(1993, 5, 1), origen='SIMULADO', registrado_por=admin.id))
                    db.add_all(ms)
                    db.flush()

                    def ev(tipo, d, maximo, notas, titulo='QA', dimension=None):
                        e = m.Evaluacion(asignacion_id=a.id, curso_id=c.id, gestion_id=g.id, periodo_id=p.id, titulo=titulo, tipo=tipo, dimension=dimension, fecha_aplicacion=d, puntaje_maximo=maximo)
                        db.add(e)
                        db.flush()
                        for mat, x in zip(ms, notas):
                            if x is not None:
                                db.add(m.Calificacion(evaluacion_id=e.id, matricula_id=mat.id, curso_id=c.id, estado='NO_PRESENTADA' if x == 'NP' else 'CALIFICADA', puntaje=None if x == 'NP' else x, registrado_por=admin.id))

                    ev('PRUEBA', date(1993, 3, 1), 45, [36, 'NP'])  # 80
                    ev('TRABAJO', date(1993, 4, 20), 10, [5, 0])  # 50; el cero real sí cuenta
                    ev('PRUEBA', date(1993, 4, 25), 45, [None, 45])  # sin nota no es cero
                    ev('PRUEBA', date(1993, 6, 1), 45, [45, 45])  # posterior a la fecha: no entra
                    ev('OTRA', date(1993, 4, 30), 100, [77, 88], 'Nota del 1.er trimestre - QA')  # cierre: aparte
                    ev('OTRA', date(1993, 4, 30), 45, [27, 36], 'Cierre del 1.er trimestre - Saber - QA', 'Saber')  # tampoco es actividad
                    for d, est in ((3, ('ENTREGADA', 'NO_ENTREGADA')), (4, ('NO_ENTREGADA', 'ENTREGADA')), (5, ('EXENTA', 'PENDIENTE')), (6, ('NO_ENTREGADA', 'ENTREGADA'))):
                        t = m.Tarea(asignacion_id=a.id, curso_id=c.id, titulo='QA', fecha_asignacion=datetime(1993, 4, 1), fecha_limite=datetime(1993, 4, d, 12))
                        db.add(t)
                        db.flush()
                        for mat, x in zip(ms, est):
                            db.add(m.EntregaTarea(tarea_id=t.id, matricula_id=mat.id, curso_id=c.id, estado=x, fecha_entrega=datetime(1993, 4, 2) if x == 'ENTREGADA' else None, registrado_por=admin.id))
                    db.flush()
                    app.dependency_overrides[get_db] = lambda: db
                    app.dependency_overrides[get_current_user] = lambda: doc
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as cl:
                        q = {'asignacion_id': a.id, 'fecha': '1993-04-30'}
                        r = await cl.get('/docente/notas', params=q)
                        self.assertEqual(r.status_code, 200, r.text)
                        r = r.json()
                        self.assertEqual((r['total_actividades'], r['total_tareas'], len(r['estudiantes'])), (3, 4, 2))
                        x, y = r['estudiantes']
                        self.assertNotIn('nombre', x)
                        self.assertEqual((x['por_tipo']['PRUEBA'], x['por_tipo']['TRABAJO'], x['promedio'], x['sin_nota']), (80, 50, 65, 1))
                        self.assertEqual((x['ultimas'], x['anteriores'], x['cambio']), (50, 80, -30))
                        self.assertEqual((y['promedio'], y['no_presentadas'], y['cambio']), (50, 1, None))
                        self.assertEqual(x['trimestres'], {'1': 77})
                        self.assertEqual((x['dimensiones'], r['curso_promedio']['dimensiones']), ({'1-Saber': 60}, {'1-Saber': 70}))
                        self.assertEqual(x['tareas'], dict(entregadas=1, no_entregadas=2, por_revisar=0, seguidas_sin_entregar=2))
                        self.assertEqual(y['tareas'], dict(entregadas=2, no_entregadas=1, por_revisar=1, seguidas_sin_entregar=0))
                        self.assertEqual(r['curso_promedio']['promedio'], 57.5)
                        # Quien ingresa después no arrastra lo anterior a su ingreso.
                        z = (await cl.get('/docente/notas', params={**q, 'fecha': '1993-06-02'})).json()['estudiantes'][2]
                        self.assertEqual((z['sin_nota'], z['promedio'], z['tareas']['por_revisar']), (1, None, 0))
                        self.assertEqual((await cl.get('/docente/notas', params={**q, 'fecha': '2999-01-01'})).status_code, 422)
                        ev('OTRA', date(1993, 4, 30), 45, [20, 40], 'Actividad del 1.er trimestre - Saber - Exposición', 'Saber')
                        ev('PRUEBA', date(1993, 4, 28), 45, ['NP', 30], 'Prueba corta', 'Saber')
                        db.flush()
                        r2 = (await cl.get('/docente/notas', params=q)).json()
                        self.assertEqual(r2['estudiantes'][0]['dimensiones'], {'1-Saber': 60}, 'La nota de cierre ya contiene sus actividades.')
                        self.assertEqual(r2['total_actividades'], 4, 'La del archivo, sin fecha propia, no cuenta como actividad fechada.')
                        qa = dict(q, matricula_id=x['matricula_id'], trimestre=1, dimension='Saber')
                        la = (await cl.get('/docente/notas/actividades', params=qa)).json()['actividades']
                        self.assertEqual([(i['titulo'], i['fecha'], i['puntaje'], i['estado'], i['curso']) for i in la],
                            [('Prueba corta', '1993-04-28', None, 'NO_PRESENTADA', 30), ('Exposición', None, 20, 'CALIFICADA', 30)])
                        self.assertEqual((await cl.get('/docente/notas/actividades', params=dict(qa, matricula_id=1))).status_code, 404)
                        app.dependency_overrides[get_current_user] = lambda: otro
                        self.assertEqual((await cl.get('/docente/notas/actividades', params=qa)).status_code, 403)
                        self.assertEqual((await cl.get('/docente/notas', params=q)).status_code, 403)
                finally:
                    app.dependency_overrides.clear()
                    db.close()
                    tx.rollback()
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
