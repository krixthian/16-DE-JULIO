"""Asistencia por materia (por hora), licencia parcial y citaciones por origen.

Complementa la asistencia diaria (api/asistencia.py) sin modificarla. El porcentaje de asistencia se calcula por
materia (clases asistidas / clases registradas de esa materia), para que materias con distinta frecuencia semanal
se comparen en la misma escala. Todo cambio queda en auditoria_cambios.
"""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from api.asistencia import personal, autorizacion
from api.escolar import Entrada, obtener, fila
from database import get_db
from predictivo import asistencia_materia as am
import models as m

router = APIRouter(prefix='/asistencia-materia', tags=['Asistencia por materia'])
citaciones_router = APIRouter(prefix='/citaciones', tags=['Citaciones'])
ESTADOS = ('PRESENTE', 'FALTA', 'ATRASO', 'LICENCIA')


def auditar(db, obj, user, antes, motivo):
    db.flush()
    db.add(m.AuditoriaCambio(usuario_id=user.id, tabla_afectada=obj.__tablename__, registro_id=obj.id,
        operacion='ALTA' if antes is None else 'CORRECCION', antes=jsonable_encoder(antes), despues=jsonable_encoder(fila(obj)), motivo=motivo))


def materias_del_curso(db, curso_id, user=None, fecha=None):
    """Materias con asignación docente en el curso; un docente solo ve las suyas vigentes en la fecha."""
    stmt = select(m.Materia).join(m.AsignacionDocente, m.AsignacionDocente.materia_id == m.Materia.id).where(
        m.AsignacionDocente.curso_id == curso_id)
    if user is not None and user.rol == 'Docente':
        stmt = stmt.where(m.AsignacionDocente.docente_id == user.id)
        if fecha is not None:
            stmt = stmt.where(m.AsignacionDocente.vigente_desde <= fecha,
                or_(m.AsignacionDocente.vigente_hasta == None, m.AsignacionDocente.vigente_hasta >= fecha))
    return list(db.scalars(stmt.distinct().order_by(m.Materia.nombre)))


def lista(db, curso_id, fecha):
    rows = db.execute(select(m.Matricula, m.Estudiante).join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id).where(
        m.Matricula.curso_id == curso_id, m.Matricula.fecha_ingreso <= fecha,
        or_(m.Matricula.fecha_fin == None, m.Matricula.fecha_fin >= fecha)).order_by(m.Estudiante.apellido, m.Estudiante.nombre, m.Matricula.id)).all()
    return [{'matricula_id': e.id, 'nombre': s.nombre, 'apellido': s.apellido, 'codigo': s.codigo_anonimo, 'origen': e.origen} for e, s in rows]


def dia(db, course, gestion, fecha, user):
    jornada = db.scalar(select(m.JornadaClase).where(m.JornadaClase.curso_id == course.id, m.JornadaClase.fecha == fecha))
    sesiones = list(db.scalars(select(m.SesionClase).where(m.SesionClase.jornada_id == jornada.id).order_by(m.SesionClase.periodo))) if jornada else []
    registros = list(db.scalars(select(m.AsistenciaMateria).where(m.AsistenciaMateria.sesion_id.in_([s.id for s in sesiones])))) if sesiones else []
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Materia))}
    por_sesion = {}
    for r in registros:
        por_sesion.setdefault(r.sesion_id, {})[r.matricula_id] = {'estado': r.estado, 'justificada': r.justificada, 'observacion': r.observacion}
    return {'curso_id': course.id, 'curso': f'{course.grado}° {course.paralelo}', 'gestion': gestion.anio, 'fecha': fecha,
        'es_lectiva': jornada.es_lectiva if jornada else True,
        'materias': [{'id': x.id, 'nombre': x.nombre} for x in materias_del_curso(db, course.id, user, fecha)],
        'sesiones': [{'id': s.id, 'periodo': s.periodo, 'materia_id': s.materia_id, 'materia': nombres.get(s.materia_id), 'dictada': s.dictada,
            'registros': {str(k): v for k, v in por_sesion.get(s.id, {}).items()}} for s in sesiones],
        'estudiantes': lista(db, course.id, fecha)}


@router.get('/{curso_id}/{fecha}')
def consultar(curso_id: int, fecha: date, db: Session = Depends(get_db), user=Depends(personal)):
    course, gestion = autorizacion(db, user, curso_id, fecha)
    return dia(db, course, gestion, fecha, user)


class RegistroHora(Entrada):
    matricula_id: int = Field(gt=0)
    estado: Literal[ESTADOS]
    justificada: bool | None = None
    observacion: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def coherencia(self):
        if self.estado == 'PRESENTE' and self.justificada is not None:
            raise ValueError('La justificación solo corresponde a falta, atraso o licencia.')
        return self


