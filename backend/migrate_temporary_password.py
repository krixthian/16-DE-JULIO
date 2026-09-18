"""Añade campos de acceso temporal sin cambiar contraseñas existentes."""
from sqlalchemy import inspect, text
from database import engine


def migrate():
    existing = {c['name'] for c in inspect(engine).get_columns('usuarios')}
    columns = {
        'requiere_cambio_password': 'BOOLEAN NOT NULL DEFAULT FALSE',
        'password_temporal_vence_en': 'DATETIME NULL',
        'credencial_version': 'SMALLINT UNSIGNED NOT NULL DEFAULT 0',
    }
    with engine.begin() as conn:
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(text(f'ALTER TABLE usuarios ADD COLUMN {name} {definition}'))
    print('Campos de acceso temporal verificados.')


if __name__ == '__main__':
    migrate()
