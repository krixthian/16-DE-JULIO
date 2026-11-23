"""Asistencia por materia (por hora), licencia parcial y citaciones por origen.

Las pruebas de API corren dentro de una transacción que se deshace al final: no dejan registros en la base.
"""
import asyncio
import unittest
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from database import engine, get_db
from main import app
from predictivo import asistencia_materia as am
from predictivo.features import FEATURE_NAMES, VERSION
import models as m


class CalculosTests(unittest.TestCase):
    """Funciones puras: el porcentaje es por materia, no plano."""

    def setUp(self):
        # Lenguaje (materia 1): 10 clases dictadas, asistió a 9. Religión (materia 2): 2 clases, asistió a 1.
        self.sesiones = [{'id': i, 'materia_id': 1, 'dictada': True, 'jornada_id': i, 'periodo': 1} for i in range(1, 11)]
        self.sesiones += [{'id': 100 + i, 'materia_id': 2, 'dictada': True, 'jornada_id': i, 'periodo': 2} for i in (1, 2)]
        self.sesiones.append({'id': 200, 'materia_id': 2, 'dictada': False, 'jornada_id': 3, 'periodo': 2})
        self.registros = [{'sesion_id': i, 'estado': 'PRESENTE' if i < 10 else 'FALTA'} for i in range(1, 11)]
        self.registros += [{'sesion_id': 101, 'estado': 'PRESENTE'}, {'sesion_id': 102, 'estado': 'LICENCIA'}]

    def test_porcentaje_por_materia(self):
        r = am.por_materia(self.sesiones, self.registros)
        self.assertAlmostEqual(r[1]['porcentaje'], .9)
        self.assertAlmostEqual(r[2]['porcentaje'], .5)
        self.assertEqual(r[2]['dictadas'], 2, 'La clase no dictada no cuenta en el denominador.')
        # Un promedio plano (10 de 12 = 0,83) ocultaría que Religión está en 50 %.
        ind = am.indicadores(self.sesiones, self.registros, [])
        self.assertAlmostEqual(ind['asistencia_materia_media'], .7)
        self.assertAlmostEqual(ind['asistencia_materia_minima'], .5)
        self.assertEqual(ind['materias_asistencia_baja'], 1)

    def test_licencia_parcial(self):
        # Día 2: presente en la 1.ª hora (Lenguaje) y licencia en la 2.ª (Religión) -> llegó y se retiró.
        self.assertEqual(am.licencias_parciales(self.sesiones, self.registros), 1)
        # Licencia todo el día no es parcial.
        solo_licencia = [{'sesion_id': 2, 'estado': 'LICENCIA'}, {'sesion_id': 102, 'estado': 'LICENCIA'}]
        self.assertEqual(am.licencias_parciales(self.sesiones, solo_licencia), 0)

    def test_citaciones_por_origen_y_materia(self):
        cit = [{'origen': 'DOCENTE_MATERIA', 'materia_id': 1}] * 5 + [{'origen': 'DOCENTE_MATERIA', 'materia_id': 2}] * 2
        ind = am.indicadores([], [], cit)
        self.assertEqual((ind['citaciones_total'], ind['materias_con_citacion'], ind['citaciones_max_una_materia']), (7, 2, 5))
        ind = am.indicadores([], [], [{'origen': 'DIRECCION', 'materia_id': None}] * 7)
        self.assertEqual((ind['citaciones_total'], ind['citaciones_direccion'], ind['materias_con_citacion']), (7, 7, 0))
        # Sin registros, los indicadores de asistencia quedan desconocidos, no en cero.
        self.assertIsNone(am.indicadores([], [], [])['asistencia_materia_media'])

    def test_inasistencia_continua(self):
        d = lambda n: date(2026, 5, n)
        self.assertEqual(am.estado_del_dia('FALTA', ['PRESENTE']), 'FALTA', 'La asistencia diaria manda.')
        self.assertEqual(am.estado_del_dia(None, ['PRESENTE', 'LICENCIA']), 'ASISTE')
        self.assertEqual(am.estado_del_dia(None, ['FALTA', 'FALTA']), 'FALTA')
        self.assertEqual(am.estado_del_dia(None, ['FALTA', 'LICENCIA']), 'LICENCIA')
        self.assertIsNone(am.estado_del_dia(None, []))
        r = am.racha_actual([(d(4), 'ASISTE'), (d(5), 'FALTA'), (d(6), None), (d(7), 'FALTA'), (d(8), 'FALTA')])
        self.assertEqual((r['racha'], r['desde'], r['ultima_asistencia'], r['ultimo_registro']), (3, d(5), d(4), d(8)))
        self.assertEqual(am.racha_actual([(d(4), 'FALTA'), (d(5), 'LICENCIA')])['racha'], 0, 'Una licencia corta la racha de faltas.')

    def test_variables_nuevas_en_el_contrato(self):
        self.assertEqual(VERSION, 'primaria-materia-v2')
        self.assertTrue(set(am.DESCRIPCIONES) <= set(FEATURE_NAMES))
        self.assertFalse([n for n in FEATURE_NAMES if n.startswith('POST_')])


