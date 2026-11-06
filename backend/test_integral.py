"""Actividad 20: pruebas integrales sobre la aplicación completa (main.app) con SQLite temporal y datos ficticios.

- Matriz de permisos: cada endpoint × cada rol, más acceso sin sesión.
- Flujo de punta a punta: predicción → alerta → recomendación → intervención → cierre → panel → reportes → auditoría.
"""
import asyncio
import re
import tempfile
import unittest

import httpx
from fastapi.routing import APIRoute
from sqlalchemy import select, func

import main
import models as m
from api.auth import get_current_user
from database import get_db
from predictivo import real_t1
import test_alertas
import test_predictivo_api as base

ROLES = ('Admin', 'Director', 'Docente', 'Orientador')
SEGUIMIENTO = {'Admin', 'Director', 'Orientador'}
ESCOLAR = {'Admin', 'Director'}
PERSONAL = {'Admin', 'Director', 'Docente'}
POLITICA = [  # (prefijo de ruta, roles permitidos); None = público
    ('/auth/login', None), ('/auth/me', set(ROLES)), ('/users', {'Admin'}), ('/escolar', ESCOLAR), ('/predictivo', ESCOLAR),
    ('/asistencia', PERSONAL), ('/calificaciones/periodos', ESCOLAR), ('/calificaciones', PERSONAL), ('/tareas', PERSONAL),
    ('/alertas', SEGUIMIENTO), ('/intervenciones', SEGUIMIENTO), ('/dashboard', SEGUIMIENTO), ('/reportes', SEGUIMIENTO),
    ('/health', None), ('/', None)]


def politica(path):
    return next(roles for prefix, roles in POLITICA if path == prefix or path.startswith(prefix.rstrip('/') + '/') or prefix == path)


def rutas():
    for route in main.app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                url = re.sub(r'\{fecha\}', '2024-05-02', re.sub(r'\{(\w+)\}', '999999', route.path))
                yield method, route.path, url


