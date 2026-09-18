"""Asistencia diaria por curso. Las lecturas no crean jornadas ni faltas."""
import hashlib
import json
from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from database import get_db
from api.auth import get_current_user
from api.escolar import Entrada, obtener, fila
import models as m

router=APIRouter(prefix='/asistencia',tags=['Asistencia diaria'])

def personal(user=Depends(get_current_user)):
    if user.rol not in ('Admin','Director','Docente'):
        raise HTTPException(403,'Tu rol no permite acceder a la asistencia.')
    return user

def autorizacion(db,user,curso_id,fecha,lock=False):
    course=obtener(db,m.Curso,curso_id)
    gestion=obtener(db,m.Gestion,course.gestion_id,lock)
    if lock:
        course=obtener(db,m.Curso,curso_id,True)
    if user.rol=='Docente':
        stmt=select(m.AsignacionDocente.id).where(m.AsignacionDocente.curso_id==curso_id,m.AsignacionDocente.docente_id==user.id,m.AsignacionDocente.vigente_desde<=fecha,or_(m.AsignacionDocente.vigente_hasta==None,m.AsignacionDocente.vigente_hasta>=fecha)).limit(1)
        assignment=db.scalar(stmt.with_for_update() if lock else stmt)
        if not assignment:
            raise HTTPException(403,'No tienes una asignación vigente para este curso en la fecha seleccionada.')
    if not gestion.fecha_inicio or not gestion.fecha_fin:
        raise HTTPException(422,'Dirección debe completar el calendario de la gestión antes de registrar asistencia.')
    if not gestion.fecha_inicio<=fecha<=gestion.fecha_fin:
        raise HTTPException(422,'La fecha debe pertenecer al calendario de la gestión.')
    return course,gestion

