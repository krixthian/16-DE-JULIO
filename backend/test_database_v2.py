"""Pruebas sobre la base configurada; las escrituras se revierten."""
import asyncio
import unittest
from datetime import date
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
import httpx
import models
from database import engine
from main import app
from api.auth import get_current_user
from core.security import create_access_token

class DatabaseV2Tests(unittest.TestCase):
    def test_database_structure(self):
        inspector = inspect(engine)
        self.assertEqual(set(inspector.get_table_names()), set(models.Base.metadata.tables))
        self.assertEqual(sum(len(inspector.get_foreign_keys(t)) for t in inspector.get_table_names()), 47)

    def test_checks_and_course_foreign_keys(self):
        with engine.connect() as conn:
            outer = conn.begin()
            db = Session(bind=conn, join_transaction_mode='create_savepoint')
            try:
                user = db.scalars(select(models.Usuario)).first()
                student = db.scalars(select(models.Estudiante)).first()
                gestion = models.Gestion(anio=9998, fecha_inicio=date(9998,1,1), fecha_fin=date(9998,12,31))
                db.add(gestion); db.flush()
                a = models.Curso(gestion_id=gestion.id,grado=1,paralelo='TESTA')
                b = models.Curso(gestion_id=gestion.id,grado=1,paralelo='TESTB')
                db.add_all([a,b]); db.flush()
                enrollment = models.Matricula(estudiante_id=student.id,curso_id=a.id,fecha_ingreso=date(9998,1,1),origen='SIMULADO',registrado_por=user.id)
                jornada = models.JornadaClase(curso_id=b.id,fecha=date(9998,1,2))
                db.add_all([enrollment,jornada]); db.flush()
                with self.assertRaises(IntegrityError) as fk_error:
                    with db.begin_nested():
                        db.add(models.Asistencia(matricula_id=enrollment.id,curso_id=a.id,jornada_id=jornada.id,estado='PRESENTE',registrado_por=user.id))
                        db.flush()
                self.assertEqual(fk_error.exception.orig.args[0],1452)
                with self.assertRaises(OperationalError) as check_error:
                    with db.begin_nested():
                        db.add(models.Curso(gestion_id=gestion.id,grado=9,paralelo='BAD'))
                        db.flush()
                self.assertEqual(check_error.exception.orig.args[0],3819)
            finally:
                db.close(); outer.rollback()

    def test_user_permissions_and_existing_tokens(self):
        async def check():
            with Session(engine) as db:
                user = db.scalars(select(models.Usuario).where(models.Usuario.activo == True)).first()
                token = create_access_token({'sub': user.email, 'rol': user.rol})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                self.assertEqual((await client.get('/users/')).status_code,401)
                self.assertEqual((await client.get('/auth/me',headers={'Authorization':f'Bearer {token}'})).status_code,200)
                app.dependency_overrides[get_current_user] = lambda: models.Usuario(id=123,rol='Docente',activo=True)
                try:
                    self.assertEqual((await client.get('/users/')).status_code,403)
                finally:
                    app.dependency_overrides.clear()
                app.dependency_overrides[get_current_user] = lambda: models.Usuario(id=123,rol='Admin',activo=True)
                try:
                    response=await client.get('/users/')
                    self.assertEqual(response.status_code,200)
                    self.assertTrue(all('password_hash' not in row for row in response.json()))
                finally:
                    app.dependency_overrides.clear()
        asyncio.run(check())

if __name__ == '__main__':
    unittest.main()
