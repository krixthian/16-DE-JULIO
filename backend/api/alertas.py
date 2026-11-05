"""Alertas de riesgo e intervenciones. Solo identificadores anónimos; nunca nombres ni RUDE de estudiantes."""
from datetime import date, datetime, time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from api.auth import get_current_user
from api.escolar import Entrada
from database import get_db
from predictivo import recomendaciones as rp
import models as m


def seguimiento(user=Depends(get_current_user)):
    if user.rol not in ('Admin', 'Director', 'Orientador'):
        raise HTTPException(403, 'Solo administración, dirección y orientación gestionan alertas.')
    return user


router = APIRouter(tags=['Alertas e intervenciones'], dependencies=[Depends(seguimiento)])
ESTADOS_ALERTA = Literal['NUEVA', 'EN_REVISION', 'EN_SEGUIMIENTO', 'CERRADA']
ESTADOS_INTERVENCION = Literal['PROPUESTA', 'APROBADA', 'EN_CURSO', 'REALIZADA', 'CANCELADA']
NIVELES = Literal['MEDIO', 'ALTO']
ROLES_RESPONSABLE = ('Admin', 'Director', 'Orientador')
NOTA_PRIORIDAD = ('El nivel ordena la revisión (ranking de prioridad); la probabilidad no está calibrada y no es un riesgo absoluto. '
    'Umbrales MEDIO ≥ 0,5 y ALTO ≥ 0,8: propuesta pendiente de validar con Dirección.')


class CambioAlerta(Entrada):
    estado: ESTADOS_ALERTA | None = None
    responsable_id: int | None = None
    motivo_cierre: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def cierre(self):
        if self.estado is None and self.responsable_id is None:
            raise ValueError('Indica el estado o el responsable.')
        if self.estado == 'CERRADA' and not (self.motivo_cierre or '').strip():
            raise ValueError('Indica el motivo de cierre.')
        return self


class IntervencionEntrada(Entrada):
    recomendacion: str = Field(min_length=3, max_length=2000)
    fecha_planificada: date | None = None


class CambioIntervencion(Entrada):
    estado: ESTADOS_INTERVENCION
    accion_realizada: str | None = Field(default=None, max_length=1900)
    tipo_accion: Literal[tuple(rp.TIPOS_ACCION)] | None = None
    fecha_ejecucion: date | None = None
    resultado: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def realizada(self):
        if self.estado == 'REALIZADA' and not (self.accion_realizada or '').strip():
            raise ValueError('Describe la acción realizada.')
        if self.fecha_ejecucion and self.fecha_ejecucion > date.today():
            raise ValueError('La fecha de ejecución no puede ser futura.')
        return self


def snapshot(obj):
    campos = ('estado', 'responsable_id', 'cerrada_en', 'motivo_cierre') if isinstance(obj, m.Alerta) else \
        ('estado', 'recomendacion', 'regla_version', 'responsable_id', 'fecha_planificada', 'accion_realizada', 'resultado', 'realizada_en')
    return {k: getattr(obj, k) for k in campos}


def auditar(db, user, obj, operacion, antes, motivo):
    db.add(m.AuditoriaCambio(usuario_id=user.id, tabla_afectada=obj.__tablename__, registro_id=obj.id, operacion=operacion,
        motivo=motivo[:500], antes=jsonable_encoder(antes), despues=jsonable_encoder(snapshot(obj))))


def ranking(db, rows):
    """Puesto de cada predicción dentro de su gestión y modelo (1 = mayor puntaje)."""
    puntajes = {}
    for modelo, gestion in {(r[2].id, r[5].id) for r in rows}:
        valores = db.scalars(select(m.Prediccion.probabilidad)
            .join(m.CortePredictivo, m.CortePredictivo.id == m.Prediccion.corte_id)
            .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id).join(m.Curso, m.Curso.id == m.Matricula.curso_id)
            .where(m.Prediccion.modelo_id == modelo, m.Curso.gestion_id == gestion)).all()
        puntajes[modelo, gestion] = [float(v) for v in valores]
    return {r[0].id: (sum(v > float(r[1].probabilidad) for v in puntajes[r[2].id, r[5].id]) + 1, len(puntajes[r[2].id, r[5].id]))
        for r in rows}


