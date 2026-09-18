"""Pruebas reales de restricciones; todos los registros se revierten."""
import unittest
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from database import engine
from models import Usuario, Estudiante, Curso, Matricula, ContextoPermanencia

class ContextosTests(unittest.TestCase):
    def test_historial_nulos_rangos_y_relaciones(self):
        with engine.connect() as conn:
            tx = conn.begin()
            db = Session(bind=conn, join_transaction_mode='create_savepoint')
            try:
                user = db.scalars(select(Usuario)).first()
                student = db.scalars(select(Estudiante)).first()
                course = db.scalars(select(Curso)).first()
                enrollment = Matricula(estudiante_id=student.id, curso_id=course.id,
                    fecha_ingreso=date(1901,1,1), origen='SIMULADO', registrado_por=user.id)
                db.add(enrollment); db.flush()
                base = dict(matricula_id=enrollment.id, fecha_observacion=date.today(),
                    ventana_desde=date.today()-timedelta(days=7), fuente='APODERADO',
                    instrumento_version='prueba-v1', origen='SIMULADO', registrado_por=user.id)
                a = ContextoPermanencia(**base, actividades_propuestas=0)
                b = ContextoPermanencia(**base, actividades_propuestas=5)
                db.add_all([a,b]); db.flush(); db.expire_all()
                self.assertIsNone(a.acoso_reportado)
                self.assertEqual(a.actividades_propuestas, 0)
                self.assertNotEqual(a.id, b.id)
                for change in ({'dias_apoyo_estudio_semana':8}, {'actividades_propuestas':2, 'actividades_iniciadas':3},
                               {'reuniones_convocadas':0, 'reuniones_atendidas':1},
                               {'clases_observadas':1, 'clases_con_participacion':2},
                               {'contactos_realizados':1, 'contactos_respondidos':2},
                               {'acuerdos_evaluables':0, 'acuerdos_cumplidos':1},
                               {'actividades_iniciadas':1, 'actividades_completadas':2},
                               {'ventana_desde':date.today()+timedelta(days=1)},
                               {'fecha_observacion':date.today()+timedelta(days=2)},
                               {'matricula_id':18446744073709551600}):
                    with self.subTest(change=change), self.assertRaises(DBAPIError):
                        with db.begin_nested():
                            db.add(ContextoPermanencia(**(base | change))); db.flush()
            finally:
                db.close(); tx.rollback()

if __name__ == '__main__':
    unittest.main()
