"""Adaptadores de lectura. Importar este módulo no abre conexiones."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

TABLES = (
    'gestiones', 'cursos', 'matriculas', 'asignaciones_docentes', 'jornadas_clase',
    'asistencias', 'evaluaciones', 'calificaciones', 'tareas', 'entregas_tareas',
    'contextos_permanencia', 'registros_convivencia', 'situaciones_escolares',
)


def serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(type(value).__name__)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=serialize, allow_nan=False).encode()).hexdigest()


def from_json(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    tables = payload.get('tables', payload)
    missing = set(TABLES) - tables.keys()
    if missing:
        raise ValueError(f'Faltan tablas fuente: {sorted(missing)}')
    return {k: tables.get(k, []) for k in (*TABLES, 'auditoria_cambios')}


def from_mysql(db):
    from sqlalchemy import select
    import models as m
    tables = {}
    # Lectura consistente: el llamador mantiene una única transacción.
    for name in TABLES:
        table = m.Base.metadata.tables[name]
        cols = [c for c in table.c if c.name not in ('descripcion_objetiva', 'accion_inmediata', 'observacion', 'titulo')]
        tables[name] = [dict(row) for row in db.execute(select(*cols)).mappings()]
    audit = m.AuditoriaCambio.__table__
    tables['auditoria_cambios'] = [dict(row) for row in db.execute(select(audit).where(audit.c.tabla_afectada.in_(TABLES))).mappings()]
    return tables


def persist_cuts(db, rows):
    """Guardar cortes inmutables. No hace commit: lo decide el llamador."""
    from sqlalchemy import select
    import models as m
    ids = []
    for row in rows:
        enrollment = db.get(m.Matricula, row['matricula_id'])
        if enrollment is None or enrollment.origen != row['origen']:
            raise ValueError('La matrícula destino no coincide con el origen del corte.')
        # Bloqueo de matrícula serializa inserciones del mismo corte sin migración SQL.
        db.execute(select(m.Matricula.id).where(m.Matricula.id == enrollment.id).with_for_update())
        cutoff = date.fromisoformat(row['fecha_corte'])
        existing = db.scalars(select(m.CortePredictivo).where(m.CortePredictivo.matricula_id == enrollment.id,
            m.CortePredictivo.fecha_corte == cutoff, m.CortePredictivo.version_variables == row['version_variables']).with_for_update()).all()
        payload = {'indicadores': row['variables'], 'origen': row['origen'], 'gestion': row['gestion'], 'horizonte': row['horizonte']}
        if existing:
            if len(existing) != 1 or existing[0].variables != payload or existing[0].estado != row['estado']:
                raise ValueError('Ya existe un corte diferente. Revisar los datos o crear una nueva versión; no se sobrescribe.')
            ids.append(existing[0].id)
            continue
        obj = m.CortePredictivo(matricula_id=enrollment.id, fecha_corte=cutoff,
            disponible_hasta=datetime.fromisoformat(row['disponible_hasta']), version_variables=row['version_variables'],
            variables=payload, cobertura_asistencia=row['variables']['cobertura_asistencia'], estado=row['estado'], motivo=row['motivo'])
        db.add(obj)
        db.flush()
        ids.append(obj.id)
    return ids


def register_model(db, report, model_path, medium, high):
    from sqlalchemy import select
    import models as m
    if not 0 < medium < high < 1:
        raise ValueError('Los umbrales deben cumplir 0 < medio < alto < 1.')
    path = Path(model_path).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != report['modelo_sha256']:
        raise ValueError('El archivo del modelo no coincide con el reporte.')
    version = report['version_modelo']
    existing = db.scalar(select(m.ModeloPredictivo).where(m.ModeloPredictivo.version == version))
    if existing:
        raise ValueError('La versión de modelo ya está registrada.')
    obj = m.ModeloPredictivo(version=version, algoritmo='XGBoost', objetivo=report['objetivo'],
        version_variables=report['version_variables'], origen_datos=report['origen'], entrenado_en=datetime.fromisoformat(report['entrenado_en']),
        datos_hasta=date.fromisoformat(report['etiquetas_disponibles_hasta']), artefacto_uri=str(path),
        artefacto_sha256=report['modelo_sha256'], umbral_medio=medium, umbral_alto=high,
        protocolo_validacion=report['protocolo'], metricas=report)
    db.add(obj)
    db.flush()
    return obj.id