def alerta_dict(row, total, puesto):
    a, p, mod, c, cur, g, e, u = row
    return {'id': a.id, 'estado': a.estado, 'creada_en': a.creada_en, 'cerrada_en': a.cerrada_en, 'motivo_cierre': a.motivo_cierre,
        'probabilidad': float(p.probabilidad), 'nivel': p.nivel, 'factores': (p.factores or {}).get('principales', []),
        'uso': (p.factores or {}).get('uso'), 'modelo': mod.version, 'fecha_corte': c.fecha_corte, 'gestion': g.anio,
        'curso_id': cur.id, 'curso': f'{cur.grado}° {cur.paralelo}', 'grado': cur.grado, 'estudiante': e.codigo_anonimo,
        'intervenciones': total, 'responsable': {'id': u.id, 'nombre': f'{u.nombre} {u.apellido}', 'rol': u.rol},
        'prioridad': {'puesto': puesto[0], 'de': puesto[1], 'nota': NOTA_PRIORIDAD}}


def consulta():
    return (select(m.Alerta, m.Prediccion, m.ModeloPredictivo, m.CortePredictivo, m.Curso, m.Gestion, m.Estudiante, m.Usuario)
        .join(m.Prediccion, m.Prediccion.id == m.Alerta.prediccion_id)
        .join(m.ModeloPredictivo, m.ModeloPredictivo.id == m.Prediccion.modelo_id)
        .join(m.CortePredictivo, m.CortePredictivo.id == m.Prediccion.corte_id)
        .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id)
        .join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id)
        .join(m.Usuario, m.Usuario.id == m.Alerta.responsable_id))


def totales(db, ids):
    rows = db.execute(select(m.Intervencion.alerta_id, func.count()).where(m.Intervencion.alerta_id.in_(ids)).group_by(m.Intervencion.alerta_id))
    return dict(rows.all())


def responder(db, rows):
    count, puestos = totales(db, [r[0].id for r in rows]), ranking(db, rows)
    return [alerta_dict(r, count.get(r[0].id, 0), puestos[r[0].id]) for r in rows]


@router.get('/alertas')
def listar(estado: ESTADOS_ALERTA | None = None, gestion: int | None = None, curso_id: int | None = None,
        nivel: NIVELES | None = None, responsable_id: int | None = None, db: Session = Depends(get_db)):
    query = consulta().order_by(m.Gestion.anio.desc(), m.Prediccion.probabilidad.desc())
    for column, value in ((m.Alerta.estado, estado), (m.Gestion.anio, gestion), (m.Curso.id, curso_id),
            (m.Prediccion.nivel, nivel), (m.Alerta.responsable_id, responsable_id)):
        if value is not None:
            query = query.where(column == value)
    return responder(db, db.execute(query).all())


@router.get('/alertas/resumen')
def resumen(db: Session = Depends(get_db)):
    niveles = dict(db.execute(select(m.Prediccion.nivel, func.count()).group_by(m.Prediccion.nivel)).all())
    estados = dict(db.execute(select(m.Alerta.estado, func.count()).group_by(m.Alerta.estado)).all())
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    return {'predicciones': niveles, 'alertas': estados, 'nota': NOTA_PRIORIDAD, 'modelo': modelo and {'version': modelo.version,
        'origen': modelo.origen_datos, 'umbral_medio': float(modelo.umbral_medio), 'umbral_alto': float(modelo.umbral_alto)}}


