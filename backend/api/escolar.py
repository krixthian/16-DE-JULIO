"""Administración escolar. El registro académico se limita a dirección y administración."""
from datetime import date
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_db
from api.auth import get_current_user
import models as m


def encargado(user=Depends(get_current_user)):
    if user.rol not in ('Admin', 'Director'):
        raise HTTPException(403, 'Solo administración y dirección pueden gestionar estos registros.')
    return user


router = APIRouter(prefix='/escolar', tags=['Administración escolar'], dependencies=[Depends(encargado)])


class Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class GestionEntrada(Entrada):
    anio: int = Field(ge=1900, le=2100)
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode='after')
    def fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError('La fecha final debe ser igual o posterior al inicio.')
        if self.fecha_inicio.year != self.anio or self.fecha_fin.year != self.anio:
            raise ValueError('Las fechas deben pertenecer al año de la gestión.')
        return self


class CursoEntrada(Entrada):
    gestion_id: int = Field(gt=0)
    grado: int = Field(ge=1, le=6)
    paralelo: str = Field(min_length=1, max_length=5, pattern=r'^[A-Za-z0-9]+$')
    docente_asesor_id: int | None = Field(default=None, gt=0)


class EstudianteEntrada(Entrada):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    codigo_rude: str | None = Field(default=None, min_length=1, max_length=50)
    fecha_nacimiento: date | None = None

    @model_validator(mode='after')
    def nacimiento(self):
        if self.fecha_nacimiento and self.fecha_nacimiento > date.today():
            raise ValueError('La fecha de nacimiento no puede estar en el futuro.')
        return self