class HoraEntrada(Entrada):
    materia_id: int = Field(gt=0)
    dictada: bool = True
    motivo_correccion: str | None = Field(default=None, max_length=500)
    estudiantes: list[RegistroHora] = Field(default_factory=list, max_length=2000)

    @model_validator(mode='after')
    def coherencia(self):
        ids = [x.matricula_id for x in self.estudiantes]
        if len(ids) != len(set(ids)):
            raise ValueError('Hay estudiantes repetidos en la lista.')
        if not self.dictada and self.estudiantes:
            raise ValueError('Una clase no dictada no lleva asistencia.')
        if self.dictada and not self.estudiantes:
            raise ValueError('Marca la asistencia de al menos un estudiante.')
        return self


@router.put('/{curso_id}/{fecha}/{periodo}')
def guardar(curso_id: int, fecha: date, periodo: int, data: HoraEntrada, db: Session = Depends(get_db), user=Depends(personal)):
    if not 1 <= periodo <= 8:
        raise HTTPException(422, 'La hora debe estar entre 1 y 8.')
    if fecha > date.today():
        raise HTTPException(422, 'No se puede registrar asistencia de una fecha futura.')
    course, gestion = autorizacion(db, user, curso_id, fecha, True)
    if data.materia_id not in {x.id for x in materias_del_curso(db, curso_id, user, fecha)}:
        raise HTTPException(403 if user.rol == 'Docente' else 422, 'La materia no está asignada a este curso (o no es tuya en esa fecha).')
    vigentes = {x['matricula_id'] for x in lista(db, curso_id, fecha)}
    if {x.matricula_id for x in data.estudiantes} - vigentes:
        raise HTTPException(422, 'Hay estudiantes que no tienen matrícula vigente en el curso y fecha.')
    jornada = db.scalar(select(m.JornadaClase).where(m.JornadaClase.curso_id == curso_id, m.JornadaClase.fecha == fecha).with_for_update())
    if jornada is not None and not jornada.es_lectiva:
        raise HTTPException(409, 'Ese día está registrado como día sin clases.')
    motivo = data.motivo_correccion or 'Registro de asistencia por materia'
    if jornada is None:
        jornada = m.JornadaClase(curso_id=curso_id, fecha=fecha, es_lectiva=True)
        db.add(jornada)
        auditar(db, jornada, user, None, motivo)
    sesion = db.scalar(select(m.SesionClase).where(m.SesionClase.jornada_id == jornada.id, m.SesionClase.periodo == periodo).with_for_update())
    previos = {r.matricula_id: r for r in db.scalars(select(m.AsistenciaMateria).where(m.AsistenciaMateria.sesion_id == sesion.id).with_for_update())} if sesion else {}
    cambia_sesion = sesion is not None and (sesion.materia_id != data.materia_id or sesion.dictada != data.dictada)
    cambia_registro = any(x.matricula_id in previos and any(getattr(previos[x.matricula_id], k) != getattr(x, k)
        for k in ('estado', 'justificada', 'observacion')) for x in data.estudiantes)
    if (cambia_sesion or cambia_registro) and not data.motivo_correccion:
        raise HTTPException(422, 'Indica un motivo para corregir una hora ya registrada.')
    if cambia_sesion and previos and (not data.dictada or sesion.materia_id != data.materia_id):
        raise HTTPException(409, 'Esa hora ya tiene asistencia registrada; no se puede cambiar la materia ni marcarla como no dictada.')
    if sesion is None:
        sesion = m.SesionClase(jornada_id=jornada.id, curso_id=curso_id, materia_id=data.materia_id, periodo=periodo,
            dictada=data.dictada, registrado_por=user.id)
        db.add(sesion)
        auditar(db, sesion, user, None, motivo)
    elif cambia_sesion:
        antes = fila(sesion)
        sesion.materia_id, sesion.dictada = data.materia_id, data.dictada
        auditar(db, sesion, user, antes, motivo)
    for x in data.estudiantes:
        viejo = previos.get(x.matricula_id)
        if viejo and all(getattr(viejo, k) == getattr(x, k) for k in ('estado', 'justificada', 'observacion')):
            continue
        antes = fila(viejo) if viejo else None
        obj = viejo or m.AsistenciaMateria(sesion_id=sesion.id, curso_id=curso_id, matricula_id=x.matricula_id)
        obj.estado, obj.justificada, obj.observacion = x.estado, x.justificada, x.observacion
        obj.registrado_por, obj.registrado_en = user.id, datetime.now()
        db.add(obj)
        auditar(db, obj, user, antes, motivo)
    db.commit()
    return dia(db, course, gestion, fecha, user)