@router.get('/alertas/responsables')
def responsables(db: Session = Depends(get_db)):
    users = db.scalars(select(m.Usuario).where(m.Usuario.activo.is_(True), m.Usuario.rol.in_(ROLES_RESPONSABLE))
        .order_by(m.Usuario.rol, m.Usuario.apellido)).all()
    return [{'id': u.id, 'nombre': f'{u.nombre} {u.apellido}', 'rol': u.rol} for u in users]


def obtener(db, alert_id):
    row = db.execute(consulta().where(m.Alerta.id == alert_id)).first()
    if row is None:
        raise HTTPException(404, 'Alerta no encontrada.')
    return row


@router.patch('/alertas/{alert_id}')
def cambiar(alert_id: int, data: CambioAlerta, db: Session = Depends(get_db), user=Depends(seguimiento)):
    alerta = obtener(db, alert_id)[0]
    antes = snapshot(alerta)
    if data.responsable_id is not None:
        nuevo = db.get(m.Usuario, data.responsable_id)
        if nuevo is None or not nuevo.activo or nuevo.rol not in ROLES_RESPONSABLE:
            raise HTTPException(422, 'El responsable debe ser un usuario activo de administración, dirección u orientación.')
        alerta.responsable_id = nuevo.id
    if data.estado is not None:
        if alerta.estado == 'CERRADA' and data.estado != 'CERRADA':
            alerta.cerrada_en = alerta.motivo_cierre = None
        if data.estado == 'CERRADA':
            alerta.cerrada_en = alerta.cerrada_en or datetime.now().replace(microsecond=0)
            alerta.motivo_cierre = data.motivo_cierre.strip()
        alerta.estado = data.estado
    cambios = [k for k, v in antes.items() if v != getattr(alerta, k)]
    if cambios:
        auditar(db, user, alerta, 'CORRECCION', antes, 'Seguimiento de alerta: ' + ', '.join(cambios))
    db.commit()
    return responder(db, [obtener(db, alert_id)])[0]


@router.get('/alertas/{alert_id}/historial')
def historial(alert_id: int, db: Session = Depends(get_db)):
    obtener(db, alert_id)
    ids = db.scalars(select(m.Intervencion.id).where(m.Intervencion.alerta_id == alert_id)).all()
    cond = (m.AuditoriaCambio.tabla_afectada == 'alertas') & (m.AuditoriaCambio.registro_id == alert_id)
    if ids:
        cond = cond | ((m.AuditoriaCambio.tabla_afectada == 'intervenciones') & m.AuditoriaCambio.registro_id.in_(ids))
    rows = db.execute(select(m.AuditoriaCambio, m.Usuario.rol).join(m.Usuario, m.Usuario.id == m.AuditoriaCambio.usuario_id)
        .where(cond).order_by(m.AuditoriaCambio.registrado_en, m.AuditoriaCambio.id)).all()
    return [{'id': a.id, 'tabla': a.tabla_afectada, 'registro_id': a.registro_id, 'operacion': a.operacion, 'motivo': a.motivo,
        'antes': a.antes, 'despues': a.despues, 'registrado_en': a.registrado_en, 'rol': rol} for a, rol in rows]


def intervencion_dict(i):
    return {k: getattr(i, k) for k in ('id', 'alerta_id', 'recomendacion', 'regla_version', 'responsable_id', 'fecha_planificada', 'estado',
        'aprobada_por', 'aprobada_en', 'accion_realizada', 'resultado', 'realizada_en', 'creada_en')}


@router.get('/alertas/{alert_id}/intervenciones')
def intervenciones(alert_id: int, db: Session = Depends(get_db)):
    obtener(db, alert_id)
    items = db.scalars(select(m.Intervencion).where(m.Intervencion.alerta_id == alert_id).order_by(m.Intervencion.id)).all()
    return [intervencion_dict(i) for i in items]


