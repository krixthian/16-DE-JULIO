"""Pruebas de acceso temporal: transacciones revertidas, sin correo externo."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from main import app
from database import engine, get_db
from models import Usuario
from core.security import create_access_token, verify_password
from core.mail import MailError, send_temporary_password


class TemporaryPasswordTests(unittest.TestCase):
    def setUp(self):
        self.conn = engine.connect()
        self.tx = self.conn.begin()
        self.db = Session(bind=self.conn, join_transaction_mode='create_savepoint')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        admin = self.db.scalars(select(Usuario).where(Usuario.rol == 'Admin', Usuario.activo == True)).first()
        self.headers = {'Authorization': 'Bearer ' + create_access_token({'sub': admin.email, 'cv': admin.credencial_version})}
        self.email = f'test-{uuid4().hex}@example.org'
        self.settings = patch('api.users.mail_settings', return_value={})
        self.sender = patch('api.users.send_temporary_password')
        self.settings.start()
        self.send = self.sender.start()

    def tearDown(self):
        self.sender.stop()
        self.settings.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.tx.rollback()
        self.conn.close()

    def create(self):
        return self.client.post('/users/', headers=self.headers, json={'nombre':'Prueba', 'apellido':'Temporal', 'email':self.email, 'rol':'Docente'})

    def login(self, password):
        return self.client.post('/auth/login', data={'username': self.email, 'password':password})

    def test_complete_flow_and_revocation(self):
        response = self.create()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['requiere_cambio_password'])
        password = self.send.call_args.args[1]
        self.assertNotIn(password, response.text)
        user = self.db.scalars(select(Usuario).where(Usuario.email == self.email)).one()
        self.assertTrue(verify_password(password, user.password_hash))
        self.assertNotEqual(password, user.password_hash)
        token = self.login(password).json()['access_token']
        headers = {'Authorization':'Bearer '+token}
        self.assertEqual(self.client.get('/auth/me', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/asistencia/cursos', headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/users/', headers=headers, json={'nombre':'X','apellido':'Y','email':'other@example.org'}).status_code, 403)
        self.assertEqual(self.client.post('/auth/change-password', headers=headers, json={'current_password':'incorrecta','new_password':'NuevaSegura12345!'}).status_code, 400)
        self.assertEqual(self.client.post('/auth/change-password', headers=headers, json={'current_password':password,'new_password':'corta'}).status_code, 422)
        change = self.client.post('/auth/change-password', headers=headers, json={'current_password':password,'new_password':'NuevaSegura12345!'})
        self.assertEqual(change.status_code, 200, change.text)
        self.assertEqual(self.client.get('/auth/me', headers=headers).status_code, 401)
        self.assertEqual(self.login(password).status_code, 401)
        self.assertEqual(self.login('NuevaSegura12345!').status_code, 200)
        new_headers = {'Authorization':'Bearer '+change.json()['access_token']}
        self.assertEqual(self.client.get('/asistencia/cursos', headers=new_headers).status_code, 200)
        self.assertEqual(self.client.post(f'/users/{user.id}/resend-temporary-password', headers=self.headers).status_code, 409)

    def test_failure_expiration_and_resend(self):
        self.send.side_effect = MailError('Fallo de correo')
        self.assertEqual(self.create().status_code, 503)
        self.assertIsNone(self.db.scalars(select(Usuario).where(Usuario.email == self.email)).first())
        self.send.side_effect = None
        created = self.create()
        self.assertEqual(created.status_code, 200)
        old_password = self.send.call_args.args[1]
        self.assertEqual(self.create().status_code, 400)
        user = self.db.get(Usuario, created.json()['id'])
        user.password_temporal_vence_en = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.login(old_password).status_code, 401)
        self.assertEqual(self.client.post(f'/users/{user.id}/resend-temporary-password', headers=self.headers).status_code, 200)
        new_password = self.send.call_args.args[1]
        self.assertNotEqual(old_password, new_password)
        self.assertEqual(self.login(old_password).status_code, 401)
        self.assertEqual(self.login(new_password).status_code, 200)
        self.send.side_effect = MailError('Fallo de correo')
        self.assertEqual(self.client.post(f'/users/{user.id}/resend-temporary-password', headers=self.headers).status_code, 503)
        self.assertEqual(self.login(new_password).status_code, 200)

    def test_missing_settings(self):
        with patch('api.users.mail_settings', side_effect=MailError('Configura el correo')):
            self.assertEqual(self.create().status_code, 503)
        self.send.assert_not_called()


class MailTransportTests(unittest.TestCase):
    def test_tls_message_and_rejection(self):
        settings = {'SMTP_HOST':'smtp.example.org', 'SMTP_PORT':587, 'SMTP_SECURITY':'starttls', 'SMTP_USER':'sender@example.org', 'SMTP_PASSWORD':'test', 'SMTP_FROM':'sender@example.org', 'APP_URL':'https://school.example.org'}
        with patch('core.mail.smtplib.SMTP') as smtp:
            server = smtp.return_value
            server.send_message.return_value = {}
            send_temporary_password('teacher@example.org', 'temporary-test', settings)
            server.starttls.assert_called_once()
            server.login.assert_called_once()
            message = server.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'teacher@example.org')
            self.assertIn('https://school.example.org/login', message.get_content())
            server.send_message.return_value = {'teacher@example.org':(550, b'rejected')}
            with self.assertRaises(MailError):
                send_temporary_password('teacher@example.org', 'temporary-test', settings)