def resumen(db,course,gestion,fecha,lock=False):
    def read(stmt):return stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt
    jornada=db.scalar(read(select(m.JornadaClase).where(m.JornadaClase.curso_id==course.id,m.JornadaClase.fecha==fecha)))
    rows=db.execute(read(select(m.Matricula,m.Estudiante).join(m.Estudiante,m.Estudiante.id==m.Matricula.estudiante_id).where(m.Matricula.curso_id==course.id,m.Matricula.fecha_ingreso<=fecha,or_(m.Matricula.fecha_fin==None,m.Matricula.fecha_fin>=fecha)).order_by(m.Estudiante.apellido,m.Estudiante.nombre,m.Matricula.id))).all()
    stored=list(db.scalars(read(select(m.Asistencia).where(m.Asistencia.jornada_id==jornada.id)))) if jornada else []
    by_id={x.matricula_id:x for x in stored}
    roster=[{'matricula_id':e.id,'nombre':s.nombre,'apellido':s.apellido,'origen':e.origen,
             'estado':by_id[e.id].estado if e.id in by_id else None,
             'justificada':by_id[e.id].justificada if e.id in by_id else None,
             'observacion':by_id[e.id].observacion if e.id in by_id else None,
             'registrado_en':by_id[e.id].registrado_en if e.id in by_id else None} for e,s in rows]
    digest={'jornada':fila(jornada) if jornada else None,'lista':roster,'registros':[fila(x) for x in sorted(stored,key=lambda x:x.id)]}
    version=hashlib.sha256(json.dumps(jsonable_encoder(digest),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'curso_id':course.id,'curso':f'{course.grado}° {course.paralelo}','gestion':gestion.anio,'fecha':fecha,
            'es_lectiva':jornada.es_lectiva if jornada else True,'motivo_no_lectiva':jornada.motivo_no_lectiva if jornada else None,
            'jornada_registrada':jornada is not None,'revision':version,'estudiantes':roster,
            'registros_fuera_lista':len(set(by_id)-{e.id for e,s in rows})}

class RegistroEntrada(Entrada):
    matricula_id:int=Field(gt=0)
    estado:Literal['PRESENTE','FALTA','ATRASO','LICENCIA']|None=None
    justificada:bool|None=None
    observacion:str|None=Field(default=None,max_length=500)

    @model_validator(mode='after')
    def coherencia(self):
        if self.estado in (None,'PRESENTE') and self.justificada is not None:
            raise ValueError('La justificación solo corresponde a falta, atraso o licencia.')
        if self.estado is None and self.observacion:
            raise ValueError('Selecciona un estado antes de guardar una observación.')
        return self

class ListaEntrada(Entrada):
    revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    es_lectiva:bool=True
    motivo_no_lectiva:str|None=Field(default=None,max_length=200)
    motivo_correccion:str|None=Field(default=None,max_length=500)
    estudiantes:list[RegistroEntrada]=Field(max_length=2000)

    @model_validator(mode='after')
    def coherencia(self):
        ids=[x.matricula_id for x in self.estudiantes]
        if len(ids)!=len(set(ids)):raise ValueError('Hay estudiantes repetidos en la lista.')
        if not self.es_lectiva and not self.motivo_no_lectiva:
            raise ValueError('Indica el motivo del día sin clases.')
        if not self.es_lectiva and any(x.estado for x in self.estudiantes):
            raise ValueError('Un día sin clases no puede contener asistencias.')
        return self

@router.get('/cursos')
def cursos(db:Session=Depends(get_db),user=Depends(personal)):
    stmt=select(m.Curso,m.Gestion).join(m.Gestion,m.Gestion.id==m.Curso.gestion_id)
    if user.rol=='Docente':
        stmt=stmt.where(m.Curso.id.in_(select(m.AsignacionDocente.curso_id).where(m.AsignacionDocente.docente_id==user.id)))
    return [{'id':c.id,'nombre':f'{g.anio} · {c.grado}° {c.paralelo}','fecha_inicio':g.fecha_inicio,'fecha_fin':g.fecha_fin} for c,g in db.execute(stmt.order_by(m.Gestion.anio.desc(),m.Curso.grado,m.Curso.paralelo))]

@router.get('/{curso_id}/{fecha}')
def consultar(curso_id:int,fecha:date,db:Session=Depends(get_db),user=Depends(personal)):
    course,gestion=autorizacion(db,user,curso_id,fecha)
    return resumen(db,course,gestion,fecha)

def auditar(db,obj,user,antes,motivo):
    db.flush()
    db.add(m.AuditoriaCambio(usuario_id=user.id,tabla_afectada=obj.__tablename__,registro_id=obj.id,
        operacion='ALTA' if antes is None else 'CORRECCION',antes=jsonable_encoder(antes),despues=jsonable_encoder(fila(obj)),motivo=motivo))

@router.put('/{curso_id}/{fecha}')
def guardar(curso_id:int,fecha:date,data:ListaEntrada,db:Session=Depends(get_db),user=Depends(personal)):
    if fecha>date.today():raise HTTPException(422,'No se puede registrar asistencia de una fecha futura.')
    course,gestion=autorizacion(db,user,curso_id,fecha,True)
    actual=resumen(db,course,gestion,fecha,True)
    if actual['revision']!=data.revision:
        raise HTTPException(409,'La lista cambió desde que la abriste. Vuelve a cargarla antes de guardar.')
    if actual['registros_fuera_lista']:
        raise HTTPException(409,'Existen asistencias fuera de la matrícula vigente. Dirección debe revisar el historial.')
    expected={x['matricula_id'] for x in actual['estudiantes']}
    if {x.matricula_id for x in data.estudiantes}!=expected:
        raise HTTPException(422,'La lista no coincide con las matrículas vigentes del curso y fecha.')
    jornada=db.scalar(select(m.JornadaClase).where(m.JornadaClase.curso_id==curso_id,m.JornadaClase.fecha==fecha).with_for_update())
    records={x.matricula_id:x for x in db.scalars(select(m.Asistencia).where(m.Asistencia.jornada_id==jornada.id).with_for_update())} if jornada else {}
    if user.rol=='Docente' and (not data.es_lectiva or (jornada and not jornada.es_lectiva)):
        raise HTTPException(403,'Solo dirección o administración puede modificar días sin clases.')
    if not data.es_lectiva and records:
        raise HTTPException(409,'Ya hay asistencia registrada. No se puede convertir el día en no lectivo sin revisar el historial.')
    changes=[]
    for item in data.estudiantes:
        old=records.get(item.matricula_id)
        if old and item.estado is None:
            raise HTTPException(422,'Una asistencia guardada no puede volver a sin registro. Corrige su estado.')
        if item.estado and (old is None or any(getattr(old,k)!=getattr(item,k) for k in ('estado','justificada','observacion'))):
            changes.append((item,old))
    day_changed=jornada and (jornada.es_lectiva!=data.es_lectiva or jornada.motivo_no_lectiva!=(None if data.es_lectiva else data.motivo_no_lectiva))
    if (day_changed or any(old for item,old in changes)) and not data.motivo_correccion:
        raise HTTPException(422,'Indica un motivo para corregir registros guardados.')
    if not jornada and data.es_lectiva and not any(x.estado for x in data.estudiantes):
        raise HTTPException(422,'Marca al menos un estudiante antes de guardar la lista.')
    reason=data.motivo_correccion or 'Registro de asistencia diaria'
    if jornada is None:
        jornada=m.JornadaClase(curso_id=curso_id,fecha=fecha,es_lectiva=data.es_lectiva,motivo_no_lectiva=None if data.es_lectiva else data.motivo_no_lectiva)
        db.add(jornada);auditar(db,jornada,user,None,reason)
    elif day_changed:
        before=fila(jornada);jornada.es_lectiva=data.es_lectiva;jornada.motivo_no_lectiva=None if data.es_lectiva else data.motivo_no_lectiva
        auditar(db,jornada,user,before,reason)
    for item,old in changes:
        before=fila(old) if old else None
        obj=old or m.Asistencia(matricula_id=item.matricula_id,jornada_id=jornada.id,curso_id=curso_id)
        obj.estado=item.estado;obj.justificada=item.justificada;obj.observacion=item.observacion
        obj.registrado_por=user.id;obj.registrado_en=datetime.now()
        db.add(obj);auditar(db,obj,user,before,reason)
    db.commit()
    return resumen(db,course,gestion,fecha)
