"""Correo SMTP con TLS; las credenciales se leen de configuración local privada."""
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse


class MailError(Exception):
    pass


def mail_settings():
    path = Path(__file__).resolve().parents[1] / '.mail.json'
    try:
        settings = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
        if not isinstance(settings, dict):
            raise ValueError()
        for key in ('SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_SECURITY', 'APP_URL'):
            if key in os.environ:
                settings[key] = os.environ[key]
        if not all(settings.get(k) for k in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM', 'APP_URL')):
            raise ValueError()
        settings['SMTP_PORT'] = int(settings.get('SMTP_PORT', 587))
        settings.setdefault('SMTP_SECURITY', 'starttls')
        if settings['SMTP_SECURITY'] not in ('starttls', 'ssl'):
            raise ValueError()
        if urlparse(settings['APP_URL']).scheme not in ('http', 'https'):
            raise ValueError()
        return settings
    except (ValueError, OSError, TypeError):
        raise MailError('Configura el correo de salida en backend/.mail.json antes de registrar docentes.') from None


def send_temporary_password(recipient, password, settings):
    message = EmailMessage()
    message['Subject'] = 'Tu acceso al sistema — U.E. 16 de Julio'
    message['From'] = settings['SMTP_FROM']
    message['To'] = recipient
    message.set_content(
        'Se ha creado o renovado tu acceso al Sistema de Alerta Temprana.\n\n'
        f"Ingresar: {settings['APP_URL'].rstrip('/')}/login\n"
        f'Correo: {recipient}\nContraseña temporal: {password}\n\n'
        'La contraseña vence en 24 horas. Al ingresar deberás establecer una nueva.\n'
        'Si venció, solicita al administrador un nuevo envío. No compartas esta contraseña.\n'
    )
    try:
        context = ssl.create_default_context()
        if settings['SMTP_SECURITY'] == 'ssl':
            server = smtplib.SMTP_SSL(settings['SMTP_HOST'], settings['SMTP_PORT'], timeout=10, context=context)
        else:
            server = smtplib.SMTP(settings['SMTP_HOST'], settings['SMTP_PORT'], timeout=10)
        with server:
            if settings['SMTP_SECURITY'] == 'starttls':
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            server.login(settings['SMTP_USER'], settings['SMTP_PASSWORD'])
            if server.send_message(message):
                raise MailError('El servidor rechazó el destinatario.')
    except (OSError, smtplib.SMTPException, ValueError):
        raise MailError('No se pudo enviar el correo. Revisa la configuración y vuelve a intentarlo.') from None
