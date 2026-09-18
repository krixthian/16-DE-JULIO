"""Migración hacia una base separada; nunca modifica el origen."""
import json
from pathlib import Path
from sqlalchemy import create_engine, inspect, text, select
from sqlalchemy.engine import make_url
from database import engine, Base
import models

ROOT = Path(__file__).resolve().parent
DESTINATION = 'alerta_temprana_v2'

def migrate():
    source_url = engine.url
    if source_url.database == DESTINATION:
        print('La aplicación ya utiliza v2. No se repite la copia.')
        return
    # Read all supported legacy records first, before creating anything.
    legacy = {}
    with engine.connect() as conn:
        for name in inspect(engine).get_table_names():
            if name not in ('usuarios', 'estudiantes', 'cursos'):
                if conn.execute(text(f'SELECT COUNT(*) FROM `{name}`')).scalar():
                    raise RuntimeError('Hay registros académicos existentes. Se requiere un mapeo adicional antes de migrar.')
        for name in ('usuarios', 'estudiantes', 'cursos'):
            legacy[name] = list(conn.execute(text(f'SELECT * FROM `{name}`')).mappings())
    admin = create_engine(source_url.set(database=None), hide_parameters=True)
    with admin.begin() as conn:
        exists = conn.execute(text('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:n'), {'n': DESTINATION}).scalar()
        if exists:
            raise RuntimeError('La base destino ya existe. No se sobrescribe. Revisa la migración anterior.')
        conn.execute(text(f'CREATE DATABASE `{DESTINATION}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'))
    target_url = source_url.set(database=DESTINATION)
    target = create_engine(target_url, hide_parameters=True)
    Base.metadata.create_all(target)
    pending = []
    with target.begin() as conn:
        for row in legacy['usuarios']:
            conn.execute(models.Usuario.__table__.insert().values(**{k: row[k] for k in models.Usuario.__table__.columns.keys() if k in row}))
        years = {}
        for row in legacy['cursos']:
            year = int(row['gestion'])
            if year not in years:
                years[year] = conn.execute(models.Gestion.__table__.insert().values(anio=year)).inserted_primary_key[0]
            import re
            grade = int(re.search(r'\d+', str(row['grado'])).group())
            if str(row['nivel']).lower() != 'primaria':
                raise RuntimeError('Existe un nivel fuera del alcance primaria.')
            conn.execute(models.Curso.__table__.insert().values(id=row['id'], gestion_id=years[year], nivel='PRIMARIA', grado=grade, paralelo=row['paralelo'], docente_asesor_id=row['docente_asesor_id']))
        for row in legacy['estudiantes']:
            conn.execute(models.Estudiante.__table__.insert().values(id=row['id'], codigo_anonimo=f"LEGACY-{row['id']:06d}", codigo_rude=row['codigo_rude'], nombre=row['nombre'], apellido=row['apellido'], fecha_nacimiento=row['fecha_nacimiento']))
            # Preserve unknown relationship dates in the source; do not fabricate a valid-since date.
            if row.get('nombre_apoderado'):
                apoderado_id = conn.execute(models.Apoderado.__table__.insert().values(nombre_completo=row['nombre_apoderado'], telefono=row.get('telefono_apoderado'))).inserted_primary_key[0]
            else:
                apoderado_id = None
            pending.append({'estudiante_id': row['id'], 'curso_id': row['curso_id'], 'apoderado_id': apoderado_id, 'pendiente': 'Confirmar fecha de ingreso, origen real/simulado, parentesco y vigencia del contacto; crear matrícula y vínculo familiar.'})
        assert conn.execute(select(text('count(*)')).select_from(models.Usuario)).scalar() == len(legacy['usuarios'])
        assert conn.execute(select(text('count(*)')).select_from(models.Estudiante)).scalar() == len(legacy['estudiantes'])
    if len(inspect(target).get_table_names()) != 27:
        raise RuntimeError('La estructura destino no está completa.')
    (ROOT/'migracion_v2_pendientes.json').write_text(json.dumps({'calendarios_pendientes': sorted(years), 'matriculas_pendientes': pending}, ensure_ascii=False, indent=2), encoding='utf-8')
    # Switch local configuration only after successful DDL, copy and verification.
    (ROOT/'.database-url').write_text(target_url.render_as_string(hide_password=False), encoding='utf-8')
    print(json.dumps({'tablas': 27, 'usuarios_copiados': len(legacy['usuarios']), 'estudiantes_copiados': len(legacy['estudiantes']), 'cursos_copiados': len(legacy['cursos']), 'matriculas_pendientes': len(pending), 'base_anterior_conservada': True}))

if __name__ == '__main__':
    migrate()
