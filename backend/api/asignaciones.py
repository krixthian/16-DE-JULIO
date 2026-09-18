"""Catálogo de materias y responsables por curso, con historial de vigencia."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import get_db
from api.escolar import Entrada, encargado, obtener, guardar, fila, aplicar
import models as m

router=APIRouter(prefix='/escolar',tags=['Materias y asignaciones'],dependencies=[Depends(encargado)])

class MateriaEntrada(Entrada):
    nombre:str=Field(min_length=1,max_length=120)
    sigla:str|None=Field(default=None,min_length=1,max_length=20)

class AsignacionEntrada(Entrada):
    curso_id:int=Field(gt=0)
    materia_id:int=Field(gt=0)
    docente_id:int=Field(gt=0)
    vigente_desde:date
    vigente_hasta:date|None=None

    @model_validator(mode='after')
    def fechas(self):
        if self.vigente_hasta and self.vigente_hasta < self.vigente_desde:
            raise ValueError('La fecha final no puede ser anterior al inicio.')
        return self

@router.get('/materias')
def listar_materias(db:Session=Depends(get_db)):
    return [fila(x) for x in db.scalars(select(m.Materia).order_by(m.Materia.nombre))]

@router.post('/materias',status_code=201)
def crear_materia(data:MateriaEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    return guardar(db,m.Materia(**data.model_dump()),user)

@router.put('/materias/{id}')
def editar_materia(id:int,data:MateriaEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    obj=obtener(db,m.Materia,id,True)
    antes=fila(obj);aplicar(obj,data)
    return guardar(db,obj,user,antes)

@router.get('/asignaciones')
def listar_asignaciones(db:Session=Depends(get_db)):
    rows=db.execute(select(m.AsignacionDocente,m.Materia.nombre,m.Usuario.nombre,m.Usuario.apellido,m.Usuario.activo,m.Curso.grado,m.Curso.paralelo,m.Gestion.anio,m.Gestion.fecha_fin).join(m.Materia,m.Materia.id==m.AsignacionDocente.materia_id).join(m.Usuario,m.Usuario.id==m.AsignacionDocente.docente_id).join(m.Curso,m.Curso.id==m.AsignacionDocente.curso_id).join(m.Gestion,m.Gestion.id==m.Curso.gestion_id).order_by(m.Gestion.anio.desc(),m.Curso.grado,m.Curso.paralelo,m.Materia.nombre,m.AsignacionDocente.vigente_desde.desc()))
    today=date.today()
    return [{**fila(a),'materia_nombre':mn,'docente_nombre':f'{n} {s}','docente_activo':active,'curso_nombre':f'{g}° {p}','gestion_anio':year,
             'estado':'PROGRAMADA' if a.vigente_desde>today else ('FINALIZADA' if (a.vigente_hasta or end) and (a.vigente_hasta or end)<today else 'VIGENTE')} for a,mn,n,s,active,g,p,year,end in rows]

def validar(db,data,id=None):
    course=obtener(db,m.Curso,data.curso_id)
    gestion=obtener(db,m.Gestion,course.gestion_id,True)
    obtener(db,m.Materia,data.materia_id,True)
    teacher=obtener(db,m.Usuario,data.docente_id,True)
    if teacher.rol!='Docente' or not teacher.activo:
        # An inactive teacher may only have an existing segment closed/corrected, never be newly assigned.
        old=obtener(db,m.AsignacionDocente,id) if id else None
        if not old or (old.curso_id,old.materia_id,old.docente_id,old.vigente_desde)!=(data.curso_id,data.materia_id,data.docente_id,data.vigente_desde) or not data.vigente_hasta or data.vigente_hasta>date.today() or (old.vigente_hasta and data.vigente_hasta>old.vigente_hasta):
            raise HTTPException(422,'Selecciona un docente activo. Para un docente inactivo solo se permite cerrar su asignación existente.')
    if not gestion.fecha_inicio or not gestion.fecha_fin:
        raise HTTPException(422,'Completa las fechas de la gestión antes de asignar docentes.')
    end=data.vigente_hasta or gestion.fecha_fin
    if not gestion.fecha_inicio<=data.vigente_desde<=end<=gestion.fecha_fin:
        raise HTTPException(422,'La vigencia debe estar dentro del calendario de la gestión.')
    conflict=db.scalar(select(m.AsignacionDocente.id).where(m.AsignacionDocente.curso_id==data.curso_id,m.AsignacionDocente.materia_id==data.materia_id,m.AsignacionDocente.id!=(id or 0),m.AsignacionDocente.vigente_desde<=end,func.coalesce(m.AsignacionDocente.vigente_hasta,gestion.fecha_fin)>=data.vigente_desde).with_for_update().limit(1))
    if conflict:
        raise HTTPException(409,'La materia ya tiene un docente asignado en ese curso durante estas fechas. Finaliza la asignación anterior antes de registrar el reemplazo.')
    return end

@router.post('/asignaciones',status_code=201)
def crear_asignacion(data:AsignacionEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    validar(db,data)
    return guardar(db,m.AsignacionDocente(**data.model_dump()),user)

@router.put('/asignaciones/{id}')
def editar_asignacion(id:int,data:AsignacionEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    end=validar(db,data,id)
    obj=obtener(db,m.AsignacionDocente,id,True)
    # Preserve teacher/subject ownership of already recorded schoolwork.
    evaluations=list(db.scalars(select(m.Evaluacion).where(m.Evaluacion.asignacion_id==id)))
    tasks=list(db.scalars(select(m.Tarea).where(m.Tarea.asignacion_id==id)))
    if evaluations or tasks:
        if (obj.curso_id,obj.materia_id,obj.docente_id)!=(data.curso_id,data.materia_id,data.docente_id):
            raise HTTPException(409,'La asignación tiene actividades. Conserva su docente, curso y materia y registra un nuevo segmento para el reemplazo.')
        if any(not data.vigente_desde<=e.fecha_aplicacion<=end for e in evaluations) or any(not data.vigente_desde<=t.fecha_asignacion.date()<=t.fecha_limite.date()<=end for t in tasks):
            raise HTTPException(409,'La vigencia dejaría actividades registradas fuera de la asignación.')
    antes=fila(obj);aplicar(obj,data)
    return guardar(db,obj,user,antes)
