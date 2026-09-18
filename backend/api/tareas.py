"""Tareas y entregas por matrícula, sin convertir ausencia de registro en incumplimiento."""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from database import get_db
from api.escolar import Entrada, obtener, fila
from api.asistencia import auditar
from api.calificaciones import personal, assignment, contexto, revision
import models as m

router=APIRouter(prefix='/tareas',tags=['Seguimiento de tareas'])
router.add_api_route('/contexto',contexto,methods=['GET'])

class TareaEntrada(Entrada):
    asignacion_id:int=Field(gt=0)
    titulo:str=Field(min_length=1,max_length=160)
    fecha_asignacion:datetime
    fecha_limite:datetime
    evaluacion_id:int|None=Field(default=None,gt=0)
    @model_validator(mode='after')
    def fechas(self):
        if self.fecha_asignacion.tzinfo or self.fecha_limite.tzinfo:
            raise ValueError('Usa fecha y hora local del colegio, sin zona horaria.')
        if self.fecha_limite<self.fecha_asignacion:raise ValueError('El plazo no puede preceder a la asignación.')
        return self

class Edicion(TareaEntrada):
    revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    motivo_correccion:str=Field(min_length=1,max_length=500)

def validar(db,user,data):
    a,c,g=assignment(db,user,data.asignacion_id,True)
    if not g.fecha_inicio or not g.fecha_fin:raise HTTPException(422,'Completa el calendario de la gestión.')
    if not g.fecha_inicio<=data.fecha_asignacion.date()<=data.fecha_limite.date()<=g.fecha_fin:
        raise HTTPException(422,'Las fechas deben estar dentro de la gestión.')
    if not a.vigente_desde<=data.fecha_asignacion.date()<=data.fecha_limite.date()<=(a.vigente_hasta or g.fecha_fin):
        raise HTTPException(422,'Las fechas deben estar dentro de la asignación docente.')
    if data.evaluacion_id:
        e=obtener(db,m.Evaluacion,data.evaluacion_id,True)
        if e.asignacion_id!=a.id:raise HTTPException(422,'La evaluación debe pertenecer a la misma asignación.')
    return a,c,g

def salida(t):
    data=fila(t)
    return {**data,'revision':revision(data)}

def acceso(db,user,id,lock=False):
    t=obtener(db,m.Tarea,id)
    assignment(db,user,t.asignacion_id,lock)
    if lock:t=obtener(db,m.Tarea,id,True)
    return t

@router.get('')
def listar(asignacion_id:int,db:Session=Depends(get_db),user=Depends(personal)):
    assignment(db,user,asignacion_id)
    return [salida(t) for t in db.scalars(select(m.Tarea).where(m.Tarea.asignacion_id==asignacion_id).order_by(m.Tarea.fecha_asignacion.desc(),m.Tarea.id.desc()))]

@router.post('',status_code=201)
def crear(data:TareaEntrada,db:Session=Depends(get_db),user=Depends(personal)):
    a,c,g=validar(db,user,data)
    t=m.Tarea(**data.model_dump(),curso_id=c.id)
    db.add(t);auditar(db,t,user,None,'Creación de tarea');db.commit();db.refresh(t)
    return salida(t)

@router.put('/{id}')
def editar(id:int,data:Edicion,db:Session=Depends(get_db),user=Depends(personal)):
    t=acceso(db,user,id,True)
    if data.asignacion_id!=t.asignacion_id:raise HTTPException(409,'No se puede trasladar la tarea a otra asignación.')
    if data.revision!=revision(fila(t)):raise HTTPException(409,'La tarea cambió. Vuelve a consultarla.')
    validar(db,user,data)
    linked=db.scalar(select(m.EntregaTarea.id).where(m.EntregaTarea.tarea_id==id).with_for_update().limit(1))
    if linked and any(getattr(t,k)!=getattr(data,k) for k in ('fecha_asignacion','fecha_limite','evaluacion_id')):
        raise HTTPException(409,'Con entregas registradas se conserva fecha, plazo y evaluación para proteger el historial.')
    before=fila(t)
    for k,v in data.model_dump(exclude={'revision','motivo_correccion'}).items():setattr(t,k,v)
    auditar(db,t,user,before,data.motivo_correccion);db.commit();db.refresh(t)
    return salida(t)