class MatriculaEntrada(Entrada):
    estudiante_id: int = Field(gt=0)
    curso_id: int = Field(gt=0)
    fecha_ingreso: date
    fecha_fin: date | None = None
    origen: Literal['REAL', 'SIMULADO']

    @model_validator(mode='after')
    def fechas(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_ingreso:
            raise ValueError('La fecha final no puede ser anterior al ingreso.')
        return self


def fila(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def obtener(db, model, id, lock=False):
    stmt = select(model).where(model.id == id)
    if lock:
        stmt = stmt.with_for_update()
    obj = db.scalar(stmt)
    if obj is None:
        raise HTTPException(404, 'El registro solicitado no existe.')
    return obj


def guardar(db, obj, user, antes=None):
    try:
        db.add(obj)
        db.flush()
        db.add(m.AuditoriaCambio(usuario_id=user.id, tabla_afectada=obj.__tablename__, registro_id=obj.id,
            operacion='ALTA' if antes is None else 'CORRECCION', antes=jsonable_encoder(antes),
            despues=jsonable_encoder(fila(obj)), motivo='Registro desde administración escolar'))
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Ya existe un registro con esos datos o una relación impide el cambio.')
    return fila(obj)


def aplicar(obj, data):
    for k, v in data.model_dump().items():
        setattr(obj, k, v)


@router.get('/gestiones')
def gestiones(db: Session = Depends(get_db)):
    return [fila(x) for x in db.scalars(select(m.Gestion).order_by(m.Gestion.anio.desc()))]


@router.post('/gestiones', status_code=201)
def crear_gestion(data: GestionEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    return guardar(db, m.Gestion(**data.model_dump()), user)


@router.put('/gestiones/{id}')
def editar_gestion(id: int, data: GestionEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    obj = obtener(db, m.Gestion, id, True)
    if obj.anio != data.anio and db.scalar(select(m.Curso.id).where(m.Curso.gestion_id == id).limit(1)):
        raise HTTPException(409, 'No se puede cambiar el año de una gestión que tiene cursos.')
    for period in db.scalars(select(m.Periodo).where(m.Periodo.gestion_id == id)):
        if period.fecha_inicio and period.fecha_fin and not (data.fecha_inicio <= period.fecha_inicio <= period.fecha_fin <= data.fecha_fin):
            raise HTTPException(409, 'Las fechas dejarían un trimestre fuera de la gestión.')
    for enrollment in db.scalars(select(m.Matricula).join(m.Curso, m.Curso.id == m.Matricula.curso_id).where(m.Curso.gestion_id == id)):
        if not data.fecha_inicio <= enrollment.fecha_ingreso <= (enrollment.fecha_fin or data.fecha_fin) <= data.fecha_fin:
            raise HTTPException(409, 'Las fechas dejarían una matrícula fuera de la gestión.')
    for assignment in db.scalars(select(m.AsignacionDocente).join(m.Curso,m.Curso.id==m.AsignacionDocente.curso_id).where(m.Curso.gestion_id==id)):
        if not data.fecha_inicio <= assignment.vigente_desde <= (assignment.vigente_hasta or data.fecha_fin) <= data.fecha_fin:
            raise HTTPException(409,'Las fechas dejarían una asignación docente fuera de la gestión.')
    # Existing classroom activities also constrain a calendar correction.
    for model, column in ((m.JornadaClase,m.JornadaClase.fecha),(m.Evaluacion,m.Evaluacion.fecha_aplicacion)):
        outside = db.scalar(select(model.id).join(m.Curso, m.Curso.id == model.curso_id).where(m.Curso.gestion_id == id, or_(column < data.fecha_inicio, column > data.fecha_fin)).limit(1))
        if outside:
            raise HTTPException(409, 'Las fechas dejarían actividades escolares fuera de la gestión.')
    antes = fila(obj); aplicar(obj, data)
    return guardar(db, obj, user, antes)


@router.get('/docentes')
def docentes(db: Session = Depends(get_db)):
    return [{'id':u.id, 'nombre':u.nombre, 'apellido':u.apellido} for u in db.scalars(select(m.Usuario).where(m.Usuario.rol == 'Docente', m.Usuario.activo == True).order_by(m.Usuario.apellido))]


@router.get('/cursos')
def cursos(db: Session = Depends(get_db)):
    rows = db.execute(select(m.Curso, m.Gestion.anio, m.Usuario.nombre, m.Usuario.apellido).join(m.Gestion).outerjoin(m.Usuario, m.Curso.docente_asesor_id == m.Usuario.id).order_by(m.Gestion.anio.desc(), m.Curso.grado, m.Curso.paralelo))
    return [{**fila(c), 'gestion_anio':year, 'docente_nombre':f'{name or ""} {last or ""}'.strip()} for c,year,name,last in rows]


def validar_curso(db, data):
    obtener(db, m.Gestion, data.gestion_id, True)
    if data.docente_asesor_id:
        u = obtener(db, m.Usuario, data.docente_asesor_id)
        if not u.activo or u.rol != 'Docente':
            raise HTTPException(422, 'El asesor debe ser un docente activo.')


@router.post('/cursos', status_code=201)
def crear_curso(data: CursoEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    validar_curso(db, data)
    data.paralelo = data.paralelo.upper()
    return guardar(db, m.Curso(**data.model_dump()), user)


@router.put('/cursos/{id}')
def editar_curso(id: int, data: CursoEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    validar_curso(db, data)
    obj = obtener(db, m.Curso, id, True)
    data.paralelo = data.paralelo.upper()
    if (obj.gestion_id,obj.grado,obj.paralelo) != (data.gestion_id,data.grado,data.paralelo):
        for model in (m.Matricula,m.AsignacionDocente,m.JornadaClase):
            if db.scalar(select(model.id).where(model.curso_id == id).limit(1)):
                raise HTTPException(409, 'El curso ya tiene registros. Conserva su identidad y crea otro curso para el cambio.')
    antes = fila(obj); aplicar(obj,data)
    return guardar(db,obj,user,antes)


@router.get('/estudiantes')
def estudiantes(db: Session = Depends(get_db)):
    return [fila(x) for x in db.scalars(select(m.Estudiante).order_by(m.Estudiante.apellido,m.Estudiante.nombre))]


@router.post('/estudiantes', status_code=201)
def crear_estudiante(data: EstudianteEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    return guardar(db,m.Estudiante(codigo_anonimo='EST-'+uuid4().hex, **data.model_dump()),user)


@router.put('/estudiantes/{id}')
def editar_estudiante(id: int, data: EstudianteEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    obj = obtener(db,m.Estudiante,id,True)
    if data.fecha_nacimiento and db.scalar(select(m.Matricula.id).where(m.Matricula.estudiante_id == id,m.Matricula.fecha_ingreso < data.fecha_nacimiento).limit(1)):
        raise HTTPException(422, 'El nacimiento no puede ser posterior al ingreso registrado.')
    antes=fila(obj); aplicar(obj,data)
    return guardar(db,obj,user,antes)


@router.get('/matriculas')
def matriculas(db: Session = Depends(get_db)):
    rows=db.execute(select(m.Matricula,m.Estudiante.nombre,m.Estudiante.apellido,m.Curso.grado,m.Curso.paralelo,m.Gestion.anio,m.Gestion.fecha_fin).join(m.Estudiante,m.Estudiante.id==m.Matricula.estudiante_id).join(m.Curso,m.Curso.id==m.Matricula.curso_id).join(m.Gestion,m.Gestion.id==m.Curso.gestion_id).order_by(m.Matricula.fecha_ingreso.desc(),m.Matricula.id.desc()))
    today=date.today()
    return [{**fila(x),'estudiante_nombre':f'{n} {a}','curso_nombre':f'{g}° {p}','gestion_anio':y,
             'estado': 'PROGRAMADA' if x.fecha_ingreso > today else ('FINALIZADA' if (x.fecha_fin or fin) and (x.fecha_fin or fin) < today else 'VIGENTE')} for x,n,a,g,p,y,fin in rows]


def validar_matricula(db,data,id=None):
    curso=obtener(db,m.Curso,data.curso_id)
    gestion=obtener(db,m.Gestion,curso.gestion_id,True)
    student=obtener(db,m.Estudiante,data.estudiante_id,True)
    if not gestion.fecha_inicio or not gestion.fecha_fin:
        raise HTTPException(422, 'Completa las fechas de la gestión antes de matricular.')
    end=data.fecha_fin or gestion.fecha_fin
    if not gestion.fecha_inicio <= data.fecha_ingreso <= end <= gestion.fecha_fin:
        raise HTTPException(422, 'La matrícula debe estar dentro de las fechas de la gestión.')
    if student.fecha_nacimiento and data.fecha_ingreso < student.fecha_nacimiento:
        raise HTTPException(422, 'El ingreso no puede ser anterior al nacimiento.')
    # Lock the student first: two concurrent requests cannot open overlapping segments.
    overlap=db.scalar(select(m.Matricula.id).join(m.Curso,m.Curso.id==m.Matricula.curso_id).join(m.Gestion,m.Gestion.id==m.Curso.gestion_id).where(m.Matricula.estudiante_id==data.estudiante_id,m.Matricula.id != (id or 0),m.Matricula.fecha_ingreso <= end,func.coalesce(m.Matricula.fecha_fin,m.Gestion.fecha_fin) >= data.fecha_ingreso).with_for_update().limit(1))
    if overlap:
        raise HTTPException(409, 'El estudiante ya tiene una matrícula que se cruza con estas fechas. Cierra el segmento anterior antes de cambiar de curso.')


@router.post('/matriculas', status_code=201)
def crear_matricula(data: MatriculaEntrada, db: Session = Depends(get_db), user=Depends(encargado)):
    validar_matricula(db,data)
    return guardar(db,m.Matricula(**data.model_dump(),registrado_por=user.id),user)


@router.put('/matriculas/{id}')
def editar_matricula(id:int,data:MatriculaEntrada,db:Session=Depends(get_db),user=Depends(encargado)):
    validar_matricula(db,data,id)
    obj=obtener(db,m.Matricula,id,True)
    if obj.estudiante_id != data.estudiante_id or obj.curso_id != data.curso_id:
        raise HTTPException(409,'Para cambiar de estudiante o curso, conserva esta matrícula y crea una nueva.')
    if any(getattr(obj,k)!=v for k,v in data.model_dump().items()):
        for model in (m.Asistencia,m.Calificacion,m.EntregaTarea,m.RegistroConvivencia,m.SituacionEscolar,m.CortePredictivo,m.Citacion):
            if db.scalar(select(model.id).where(model.matricula_id==id).limit(1)):
                raise HTTPException(409,'La matrícula tiene registros asociados. Su cierre o corrección requiere revisar ese historial.')
    antes=fila(obj); aplicar(obj,data)
    return guardar(db,obj,user,antes)