def desglose(db, matricula):
    """Asistencia por materia, licencias parciales y citaciones por origen de una matrícula (todo el registro disponible)."""
    jornadas = list(db.scalars(select(m.JornadaClase.id).where(m.JornadaClase.curso_id == matricula.curso_id, m.JornadaClase.es_lectiva == True)))
    sesiones = [{'id': s.id, 'materia_id': s.materia_id, 'dictada': s.dictada, 'jornada_id': s.jornada_id, 'periodo': s.periodo}
        for s in db.scalars(select(m.SesionClase).where(m.SesionClase.jornada_id.in_(jornadas)))] if jornadas else []
    registros = [{'sesion_id': r.sesion_id, 'estado': r.estado} for r in db.scalars(select(m.AsistenciaMateria).where(
        m.AsistenciaMateria.matricula_id == matricula.id))]
    citaciones = [{'origen': c.origen, 'materia_id': c.materia_id, 'fecha': c.fecha_programada, 'estado': c.estado}
        for c in db.scalars(select(m.Citacion).where(m.Citacion.matricula_id == matricula.id).order_by(m.Citacion.fecha_programada))]
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Materia))}
    materias = am.por_materia(sesiones, registros)
    por_materia_cit = {}
    for c in citaciones:
        if c['materia_id'] is not None:
            por_materia_cit[c['materia_id']] = por_materia_cit.get(c['materia_id'], 0) + 1
    filas = [{'materia_id': k, 'materia': nombres.get(k), **v, 'citaciones': por_materia_cit.get(k, 0), 'baja': v['porcentaje'] is not None and v['porcentaje'] < am.UMBRAL_MATERIA}
        for k, v in materias.items()]
    filas += [{'materia_id': k, 'materia': nombres.get(k), 'dictadas': 0, 'observadas': 0, 'presentes': 0, 'atrasos': 0, 'faltas': 0, 'licencias': 0,
        'porcentaje': None, 'citaciones': n, 'baja': False} for k, n in por_materia_cit.items() if k not in materias]
    return {'matricula_id': matricula.id, 'umbral': am.UMBRAL_MATERIA, 'materias': sorted(filas, key=lambda f: (f['porcentaje'] is None, f['porcentaje'] or 0)),
        'indicadores': am.indicadores(sesiones, registros, citaciones),
        'citaciones': [{**c, 'materia': nombres.get(c['materia_id'])} for c in citaciones]}


@router.get('/matricula/{matricula_id}/desglose')
def ver_desglose(matricula_id: int, db: Session = Depends(get_db), user=Depends(personal)):
    matricula = obtener(db, m.Matricula, matricula_id)
    if user.rol == 'Docente' and not db.scalar(select(m.AsignacionDocente.id).where(m.AsignacionDocente.curso_id == matricula.curso_id,
            m.AsignacionDocente.docente_id == user.id).limit(1)):
        raise HTTPException(403, 'No tienes una asignación en el curso de esta matrícula.')
    return desglose(db, matricula)


class CitacionEntrada(Entrada):
    matricula_id: int = Field(gt=0)
    apoderado_id: int = Field(gt=0)
    fecha_programada: datetime
    motivo: str = Field(min_length=3, max_length=2000)
    origen: Literal['DOCENTE_MATERIA', 'DIRECCION', 'ORIENTACION']
    materia_id: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def coherencia(self):
        if (self.origen == 'DOCENTE_MATERIA') != (self.materia_id is not None):
            raise ValueError('Una citación de docente por materia debe indicar la materia; las de dirección u orientación no llevan materia.')
        return self


@citaciones_router.post('', status_code=201)
def crear_citacion(data: CitacionEntrada, db: Session = Depends(get_db), user=Depends(personal)):
    matricula = obtener(db, m.Matricula, data.matricula_id)
    obtener(db, m.Apoderado, data.apoderado_id)
    if user.rol == 'Docente':
        if data.origen != 'DOCENTE_MATERIA' or data.materia_id not in {x.id for x in materias_del_curso(db, matricula.curso_id, user)}:
            raise HTTPException(403, 'Un docente solo registra citaciones de sus materias en el curso.')
    elif data.materia_id is not None and data.materia_id not in {x.id for x in materias_del_curso(db, matricula.curso_id)}:
        raise HTTPException(422, 'La materia no está asignada al curso del estudiante.')
    obj = m.Citacion(matricula_id=data.matricula_id, apoderado_id=data.apoderado_id, fecha_programada=data.fecha_programada,
        motivo=data.motivo, origen=data.origen, materia_id=data.materia_id, registrado_por=user.id)
    db.add(obj)
    auditar(db, obj, user, None, 'Registro de citación')
    db.commit()
    return {'id': obj.id, **desglose(db, matricula)}


@citaciones_router.get('/apoderados/{matricula_id}')
def apoderados(matricula_id: int, db: Session = Depends(get_db), user=Depends(personal)):
    """Apoderados vinculados al estudiante de la matrícula (para elegir a quién se cita)."""
    matricula = obtener(db, m.Matricula, matricula_id)
    rows = db.execute(select(m.EstudianteApoderado).where(m.EstudianteApoderado.estudiante_id == matricula.estudiante_id,
        or_(m.EstudianteApoderado.vigente_hasta == None, m.EstudianteApoderado.vigente_hasta >= date.today()))).scalars()
    # Sin nombres ni teléfonos: basta el parentesco para elegir a quién se cita.
    return [{'id': v.apoderado_id, 'nombre': v.parentesco + (' · contacto principal' if v.contacto_principal else '')} for v in rows]
