"""Integración API/ORM en SQLite temporal; no usa datos ni tablas de MySQL.

SQLite verifica el contrato de persistencia y permisos. No sustituye pruebas de
concurrencia y tipos específicas de MySQL.
"""
import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, MetaData, Integer, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models as m
from api.predictivo import router
from api.auth import get_current_user
from database import get_db
from predictivo.source import register_model
from predictivo.training import train_baseline
from test_predictivo import training_fixture


class PredictivoApiTests(unittest.TestCase):
    def test_main_application_registers_routes_and_requires_authentication(self):
        from main import app
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                self.assertIn('/predictivo/cortes', app.openapi()['paths'])
                response = await client.get('/predictivo/variables')
                self.assertEqual(response.status_code, 401)
        asyncio.run(run())

    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        metadata = MetaData()
        for table in m.Base.metadata.sorted_tables:
            copied = table.to_metadata(metadata)
            for col in copied.c:
                col.type = col.type.as_generic()
                if col.primary_key and col.name == 'id':
                    col.type = Integer()
        metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = m.Usuario(id=1, nombre='Prueba', apellido='Temporal', email='temporal@example.invalid', rol='Admin', activo=True)
        self.db.add(self.user)
        self.db.add(m.Gestion(id=1, anio=2023, fecha_inicio=date(2023, 2, 1), fecha_fin=date(2023, 11, 30)))
        self.db.add(m.Curso(id=1, gestion_id=1, grado=2, paralelo='A'))
        self.db.add(m.Estudiante(id=1, codigo_anonimo='TEST-1', nombre='Ficticio', apellido='Temporal'))
        self.db.add(m.Matricula(id=1, estudiante_id=1, curso_id=1, fecha_ingreso=date(2023, 2, 1),
            origen='SIMULADO', registrado_por=1, creado_en=datetime(2023, 2, 1)))
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: self.user

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_permissions_preview_persistence_and_immutable_cuts(self):
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test') as client:
                request = dict(gestion_id=1, fecha_corte='2023-03-31', origen='SIMULADO')
                response = await client.get('/predictivo/variables')
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.json()['variables']), 40)
                response = await client.post('/predictivo/cortes/consultar', json=request)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['registros'][0]['estado'], 'DATOS_INSUFICIENTES')
                self.assertEqual(self.db.scalar(select(func.count()).select_from(m.CortePredictivo)), 0)
                first = await client.post('/predictivo/cortes', json=request)
                self.assertEqual(first.status_code, 201, first.text)
                again = await client.post('/predictivo/cortes', json=request)
                self.assertEqual(again.json()['ids'], first.json()['ids'])
                self.assertEqual(self.db.scalar(select(func.count()).select_from(m.CortePredictivo)), 1)
                self.assertEqual(self.db.scalar(select(func.count()).select_from(m.Prediccion)), 0)
                cut = self.db.get(m.CortePredictivo, first.json()['ids'][0])
                self.assertEqual(cut.variables['origen'], 'SIMULADO')
                self.db.get(m.Curso, 1).grado = 3
                self.db.commit()
                conflict = await client.post('/predictivo/cortes', json=request)
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(self.db.get(m.CortePredictivo, cut.id).variables['indicadores']['grado'], 2)
                for role in ('Docente', 'Orientador'):
                    self.user.rol = role
                    self.assertEqual((await client.post('/predictivo/cortes', json=request)).status_code, 403)
                self.user.rol = 'Director'
                self.assertEqual((await client.get('/predictivo/variables')).status_code, 200)
                self.assertEqual((await client.post('/predictivo/cortes/consultar', json={**request, 'fecha_corte': '2100-03-31'})).status_code, 422)
                self.assertEqual((await client.post('/predictivo/cortes/consultar', json={**request, 'gestion_id': 999})).status_code, 404)
                self.assertEqual((await client.post('/predictivo/cortes/consultar', json={**request, 'origen': 'REAL'})).json()['total'], 0)
        asyncio.run(run())

    def test_model_registry_hash_thresholds_origin_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'model'
            report = train_baseline(training_fixture(), out, 2023)
            with self.assertRaises(ValueError):
                register_model(self.db, report, out / 'modelo_xgboost.json', .8, .2)
            model_id = register_model(self.db, report, out / 'modelo_xgboost.json', .4, .7)
            self.db.commit()
            saved = self.db.get(m.ModeloPredictivo, model_id)
            self.assertEqual(saved.origen_datos, 'SIMULADO')
            self.assertEqual(saved.artefacto_sha256, report['modelo_sha256'])
            with self.assertRaises(ValueError):
                register_model(self.db, report, out / 'modelo_xgboost.json', .4, .7)
            (out / 'modelo_xgboost.json').write_text('{}')
            with self.assertRaises(ValueError):
                register_model(self.db, report, out / 'modelo_xgboost.json', .4, .7)


if __name__ == '__main__':
    unittest.main()