def lista(db,t,lock=False):
    def read(q):return q.with_for_update().execution_options(populate_existing=True) if lock else q
    day=t.fecha_asignacion.date()
    members=db.execute(read(select(m.Matricula,m.Estudiante).join(m.Estudiante,m.Estudiante.id==m.Matricula.estudiante_id).where(m.Matricula.curso_id==t.curso_id,m.Matricula.fecha_ingreso<=day,or_(m.Matricula.fecha_fin==None,m.Matricula.fecha_fin>=day)).order_by(m.Estudiante.apellido,m.Estudiante.nombre,m.Matricula.id))).all()
    stored=list(db.scalars(read(select(m.EntregaTarea).where(m.EntregaTarea.tarea_id==t.id).order_by(m.EntregaTarea.id))))
    by_id={e.matricula_id:e for e in stored}
    rows=[]
    for mat,s in members:
        e=by_id.get(mat.id)
        rows.append({'matricula_id':mat.id,'nombre':s.nombre,'apellido':s.apellido,'origen':mat.origen,
          'estado':e.estado if e else None,'fecha_entrega':e.fecha_entrega if e else None,
          'fuera_plazo':bool(e and e.fecha_entrega and e.fecha_entrega>t.fecha_limite),
          'registrado_en':e.registrado_en if e else None})
    return {'tarea':salida(t),'estudiantes':rows,'registros_fuera_lista':len(set(by_id)-{mat.id for mat,s in members}),
            'revision':revision({'tarea':fila(t),'lista':rows,'entregas':[fila(e) for e in stored]})}

class Entrega(Entrada):
    matricula_id:int=Field(gt=0)
    estado:Literal['PENDIENTE','ENTREGADA','NO_ENTREGADA','EXENTA']|None=None
    fecha_entrega:datetime|None=None
    @model_validator(mode='after')
    def coherencia(self):
        if (self.estado=='ENTREGADA')!=(self.fecha_entrega is not None):
            raise ValueError('Solo una tarea entregada requiere fecha de entrega.')
        if self.fecha_entrega and self.fecha_entrega.tzinfo:raise ValueError('Usa fecha y hora local del colegio.')
        return self

class Entregas(Entrada):
    revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    motivo_correccion:str|None=Field(default=None,min_length=1,max_length=500)
    estudiantes:list[Entrega]=Field(max_length=2000)
    @model_validator(mode='after')
    def unicos(self):
        ids=[x.matricula_id for x in self.estudiantes]
        if len(ids)!=len(set(ids)):raise ValueError('Hay matrículas repetidas.')
        return self

@router.get('/{id}/entregas')
def consultar(id:int,db:Session=Depends(get_db),user=Depends(personal)):
    return lista(db,acceso(db,user,id))

@router.put('/{id}/entregas')
def guardar(id:int,data:Entregas,db:Session=Depends(get_db),user=Depends(personal)):
    t=acceso(db,user,id,True)
    validar(db,user,TareaEntrada(**{k:getattr(t,k) for k in TareaEntrada.model_fields}))
    now=datetime.now()
    if t.fecha_asignacion>now:raise HTTPException(422,'La tarea todavía no ha sido asignada.')
    current=lista(db,t,True)
    if current['revision']!=data.revision:raise HTTPException(409,'La lista cambió. Vuelve a consultarla.')
    if current['registros_fuera_lista']:raise HTTPException(409,'Dirección debe revisar entregas fuera de la matrícula vigente.')
    if {x.matricula_id for x in data.estudiantes}!={x['matricula_id'] for x in current['estudiantes']}:
        raise HTTPException(422,'La lista debe coincidir con las matrículas de la fecha de asignación.')
    old={e.matricula_id:e for e in db.scalars(select(m.EntregaTarea).where(m.EntregaTarea.tarea_id==id).with_for_update())}
    changes=[]
    for x in data.estudiantes:
        e=old.get(x.matricula_id)
        if x.fecha_entrega and not t.fecha_asignacion<=x.fecha_entrega<=now:
            raise HTTPException(422,'La entrega debe estar entre la asignación y el momento actual.')
        if x.estado=='NO_ENTREGADA' and now<=t.fecha_limite:raise HTTPException(422,'El plazo aún no terminó. Utiliza Pendiente.')
        if e and x.estado is None:raise HTTPException(422,'No se puede borrar un registro guardado; corrige el estado.')
        if x.estado is not None and (not e or e.estado!=x.estado or e.fecha_entrega!=x.fecha_entrega):changes.append((x,e))
    if not old and not changes:raise HTTPException(422,'Registra al menos un estado.')
    if any(e for x,e in changes) and not data.motivo_correccion:raise HTTPException(422,'Indica un motivo de corrección.')
    for x,e in changes:
        before=fila(e) if e else None
        obj=e or m.EntregaTarea(tarea_id=id,matricula_id=x.matricula_id,curso_id=t.curso_id)
        obj.estado=x.estado;obj.fecha_entrega=x.fecha_entrega;obj.registrado_por=user.id;obj.registrado_en=now
        db.add(obj);auditar(db,obj,user,before,data.motivo_correccion or 'Registro de entrega')
    db.commit()
    return lista(db,t)
