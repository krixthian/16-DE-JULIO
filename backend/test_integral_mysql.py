"""Actividad 20: el flujo de punta a punta sobre MySQL real, en una base de PRUEBAS desechable.

Solo corre si MYSQL_PRUEBAS_DB nombra una base que termina en "_pruebas" y está vacía (creada con
database_schema_actual.sql). Nunca usa la base real ni borra nada; para repetir, recrear la base de pruebas.
"""
import os
import unittest
from datetime import date, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import models as m
import test_integral

NAME = os.environ.get('MYSQL_PRUEBAS_DB', '')


@unittest.skipUnless(NAME.endswith('_pruebas'), 'Define MYSQL_PRUEBAS_DB=<base>_pruebas para correr sobre MySQL.')
class IntegralMySQLTests(unittest.TestCase):
    prepare = test_integral.IntegralTests.prepare
    client = test_integral.IntegralTests.client
    test_end_to_end_follow_up_workflow = test_integral.IntegralTests.test_end_to_end_follow_up_workflow

    def setUp(self):
        from database import engine
        self.engine = create_engine(engine.url.set(database=NAME), hide_parameters=True)
        self.db = Session(self.engine)
        if self.db.scalar(select(func.count()).select_from(m.Usuario)):
            self.skipTest('La base de pruebas ya tiene datos: recréala vacía para repetir.')
        self.user = m.Usuario(id=1, nombre='Prueba', apellido='Temporal', email='temporal@colegio-prueba.bo', rol='Admin', activo=True)
        self.db.add(self.user)
        self.db.flush()
        self.db.add(m.Gestion(id=1, anio=2023, fecha_inicio=date(2023, 2, 1), fecha_fin=date(2023, 11, 30)))
        self.db.flush()
        self.db.add(m.Curso(id=1, gestion_id=1, grado=2, paralelo='A'))
        self.db.flush()
        self.db.add(m.Estudiante(id=1, codigo_anonimo='TEST-1', nombre='Ficticio', apellido='Temporal'))
        self.db.flush()
        self.db.add(m.Matricula(id=1, estudiante_id=1, curso_id=1, fecha_ingreso=date(2023, 2, 1),
            origen='SIMULADO', registrado_por=1, creado_en=datetime(2023, 2, 1)))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()


if __name__ == '__main__':
    unittest.main()