def crear_intervencion(db, user, alerta, recomendacion, fecha, regla, motivo):
    if alerta.estado == 'CERRADA':
        raise HTTPException(409, 'La alerta está cerrada.')
    item = m.Intervencion(alerta_id=alerta.id, recomendacion=recomendacion, fecha_planificada=fecha,
        responsable_id=user.id, regla_version=regla)
    db.add(item)
    db.flush()
    auditar(db, user, item, 'ALTA', None, motivo)
    if alerta.estado == 'NUEVA':
        antes = snapshot(alerta)
        alerta.estado = 'EN_SEGUIMIENTO'
        auditar(db, user, alerta, 'CORRECCION', antes, 'Seguimiento de alerta: estado (al registrar intervención)')
    db.commit()
    db.refresh(item)
    return intervencion_dict(item)


@router.post('/alertas/{alert_id}/intervenciones', status_code=201)
def proponer(alert_id: int, data: IntervencionEntrada, db: Session = Depends(get_db), user=Depends(seguimiento)):
    alerta = obtener(db, alert_id)[0]
    return crear_intervencion(db, user, alerta, data.recomendacion, data.fecha_planificada, 'manual', 'Intervención registrada')


def reglas_alerta(db, row):
    activas = rp.evaluar((row[3].variables or {}).get('indicadores'), row[1].nivel)
    usadas = dict(db.execute(select(m.Intervencion.regla_version, m.Intervencion.id).where(
        m.Intervencion.alerta_id == row[0].id, m.Intervencion.regla_version.in_([r['regla_version'] for r in activas]))).all())
    return [{**r, 'intervencion_id': usadas.get(r['regla_version'])} for r in activas]


@router.get('/alertas/{alert_id}/recomendaciones')
def recomendaciones(alert_id: int, db: Session = Depends(get_db)):
    return {'version': rp.VERSION, 'validacion': rp.VALIDACION, 'tipos_accion': rp.TIPOS_ACCION,
        'reglas': reglas_alerta(db, obtener(db, alert_id))}


@router.post('/alertas/{alert_id}/recomendaciones/{codigo}', status_code=201)
def adoptar(alert_id: int, codigo: str, fecha_planificada: date | None = None, db: Session = Depends(get_db), user=Depends(seguimiento)):
    row = obtener(db, alert_id)
    regla = next((r for r in reglas_alerta(db, row) if r['codigo'] == codigo), None)
    if regla is None:
        raise HTTPException(422, f'La regla {codigo} no se activa para esta alerta.')
    if regla['intervencion_id']:
        raise HTTPException(409, f'La recomendación {codigo} ya está registrada como intervención.')
    texto = f"{regla['codigo']} · {regla['recomendacion']} Dato: {regla['dato']}. ({rp.VALIDACION}.)"
    return crear_intervencion(db, user, row[0], texto, fecha_planificada, regla['regla_version'], f'Recomendación {codigo} adoptada')


@router.patch('/intervenciones/{item_id}')
def actualizar(item_id: int, data: CambioIntervencion, db: Session = Depends(get_db), user=Depends(seguimiento)):
    item = db.get(m.Intervencion, item_id)
    if item is None:
        raise HTTPException(404, 'Intervención no encontrada.')
    now = datetime.now().replace(microsecond=0)
    antes = snapshot(item)
    if data.estado in ('APROBADA', 'EN_CURSO', 'REALIZADA') and item.aprobada_por is None:
        item.aprobada_por, item.aprobada_en = user.id, now
    if data.estado == 'REALIZADA':
        tipo = rp.TIPOS_ACCION[data.tipo_accion or 'OTRA']
        item.accion_realizada = f'[{tipo}] {data.accion_realizada.strip()}'
        item.realizada_en = datetime.combine(data.fecha_ejecucion, time()) if data.fecha_ejecucion else item.realizada_en or now
    item.estado = data.estado
    if data.resultado is not None:
        item.resultado = data.resultado
    auditar(db, user, item, 'CORRECCION', antes, f'Intervención: {antes["estado"]} → {data.estado}')
    db.commit()
    db.refresh(item)
    return intervencion_dict(item)
