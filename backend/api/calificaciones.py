"""Evaluaciones parciales, trimestres y notas con permisos y auditoría."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from database import get_db
from api.auth import get_current_user
from api.escolar import Entrada, obtener, fila, guardar as persistir, aplicar, encargado
from api.asistencia import auditar
import models as m

router=APIRouter(prefix='/calificaciones',tags=['Calificaciones'])

def personal(user=Depends(get_current_user)):
    if user.rol not in ('Admin','Director','Docente'):
        raise HTTPException(403,'Tu rol no permite acceder a calificaciones.')
    return user

def revision(value):
    return hashlib.sha256(json.dumps(jsonable_encoder(value),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def assignment(db,user,id,lock=False):
    obj=obtener(db,m.AsignacionDocente,id)
    if user.rol=='Docente' and obj.docente_id!=user.id:
        raise HTTPException(403,'No tienes acceso a esta asignación docente.')
    curso=obtener(db,m.Curso,obj.curso_id)
    gestion=obtener(db,m.Gestion,curso.gestion_id,lock)
    if lock:
        obj=db.scalar(select(m.AsignacionDocente).where(m.AsignacionDocente.id==id).with_for_update().execution_options(populate_existing=True))
        if user.rol=='Docente' and obj.docente_id!=user.id:
            raise HTTPException(403,'La asignación docente cambió. Vuelve a consultar.')
        if obj.curso_id!=curso.id:
            raise HTTPException(409,'El curso cambió. Vuelve a consultar la asignación.')
    return obj,curso,gestion

def evaluation(db,user,id,lock=False):
    obj=obtener(db,m.Evaluacion,id)
    a,c,g=assignment(db,user,obj.asignacion_id,lock)
    if lock:
        obj=db.scalar(select(m.Evaluacion).where(m.Evaluacion.id==id).with_for_update().execution_options(populate_existing=True))
    return obj,a,c,g

class PeriodoEntrada(Entrada):
    gestion_id:int=Field(gt=0)
    numero:int=Field(ge=1,le=3)
    fecha_inicio:date
    fecha_fin:date
    @model_validator(mode='after')
    def fechas(self):
        if self.fecha_fin<self.fecha_inicio:raise ValueError('El fin del trimestre no puede ser anterior al inicio.')
        return self

def validar_periodo(db,data,id=None):
    g=obtener(db,m.Gestion,data.gestion_id,True)
    if not g.fecha_inicio or not g.fecha_fin:raise HTTPException(422,'Completa el calendario de la gestión.')
    if not g.fecha_inicio<=data.fecha_inicio<=data.fecha_fin<=g.fecha_fin:
        raise HTTPException(422,'El trimestre debe estar dentro de la gestión.')
    for p in db.scalars(select(m.Periodo).where(m.Periodo.gestion_id==g.id,m.Periodo.id!=(id or 0)).with_for_update()):
        if p.numero==data.numero:raise HTTPException(409,'Ese trimestre ya existe. Utiliza Editar.')
        if p.fecha_inicio and p.fecha_fin:
            if (p.numero<data.numero and p.fecha_fin>=data.fecha_inicio) or (p.numero>data.numero and p.fecha_inicio<=data.fecha_fin):
                raise HTTPException(409,'Los trimestres deben estar ordenados y no solaparse.')

@router.post('/periodos',status_code=201)
def crear_periodo(data:PeriodoEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    validar_periodo(db,data)
    return persistir(db,m.Periodo(**data.model_dump()),user)

@router.put('/periodos/{id}')
def editar_periodo(id:int,data:PeriodoEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    validar_periodo(db,data,id)
    obj=obtener(db,m.Periodo,id,True)
    if obj.gestion_id!=data.gestion_id or obj.numero!=data.numero:
        raise HTTPException(409,'Conserva la gestión y el número del trimestre; puedes corregir sus fechas.')
    if db.scalar(select(m.Evaluacion.id).where(m.Evaluacion.periodo_id==id,or_(m.Evaluacion.fecha_aplicacion<data.fecha_inicio,m.Evaluacion.fecha_aplicacion>data.fecha_fin)).with_for_update().limit(1)):
        raise HTTPException(409,'Las fechas dejarían una evaluación fuera del trimestre.')
    antes=fila(obj);aplicar(obj,data)
    return persistir(db,obj,user,antes)

@router.get('/contexto')
def contexto(db:Session=Depends(get_db),user=Depends(personal)):
    stmt=select(m.AsignacionDocente,m.Curso,m.Gestion,m.Materia,m.Usuario).join(m.Curso,m.Curso.id==m.AsignacionDocente.curso_id).join(m.Gestion,m.Gestion.id==m.Curso.gestion_id).join(m.Materia,m.Materia.id==m.AsignacionDocente.materia_id).join(m.Usuario,m.Usuario.id==m.AsignacionDocente.docente_id)
    if user.rol=='Docente':stmt=stmt.where(m.AsignacionDocente.docente_id==user.id)
    assignments=[{**fila(a),'gestion_id':g.id,'gestion_anio':g.anio,'curso_nombre':f'{c.grado}° {c.paralelo}','materia_nombre':s.nombre,'docente_nombre':f'{u.nombre} {u.apellido}'} for a,c,g,s,u in db.execute(stmt.order_by(m.Gestion.anio.desc(),m.Curso.grado,m.Curso.paralelo,m.Materia.nombre))]
    years=select(m.Gestion).order_by(m.Gestion.anio.desc())
    periods=select(m.Periodo).order_by(m.Periodo.gestion_id,m.Periodo.numero)
    if user.rol=='Docente':
        ids={a['gestion_id'] for a in assignments};years=years.where(m.Gestion.id.in_(ids));periods=periods.where(m.Periodo.gestion_id.in_(ids))
    return {'asignaciones':assignments,'gestiones':[fila(g) for g in db.scalars(years)],'periodos':[fila(p) for p in db.scalars(periods)]}

class EvaluacionEntrada(Entrada):
    asignacion_id:int=Field(gt=0)
    periodo_id:int=Field(gt=0)
    titulo:str=Field(min_length=1,max_length=160)
    tipo:Literal['PRUEBA','TRABAJO','PROYECTO','ORAL','OTRA']
    fecha_aplicacion:date
    puntaje_maximo:Decimal=Field(gt=0,max_digits=8,decimal_places=2)
    dimension:str|None=Field(default=None,min_length=1,max_length=60)

class EvaluacionEdicion(EvaluacionEntrada):
    revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    motivo_correccion:str=Field(min_length=1,max_length=500)

def validar_evaluacion(db,user,data):
    a,c,g=assignment(db,user,data.asignacion_id,True)
    p=obtener(db,m.Periodo,data.periodo_id,True)
    if not g.fecha_inicio or not g.fecha_fin or not p.fecha_inicio or not p.fecha_fin:
        raise HTTPException(422,'Completa el calendario y las fechas del trimestre.')
    if p.gestion_id!=g.id:raise HTTPException(422,'El trimestre no pertenece a la gestión del curso.')
    if not g.fecha_inicio<=p.fecha_inicio<=data.fecha_aplicacion<=p.fecha_fin<=g.fecha_fin:
        raise HTTPException(422,'La fecha de evaluación debe estar dentro del trimestre y de la gestión.')
    if not a.vigente_desde<=data.fecha_aplicacion<=(a.vigente_hasta or g.fecha_fin):
        raise HTTPException(422,'La evaluación debe estar dentro de la vigencia de la asignación docente.')
    return a,c,g

def evaluacion_salida(obj):
    data=fila(obj)
    return {**data,'revision':revision(data)}

@router.get('/evaluaciones')
def listar_evaluaciones(asignacion_id:int,db:Session=Depends(get_db),user=Depends(personal)):
    assignment(db,user,asignacion_id)
    return [evaluacion_salida(e) for e in db.scalars(select(m.Evaluacion).where(m.Evaluacion.asignacion_id==asignacion_id).order_by(m.Evaluacion.fecha_aplicacion.desc(),m.Evaluacion.id.desc()))]

@router.post('/evaluaciones',status_code=201)
def crear_evaluacion(data:EvaluacionEntrada,db:Session=Depends(get_db),user=Depends(personal)):
    a,c,g=validar_evaluacion(db,user,data)
    obj=m.Evaluacion(**data.model_dump(),curso_id=c.id,gestion_id=g.id)
    persistir(db,obj,user)
    return evaluacion_salida(obj)

@router.put('/evaluaciones/{id}')
def editar_evaluacion(id:int,data:EvaluacionEdicion,db:Session=Depends(get_db),user=Depends(personal)):
    obj,a,c,g=evaluation(db,user,id,True)
    if data.asignacion_id!=obj.asignacion_id:raise HTTPException(409,'La evaluación no puede trasladarse a otra asignación.')
    if data.revision!=revision(fila(obj)):raise HTTPException(409,'La evaluación cambió. Vuelve a cargarla.')
    validar_evaluacion(db,user,data)
    linked=db.scalar(select(m.Calificacion.id).where(m.Calificacion.evaluacion_id==id).with_for_update().limit(1)) or db.scalar(select(m.Tarea.id).where(m.Tarea.evaluacion_id==id).with_for_update().limit(1))
    if linked and any(getattr(obj,k)!=getattr(data,k) for k in ('fecha_aplicacion','periodo_id','puntaje_maximo','dimension')):
        raise HTTPException(409,'La evaluación ya tiene notas o tareas. Conserva su fecha, trimestre, escala y dimensión para proteger el historial.')
    before=fila(obj)
    for k,v in data.model_dump(exclude={'revision','motivo_correccion'}).items():setattr(obj,k,v)
    auditar(db,obj,user,before,data.motivo_correccion);db.commit();db.refresh(obj)
    return evaluacion_salida(obj)

def lista(db,e,lock=False):
    def read(stmt):return stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt
    members=list(db.execute(read(select(m.Matricula,m.Estudiante).join(m.Estudiante,m.Estudiante.id==m.Matricula.estudiante_id).where(m.Matricula.curso_id==e.curso_id,m.Matricula.fecha_ingreso<=e.fecha_aplicacion,or_(m.Matricula.fecha_fin==None,m.Matricula.fecha_fin>=e.fecha_aplicacion)).order_by(m.Estudiante.apellido,m.Estudiante.nombre,m.Matricula.id))))
    notes=list(db.scalars(read(select(m.Calificacion).where(m.Calificacion.evaluacion_id==e.id).order_by(m.Calificacion.id))))
    by_id={x.matricula_id:x for x in notes}
    rows=[{'matricula_id':mat.id,'nombre':s.nombre,'apellido':s.apellido,'origen':mat.origen,'estado':by_id[mat.id].estado if mat.id in by_id else None,'puntaje':by_id[mat.id].puntaje if mat.id in by_id else None,'registrado_en':by_id[mat.id].registrado_en if mat.id in by_id else None} for mat,s in members]
    return {'evaluacion':evaluacion_salida(e),'revision':revision({'evaluacion':fila(e),'lista':rows,'notas':[fila(n) for n in notes]}),'estudiantes':rows,'registros_fuera_lista':len(set(by_id)-{mat.id for mat,s in members})}

class NotaEntrada(Entrada):
    matricula_id:int=Field(gt=0)
    estado:Literal['CALIFICADA','PENDIENTE','NO_PRESENTADA','EXENTA']|None=None
    puntaje:Annotated[Decimal,Field(ge=0,max_digits=8,decimal_places=2)]|None=None
    @model_validator(mode='after')
    def coherencia(self):
        if self.estado=='CALIFICADA' and self.puntaje is None:raise ValueError('Una evaluación calificada requiere puntaje, incluso si es cero.')
        if self.estado!='CALIFICADA' and self.puntaje is not None:raise ValueError('Solo las evaluaciones calificadas pueden tener puntaje.')
        return self

class NotasEntrada(Entrada):
    revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    motivo_correccion:str|None=Field(default=None,min_length=1,max_length=500)
    estudiantes:list[NotaEntrada]=Field(max_length=2000)
    @model_validator(mode='after')
    def duplicates(self):
        ids=[x.matricula_id for x in self.estudiantes]
        if len(ids)!=len(set(ids)):raise ValueError('Hay matrículas repetidas en la lista.')
        return self

@router.get('/evaluaciones/{id}/notas')
def consultar_notas(id:int,db:Session=Depends(get_db),user=Depends(personal)):
    e,a,c,g=evaluation(db,user,id)
    return lista(db,e)

@router.put('/evaluaciones/{id}/notas')
def guardar_notas(id:int,data:NotasEntrada,db:Session=Depends(get_db),user=Depends(personal)):
    e,a,c,g=evaluation(db,user,id,True)
    if e.fecha_aplicacion>date.today():raise HTTPException(422,'No se pueden registrar notas de una evaluación futura.')
    # Recheck dates in case the calendar or assignment was corrected elsewhere.
    validar_evaluacion(db,user,EvaluacionEntrada(**{k:getattr(e,k) for k in EvaluacionEntrada.model_fields}))
    actual=lista(db,e,True)
    if actual['revision']!=data.revision:raise HTTPException(409,'La lista cambió. Recárgala antes de guardar para no sobrescribir otras notas.')
    if actual['registros_fuera_lista']:raise HTTPException(409,'Hay notas fuera de la matrícula vigente. Dirección debe revisar el historial.')
    if {x.matricula_id for x in data.estudiantes}!={x['matricula_id'] for x in actual['estudiantes']}:
        raise HTTPException(422,'La lista no coincide con las matrículas vigentes en la fecha de evaluación.')
    existing={n.matricula_id:n for n in db.scalars(select(m.Calificacion).where(m.Calificacion.evaluacion_id==id).with_for_update())}
    changes=[]
    for item in data.estudiantes:
        old=existing.get(item.matricula_id)
        if item.puntaje is not None and item.puntaje>e.puntaje_maximo:raise HTTPException(422,'Un puntaje supera el máximo de la evaluación.')
        if old and item.estado is None:raise HTTPException(422,'Una nota guardada no puede borrarse. Corrige su estado e indica el motivo.')
        if item.estado is not None and (old is None or old.estado!=item.estado or old.puntaje!=item.puntaje):changes.append((item,old))
    if not existing and not changes:raise HTTPException(422,'Registra al menos un estado o una nota antes de guardar.')
    if any(old for item,old in changes) and not data.motivo_correccion:raise HTTPException(422,'Indica el motivo para corregir notas ya guardadas.')
    for item,old in changes:
        before=fila(old) if old else None
        obj=old or m.Calificacion(evaluacion_id=id,matricula_id=item.matricula_id,curso_id=e.curso_id)
        obj.estado=item.estado;obj.puntaje=item.puntaje;obj.registrado_por=user.id;obj.registrado_en=datetime.now()
        db.add(obj);auditar(db,obj,user,before,data.motivo_correccion or 'Registro de calificaciones parciales')
    db.commit()
    return lista(db,e)
