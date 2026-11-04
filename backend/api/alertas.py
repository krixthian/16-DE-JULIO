"""Alertas de riesgo e intervenciones. Solo identificadores anónimos; nunca nombres ni RUDE."""
from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from api.auth import get_current_user
from api.escolar import Entrada
from database import get_db
import models as m


def seguimiento(user=Depends(get_current_user)):
    if user.rol not in ('Admin', 'Director', 'Orientador'):
        raise HTTPException(403, 'Solo administración, dirección y orientación gestionan alertas.')
    return user


router = APIRouter(tags=['Alertas e intervenciones'], dependencies=[Depends(seguimiento)])
ESTADOS_ALERTA = Literal['NUEVA', 'EN_REVISION', 'EN_SEGUIMIENTO', 'CERRADA']
ESTADOS_INTERVENCION = Literal['PROPUESTA', 'APROBADA', 'EN_CURSO', 'REALIZADA', 'CANCELADA']


class CambioAlerta(Entrada):
    estado: ESTADOS_ALERTA
    motivo_cierre: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def cierre(self):
        if self.estado == 'CERRADA' and not self.motivo_cierre:
            raise ValueError('Indica el motivo de cierre.')
        return self


class IntervencionEntrada(Entrada):
    recomendacion: str = Field(min_length=3, max_length=2000)
    fecha_planificada: date | None = None


class CambioIntervencion(Entrada):
    estado: ESTADOS_INTERVENCION
    accion_realizada: str | None = Field(default=None, max_length=2000)
    resultado: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def realizada(self):
        if self.estado == 'REALIZADA' and not self.accion_realizada:
            raise ValueError('Describe la acción realizada.')
        return self


def alerta_dict(row, total):
    a, p, mod, c, cur, g, e = row
    return {'id': a.id, 'estado': a.estado, 'creada_en': a.creada_en, 'cerrada_en': a.cerrada_en, 'motivo_cierre': a.motivo_cierre,
        'probabilidad': float(p.probabilidad), 'nivel': p.nivel, 'factores': (p.factores or {}).get('principales', []),
        'uso': (p.factores or {}).get('uso'), 'modelo': mod.version, 'fecha_corte': c.fecha_corte, 'gestion': g.anio,
        'curso': f'{cur.grado}° {cur.paralelo}', 'estudiante': e.codigo_anonimo, 'intervenciones': total}


def consulta():
    return (select(m.Alerta, m.Prediccion, m.ModeloPredictivo, m.CortePredictivo, m.Curso, m.Gestion, m.Estudiante)
        .join(m.Prediccion, m.Prediccion.id == m.Alerta.prediccion_id)
        .join(m.ModeloPredictivo, m.ModeloPredictivo.id == m.Prediccion.modelo_id)
        .join(m.CortePredictivo, m.CortePredictivo.id == m.Prediccion.corte_id)
        .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id)
        .join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id))


def totales(db, ids):
    rows = db.execute(select(m.Intervencion.alerta_id, func.count()).where(m.Intervencion.alerta_id.in_(ids)).group_by(m.Intervencion.alerta_id))
    return dict(rows.all())


@router.get('/alertas')
def listar(estado: ESTADOS_ALERTA | None = None, gestion: int | None = None, db: Session = Depends(get_db)):
    query = consulta().order_by(m.Gestion.anio.desc(), m.Prediccion.probabilidad.desc())
    if estado:
        query = query.where(m.Alerta.estado == estado)
    if gestion:
        query = query.where(m.Gestion.anio == gestion)
    rows = db.execute(query).all()
    count = totales(db, [r[0].id for r in rows])
    return [alerta_dict(r, count.get(r[0].id, 0)) for r in rows]


@router.get('/alertas/resumen')
def resumen(db: Session = Depends(get_db)):
    niveles = dict(db.execute(select(m.Prediccion.nivel, func.count()).group_by(m.Prediccion.nivel)).all())
    estados = dict(db.execute(select(m.Alerta.estado, func.count()).group_by(m.Alerta.estado)).all())
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    return {'predicciones': niveles, 'alertas': estados, 'modelo': modelo and {'version': modelo.version,
        'origen': modelo.origen_datos, 'umbral_medio': float(modelo.umbral_medio), 'umbral_alto': float(modelo.umbral_alto)}}


def obtener(db, alert_id):
    row = db.execute(consulta().where(m.Alerta.id == alert_id)).first()
    if row is None:
        raise HTTPException(404, 'Alerta no encontrada.')
    return row


@router.patch('/alertas/{alert_id}')
def cambiar(alert_id: int, data: CambioAlerta, db: Session = Depends(get_db)):
    row = obtener(db, alert_id)
    alerta = row[0]
    if alerta.estado == 'CERRADA' and data.estado != 'CERRADA':
        alerta.cerrada_en = alerta.motivo_cierre = None
    if data.estado == 'CERRADA':
        alerta.cerrada_en, alerta.motivo_cierre = alerta.cerrada_en or datetime.now().replace(microsecond=0), data.motivo_cierre
    alerta.estado = data.estado
    db.commit()
    return alerta_dict(obtener(db, alert_id), totales(db, [alert_id]).get(alert_id, 0))


def intervencion_dict(i):
    return {k: getattr(i, k) for k in ('id', 'alerta_id', 'recomendacion', 'responsable_id', 'fecha_planificada', 'estado',
        'aprobada_por', 'aprobada_en', 'accion_realizada', 'resultado', 'realizada_en', 'creada_en')}


@router.get('/alertas/{alert_id}/intervenciones')
def intervenciones(alert_id: int, db: Session = Depends(get_db)):
    obtener(db, alert_id)
    items = db.scalars(select(m.Intervencion).where(m.Intervencion.alerta_id == alert_id).order_by(m.Intervencion.id)).all()
    return [intervencion_dict(i) for i in items]


@router.post('/alertas/{alert_id}/intervenciones', status_code=201)
def proponer(alert_id: int, data: IntervencionEntrada, db: Session = Depends(get_db), user=Depends(seguimiento)):
    alerta = obtener(db, alert_id)[0]
    if alerta.estado == 'CERRADA':
        raise HTTPException(409, 'La alerta está cerrada.')
    item = m.Intervencion(alerta_id=alert_id, recomendacion=data.recomendacion, fecha_planificada=data.fecha_planificada,
        responsable_id=user.id, regla_version='manual')
    db.add(item)
    if alerta.estado == 'NUEVA':
        alerta.estado = 'EN_SEGUIMIENTO'
    db.commit()
    db.refresh(item)
    return intervencion_dict(item)


@router.patch('/intervenciones/{item_id}')
def actualizar(item_id: int, data: CambioIntervencion, db: Session = Depends(get_db), user=Depends(seguimiento)):
    item = db.get(m.Intervencion, item_id)
    if item is None:
        raise HTTPException(404, 'Intervención no encontrada.')
    now = datetime.now().replace(microsecond=0)
    if data.estado in ('APROBADA', 'EN_CURSO', 'REALIZADA') and item.aprobada_por is None:
        item.aprobada_por, item.aprobada_en = user.id, now
    if data.estado == 'REALIZADA':
        item.realizada_en, item.accion_realizada = item.realizada_en or now, data.accion_realizada
    item.estado = data.estado
    if data.resultado is not None:
        item.resultado = data.resultado
    db.commit()
    db.refresh(item)
    return intervencion_dict(item)