class IntegralTests(unittest.TestCase):
    setUp = base.PredictivoApiTests.setUp
    tearDown = base.PredictivoApiTests.tearDown
    prepare = test_alertas.AlertasApiTests.prepare

    def client(self):
        main.app.dependency_overrides[get_db] = lambda: self.db
        main.app.dependency_overrides[get_current_user] = lambda: self.user
        self.addCleanup(main.app.dependency_overrides.clear)
        # El esquema de respuesta valida el correo: example.invalid es un dominio reservado.
        self.user.email = 'usuario.prueba@colegio-prueba.bo'
        self.db.commit()
        transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
        return httpx.AsyncClient(transport=transport, base_url='http://test')

    async def call(self, client, method, url):
        params = {'gestion': 2023} if url.startswith('/reportes') else None
        body = {} if method in ('POST', 'PUT', 'PATCH') else None
        if url == '/auth/login':
            return await client.post(url, data={'username': 'nadie@example.invalid', 'password': 'x'})
        return await client.request(method, url, json=body, params=params)

    def test_every_endpoint_enforces_role_policy(self):
        routes = list(rutas())
        self.assertGreaterEqual(len(routes), 58)
        failures = []

        async def run():
            async with self.client() as client:
                for method, path, url in routes:
                    allowed = politica(path)
                    guard_detail = None
                    for rol in ROLES:
                        self.user.rol = rol
                        response = await self.call(client, method, url)
                        self.db.rollback()
                        if allowed is not None and rol not in allowed:
                            if response.status_code != 403:
                                failures.append(f'{rol} {method} {path}: esperaba 403, obtuvo {response.status_code}')
                            guard_detail = response.json().get('detail')
                        elif response.status_code == 500 or (response.status_code == 401 and path != '/auth/login'):
                            failures.append(f'{rol} {method} {path}: {response.status_code}')
                    for rol in (allowed or ()):
                        self.user.rol = rol
                        response = await self.call(client, method, url)
                        self.db.rollback()
                        if response.status_code == 403 and guard_detail and response.json().get('detail') == guard_detail:
                            failures.append(f'{rol} {method} {path}: bloqueado por la regla de rol')
        asyncio.run(run())
        self.assertEqual(failures, [])

    def test_protected_endpoints_require_a_session(self):
        failures = []

        async def run():
            async with self.client() as client:
                main.app.dependency_overrides.pop(get_current_user)
                for method, path, url in rutas():
                    if politica(path) is None:
                        continue
                    response = await self.call(client, method, url)
                    if response.status_code != 401:
                        failures.append(f'{method} {path}: {response.status_code}')
                bad_login = await client.post('/auth/login', data={'username': 'nadie@example.invalid', 'password': 'x'})
                self.assertEqual(bad_login.status_code, 401)
                self.assertEqual((await client.get('/auth/me', headers={'Authorization': 'Bearer token-falso'})).status_code, 401)
        asyncio.run(run())
        self.assertEqual(failures, [])

    def test_end_to_end_follow_up_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            excel, model_id, rows = self.prepare(directory)
            counts = real_t1.generate(self.db, excel, model_id)
            self.db.commit()
        self.db.add(m.Usuario(id=2, nombre='Orientación', apellido='Prueba', email='o@example.invalid', rol='Orientador', activo=True))
        self.db.commit()

        async def run():
            async with self.client() as client:
                # Orientación revisa la alerta de mayor prioridad, la asume y registra la recomendación.
                self.user.rol = 'Orientador'
                alerts = (await client.get('/alertas')).json()
                self.assertEqual(len(alerts), counts['alertas'])
                first = alerts[0]
                self.assertEqual(first['prioridad']['puesto'], 1)
                self.assertEqual((await client.patch(f"/alertas/{first['id']}", json={'responsable_id': 2, 'estado': 'EN_REVISION'})).status_code, 200)
                rule = (await client.get(f"/alertas/{first['id']}/recomendaciones")).json()['reglas'][0]
                item = (await client.post(f"/alertas/{first['id']}/recomendaciones/{rule['codigo']}")).json()
                self.assertEqual(item['estado'], 'PROPUESTA')
                for estado in ('APROBADA', 'EN_CURSO'):
                    self.assertEqual((await client.patch(f"/intervenciones/{item['id']}", json={'estado': estado})).status_code, 200)
                done = await client.patch(f"/intervenciones/{item['id']}", json={'estado': 'REALIZADA', 'tipo_accion': 'CITACION',
                    'accion_realizada': 'Reunión con el apoderado', 'fecha_ejecucion': '2024-05-10', 'resultado': 'Compromiso de asistencia'})
                self.assertEqual(done.status_code, 200, done.text)
                closed = await client.patch(f"/alertas/{first['id']}", json={'estado': 'CERRADA', 'motivo_cierre': 'Asiste con normalidad'})
                self.assertEqual(closed.json()['estado'], 'CERRADA')
                self.assertEqual((await client.post(f"/alertas/{first['id']}/intervenciones", json={'recomendacion': 'Otra'})).status_code, 409)

                # Dirección ve el resultado en el panel y en los reportes.
                self.user.rol = 'Director'
                panel = (await client.get('/dashboard', params={'gestion': first['gestion']})).json()
                self.assertEqual(panel['intervenciones']['EJECUTADA'], 1)
                self.assertEqual(panel['resumen']['alertas_cerradas'], 1)
                csv_text = (await client.get('/reportes/alertas.csv', params={'gestion': first['gestion']})).content.decode('utf-8-sig')
                self.assertIn('[Citación al apoderado] Reunión con el apoderado', csv_text)
                self.assertIn('Cerrada', csv_text)
                pdf = await client.get('/reportes/alertas.pdf', params={'gestion': first['gestion'], 'curso_id': first['curso_id']})
                self.assertTrue(pdf.content.startswith(b'%PDF'))

                # Todo quedó auditado y un docente no accede al seguimiento.
                history = (await client.get(f"/alertas/{first['id']}/historial")).json()
                self.assertGreaterEqual(len(history), 6)
                self.assertEqual({h['tabla'] for h in history}, {'alertas', 'intervenciones'})
                self.user.rol = 'Docente'
                for url in ('/alertas', '/dashboard', f"/alertas/{first['id']}/historial"):
                    self.assertEqual((await client.get(url)).status_code, 403)
        asyncio.run(run())
        self.assertEqual(self.db.scalar(select(func.count()).select_from(m.Intervencion)), 1)


if __name__ == '__main__':
    unittest.main()
