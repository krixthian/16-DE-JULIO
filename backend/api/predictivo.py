"""Administración de indicadores. El entrenamiento permanece fuera del servidor web."""
from collections import Counter
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy.orm import Session
from api.escolar import Entrada, encargado
from database import get_db
from predictivo.features import VERSION, DESCRIPTIONS, build_features
from predictivo.source import from_mysql, persist_cuts

router = APIRouter(prefix='/predictivo', tags=['Indicadores predictivos'], dependencies=[Depends(encargado)])


class SolicitudCorte(Entrada):
    gestion_id: int = Field(gt=0)
    fecha_corte: date
    origen: Literal['REAL', 'SIMULADO']

    @model_validator(mode='after')
    def fecha_valida(self):
        if self.fecha_corte > date.today():
            raise ValueError('No se permiten cortes futuros.')
        return self


@router.get('/variables')
def variables():
    return {'version': VERSION, 'corte_inicial': '03-31', 'variables': DESCRIPTIONS,
        'suficiencia': {'min_asistencias': 5, 'min_cobertura': .8, 'min_notas': 1, 'min_tareas_confirmadas': 1},
        'advertencia': 'Suficiencia técnica inicial, no validación de riesgo. Revisar cobertura del calendario.'}


def calcular(data, db):
    import models as m
    if db.get(m.Gestion, data.gestion_id) is None:
        raise HTTPException(404, 'Gestión no encontrada.')
    try:
        return build_features(from_mysql(db), data.fecha_corte, data.origen, data.gestion_id)
    except (ValueError, KeyError) as error:
        raise HTTPException(422, f'Revisar consistencia de los registros: {error}') from error


@router.post('/cortes/consultar')
def consultar(data: SolicitudCorte, db: Session = Depends(get_db)):
    rows = calcular(data, db)
    return {'version': VERSION, 'total': len(rows), 'estados': dict(Counter(r['estado'] for r in rows)), 'registros': rows,
        'mensaje': None if rows else 'No hay matrículas de este origen disponibles en la fecha de corte. Los registros ingresados después no se trasladan al pasado.'}


@router.post('/cortes', status_code=201)
def guardar(data: SolicitudCorte, db: Session = Depends(get_db)):
    rows = calcular(data, db)
    try:
        ids = persist_cuts(db, rows)
        db.commit()
    except ValueError as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error
    return {'version': VERSION, 'total': len(ids), 'ids': ids, 'predicciones_generadas': 0}