class AsistenciaMateriaApiTests(unittest.TestCase):
    def test_registro_por_hora_desglose_y_citaciones(self):
        async def run():
            with engine.connect() as conn:
                tx = conn.begin()
                db = Session(bind=conn, join_transaction_mode='create_savepoint')
                admin = db.scalar(select(m.Usuario).where(m.Usuario.rol == 'Admin'))
                teacher = m.Usuario(nombre='Temporal', apellido='Materia', email='subject-attendance@example.invalid', rol='Docente', activo=True)
                db.add(teacher)
                db.flush()
                year = m.Gestion(anio=1992, fecha_inicio=date(1992, 2, 1), fecha_fin=date(1992, 11, 30))
                db.add(year)
                db.flush()
                course = m.Curso(gestion_id=year.id, grado=3, paralelo='QM')
                db.add(course)
                db.flush()
                lenguaje, religion = m.Materia(nombre='Lenguaje QA materia'), m.Materia(nombre='Religión QA materia')
                db.add_all([lenguaje, religion])
                db.flush()
                db.add_all([m.AsignacionDocente(curso_id=course.id, materia_id=lenguaje.id, docente_id=teacher.id, vigente_desde=date(1992, 2, 1)),
                    m.AsignacionDocente(curso_id=course.id, materia_id=religion.id, docente_id=admin.id, vigente_desde=date(1992, 2, 1))])
                student = m.Estudiante(nombre='ANONIMO', apellido='EST-QA01', codigo_anonimo='EST-QA01')
                db.add(student)
                db.flush()
                enrollment = m.Matricula(estudiante_id=student.id, curso_id=course.id, fecha_ingreso=date(1992, 2, 1), origen='SIMULADO', registrado_por=admin.id)
                db.add(enrollment)
                db.flush()
                app.dependency_overrides[get_db] = lambda: db
                app.dependency_overrides[get_current_user] = lambda: admin
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
                        async def put(fecha, hora, materia, estado, status=200, **kw):
                            body = {'materia_id': materia, 'estudiantes': [{'matricula_id': enrollment.id, 'estado': estado}] if estado else [], **kw}
                            r = await c.put(f'/asistencia-materia/{course.id}/{fecha}/{hora}', json=body)
                            self.assertEqual(r.status_code, status, r.text)
                            return r.json()

                        dia = (await c.get(f'/asistencia-materia/{course.id}/1992-03-02')).json()
                        self.assertEqual({x['nombre'] for x in dia['materias']}, {'Lenguaje QA materia', 'Religión QA materia'})
                        self.assertEqual(dia['sesiones'], [])
                        # Lunes: 1.ª hora Lenguaje presente, 2.ª hora Religión con licencia -> licencia parcial.
                        await put('1992-03-02', 1, lenguaje.id, 'PRESENTE')
                        r = await put('1992-03-02', 2, religion.id, 'LICENCIA')
                        self.assertEqual([s['periodo'] for s in r['sesiones']], [1, 2])
                        # Martes y miércoles: Lenguaje, una falta.
                        await put('1992-03-03', 1, lenguaje.id, 'PRESENTE')
                        await put('1992-03-04', 1, lenguaje.id, 'FALTA')
                        # Clase no dictada: no lleva asistencia ni cuenta en el porcentaje.
                        await put('1992-03-05', 1, religion.id, None, dictada=False)
                        await put('1992-03-05', 2, religion.id, 'PRESENTE', status=422, dictada=False)
                        # Corregir una hora exige motivo y queda auditado.
                        await put('1992-03-04', 1, lenguaje.id, 'ATRASO', status=422)
                        await put('1992-03-04', 1, lenguaje.id, 'ATRASO', motivo_correccion='Llegó tarde, no faltó')
                        await put('1992-03-04', 1, religion.id, 'ATRASO', status=409, motivo_correccion='Cambiar materia')
                        await put(date.today() + timedelta(days=1), 1, lenguaje.id, 'PRESENTE', status=422)
                        await put('1992-03-06', 9, lenguaje.id, 'PRESENTE', status=422)

                        d = (await c.get(f'/asistencia-materia/matricula/{enrollment.id}/desglose')).json()
                        filas = {f['materia']: f for f in d['materias']}
                        self.assertAlmostEqual(filas['Lenguaje QA materia']['porcentaje'], 1.0)
                        self.assertEqual(filas['Lenguaje QA materia']['dictadas'], 3)
                        self.assertAlmostEqual(filas['Religión QA materia']['porcentaje'], 0.0)
                        self.assertEqual(filas['Religión QA materia']['dictadas'], 1)
                        self.assertEqual(d['indicadores']['dias_licencia_parcial'], 1)
                        self.assertEqual(d['indicadores']['materias_asistencia_baja'], 1)

                        # Citaciones: la de docente exige materia; la de dirección no lleva materia.
                        apoderado = m.Apoderado(nombre_completo='Apoderado QA')
                        db.add(apoderado)
                        db.flush()
                        db.add(m.EstudianteApoderado(estudiante_id=student.id, apoderado_id=apoderado.id, parentesco='Madre',
                            contacto_principal=True, vigente_desde=date(1992, 2, 1)))
                        db.flush()
                        self.assertEqual((await c.get(f'/citaciones/apoderados/{enrollment.id}')).json(),
                            [{'id': apoderado.id, 'nombre': 'Madre · contacto principal'}])
                        base = {'matricula_id': enrollment.id, 'apoderado_id': apoderado.id, 'fecha_programada': '1992-03-10T08:00:00', 'motivo': 'Inasistencias'}
                        self.assertEqual((await c.post('/citaciones', json={**base, 'origen': 'DOCENTE_MATERIA'})).status_code, 422)
                        self.assertEqual((await c.post('/citaciones', json={**base, 'origen': 'DIRECCION', 'materia_id': lenguaje.id})).status_code, 422)
                        for _ in range(2):
                            self.assertEqual((await c.post('/citaciones', json={**base, 'origen': 'DOCENTE_MATERIA', 'materia_id': religion.id})).status_code, 201)
                        r = await c.post('/citaciones', json={**base, 'origen': 'DIRECCION'})
                        self.assertEqual(r.status_code, 201)
                        ind = r.json()['indicadores']
                        self.assertEqual((ind['citaciones_total'], ind['citaciones_direccion'], ind['citaciones_max_una_materia']), (3, 1, 2))

                        # Alerta de inasistencia continua: 3 días seguidos faltando a todas sus horas.
                        for dia in ('1992-03-16', '1992-03-17', '1992-03-18'):
                            await put(dia, 1, lenguaje.id, 'FALTA')
                        r = (await c.get('/alertas/inasistencia', params={'gestion': 1992, 'dias': 3})).json()
                        fila = next(a for a in r['alertas'] if a['matricula_id'] == enrollment.id)
                        self.assertEqual((fila['racha'], str(fila['desde']), fila['estudiante']), (3, '1992-03-16', 'EST-QA01'))
                        self.assertNotIn(enrollment.id, [a['matricula_id'] for a in (await c.get('/alertas/inasistencia', params={'gestion': 1992, 'dias': 4})).json()['alertas']])
                        self.assertEqual((await c.get('/alertas/inasistencia', params={'gestion': 1992, 'dias': 1})).status_code, 422)

                        # El docente solo registra sus materias y solo cita por sus materias.
                        app.dependency_overrides[get_current_user] = lambda: teacher
                        await put('1992-03-09', 1, lenguaje.id, 'PRESENTE')
                        await put('1992-03-09', 2, religion.id, 'PRESENTE', status=403)
                        self.assertEqual((await c.post('/citaciones', json={**base, 'origen': 'DIRECCION'})).status_code, 403)
                        app.dependency_overrides[get_current_user] = lambda: m.Usuario(id=admin.id, rol='Orientador')
                        self.assertEqual((await c.get(f'/asistencia-materia/{course.id}/1992-03-02')).status_code, 403)
                        self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(
                            m.AuditoriaCambio.tabla_afectada == 'asistencias_materia')), 0)
                finally:
                    app.dependency_overrides.clear()
                    db.close()
                    tx.rollback()
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
