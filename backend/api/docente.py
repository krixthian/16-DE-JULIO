"""Vista del docente: las alertas de SUS estudiantes (solo lectura).

El docente alimenta el sistema (asistencia, notas, tareas, citaciones por su materia); aquí recibe de vuelta las
alertas de los cursos donde tiene una asignación vigente. Ve la alerta inmediata (5 faltas seguidas), el nivel del
semáforo y el porqué en palabras simples; no ve puntajes ni otros cursos. La gestión del caso (responsable,
intervenciones, cierre) sigue siendo de Dirección y Orientación. Solo identificadores anónimos de estudiantes.
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from api.asistencia import personal
from api.calificaciones import assignment
from database import get_db
from predictivo import desglose as dg, seguimiento as sg
import models as m

router = APIRouter(prefix='/docente', tags=['Vista del docente'], dependencies=[Depends(personal)])
NOTA = ('Alertas de tus cursos, calculadas con la asistencia y las notas registradas hasta la fecha. "Alerta inmediata" '
    'significa 5 o más faltas seguidas: conversa con el estudiante si vuelve, y avisa a Dirección u Orientación, que '
    'coordinan el contacto con la familia. La alerta junta notas, actitud y asistencia, y dice su motivo. El color ordena a quién atender primero; no es un diagnóstico.')


def cursos_del_docente(db, user, gestion_id, fecha):
    """Cursos de la gestión donde el usuario tiene una asignación vigente a la fecha (Admin y Director: todos)."""
    stmt = select(m.Curso.id).where(m.Curso.gestion_id == gestion_id)
    if user.rol == 'Docente':
        stmt = stmt.where(m.Curso.id.in_(select(m.AsignacionDocente.curso_id).where(
            m.AsignacionDocente.docente_id == user.id, m.AsignacionDocente.vigente_desde <= fecha,
            or_(m.AsignacionDocente.vigente_hasta == None, m.AsignacionDocente.vigente_hasta >= fecha))))
    return list(db.scalars(stmt))


@router.get('/alertas')
def mis_alertas(gestion: int | None = None, fecha: date | None = None, db: Session = Depends(get_db), user=Depends(personal)):
    if gestion is None:
        gestion = db.scalar(select(func.max(m.Gestion.anio)))
    g = db.scalar(select(m.Gestion).where(m.Gestion.anio == gestion))
    if g is None:
        raise HTTPException(404, f'No existe la gestión {gestion}.')
    referencia = fecha or min(date.today(), g.fecha_fin or date.today())
    cursos = cursos_del_docente(db, user, g.id, referencia)
    base = {'gestion': gestion, 'nota': NOTA, 'racha_alerta': sg.RACHA_ALERTA, 'mis_cursos': len(cursos)}
    if not cursos:
        return {**base, 'fecha': referencia.isoformat(), 'total': 0, 'alertas': [],
            'motivo': 'No tienes cursos asignados en esta gestión.'}
    r = sg.calcular(db, gestion, fecha, solo_cursos=cursos)
    alertas = [dict(matricula_id=a['matricula_id'], estudiante=a['estudiante'], curso=a['curso'], origen=a['origen'],
        alerta_inmediata=a['alerta_inmediata'], nivel=a['perfil']['nivel'], colores=a['perfil']['colores'], motivos=a['perfil']['motivos'], notas_y_asistencia=a['perfil']['notas_y_asistencia'], faltas_seguidas=a['racha_actual'], ultima_asistencia=a['ultima_asistencia'],
        porque=[dict(descripcion=f['descripcion'], variable=f['variable'], valor=f['valor']) for f in a['factores']])
        for a in r['alertas'] if a['perfil']['nivel'] != 'VERDE']
    return {**base, 'fecha': r['fecha'], 'mes': r['mes'], 'total': len(alertas), 'estudiantes_con_registro': r['total'],
        'alertas': alertas, 'motivo': r.get('motivo')}


TIPOS = ('PRUEBA', 'TRABAJO', 'PROYECTO', 'ORAL', 'OTRA')
SEMANAS = 4
NOTA_DESGLOSE = ('Notas sobre 100 (puntaje entre el máximo de cada actividad) con lo registrado hasta la fecha. Una casilla '
    'sin nota no cuenta como cero. El promedio es simple y sirve para observar; no reemplaza la nota oficial.')


def _media(v):
    return round(sum(v) / len(v), 1) if v else None


@router.get('/notas/actividades')
def actividades_de_dimension(asignacion_id: int, matricula_id: int, trimestre: int, dimension: str, fecha: date | None = None,
        db: Session = Depends(get_db), user=Depends(personal)):
    """Las actividades que forman la nota de una dimensión para un estudiante, con el promedio del curso. Solo lectura."""
    a, curso, g = assignment(db, user, asignacion_id)
    mat = db.get(m.Matricula, matricula_id)
    if mat is None or mat.curso_id != curso.id:
        raise HTTPException(404, 'El estudiante no pertenece a este curso.')
    fecha = min(fecha or date.today(), date.today())
    evs = [e for e in db.scalars(select(m.Evaluacion).join(m.Periodo, m.Periodo.id == m.Evaluacion.periodo_id).where(m.Evaluacion.asignacion_id == a.id,
        m.Periodo.numero == trimestre, m.Evaluacion.dimension == dimension, m.Evaluacion.fecha_aplicacion <= fecha)
        .order_by(m.Evaluacion.fecha_aplicacion, m.Evaluacion.id)) if not dg.CIERRE.match(e.titulo)]
    notas = {}
    for n in db.scalars(select(m.Calificacion).where(m.Calificacion.evaluacion_id.in_([e.id for e in evs]))):
        notas.setdefault(n.evaluacion_id, {})[n.matricula_id] = n
    out = []
    for e in evs:
        n = notas.get(e.id, {})
        mia, archivo = n.get(mat.id), bool(dg.ARCHIVO.match(e.titulo))
        out.append(dict(id=e.id, titulo=e.titulo.split(' - ', 2)[-1] if archivo else e.titulo, fecha=None if archivo else e.fecha_aplicacion.isoformat(),
            maximo=float(e.puntaje_maximo), estado=mia.estado if mia else None, puntaje=float(mia.puntaje) if mia and mia.puntaje is not None else None,
            curso=_media([float(x.puntaje) for x in n.values() if x.puntaje is not None])))
    return dict(trimestre=trimestre, dimension=dimension, actividades=out)


@router.get('/notas')
def notas_desglosadas(asignacion_id: int, fecha: date | None = None, db: Session = Depends(get_db), user=Depends(personal)):
    """Notas por tipo de actividad y tareas de una asignación (materia y curso), hasta la fecha. Solo lectura."""
    a, curso, g = assignment(db, user, asignacion_id)
    hoy = date.today()
    fecha = fecha or min(hoy, g.fecha_fin or hoy)
    if fecha > hoy:
        raise HTTPException(422, 'La fecha no puede ser futura.')
    reciente = fecha - timedelta(weeks=SEMANAS)  # las últimas 4 semanas son los días posteriores a esta fecha
    materia = db.get(m.Materia, a.materia_id)
    evs = list(db.scalars(select(m.Evaluacion).where(m.Evaluacion.asignacion_id == a.id, m.Evaluacion.fecha_aplicacion <= fecha)
        .order_by(m.Evaluacion.fecha_aplicacion, m.Evaluacion.id)))
    tareas = list(db.scalars(select(m.Tarea).where(m.Tarea.asignacion_id == a.id, m.Tarea.fecha_limite <= datetime.combine(fecha, time(23, 59, 59)),
        m.Tarea.fecha_limite <= datetime.now()).order_by(m.Tarea.fecha_limite, m.Tarea.id)))
    notas = {(n.evaluacion_id, n.matricula_id): n for n in db.scalars(select(m.Calificacion).where(m.Calificacion.evaluacion_id.in_([e.id for e in evs])))}
    entregas = {(t.tarea_id, t.matricula_id): t.estado for t in db.scalars(select(m.EntregaTarea).where(m.EntregaTarea.tarea_id.in_([t.id for t in tareas])))}
    trimestrales, actividades, sobran = {}, [], dg.redundantes(evs)
    numero = {p.id: p.numero for p in db.scalars(select(m.Periodo).where(m.Periodo.gestion_id == g.id))}
    con_dimension = [e for e in evs if e.dimension in dg.DIMENSIONES and e.id not in sobran]
    con_lista = {(numero.get(e.periodo_id), e.dimension) for e in evs if e.dimension and not dg.CIERRE.match(e.titulo)}
    claves = sorted({(numero.get(e.periodo_id), e.dimension) for e in con_dimension}, key=lambda k: (k[0] or 0, list(dg.DIMENSIONES).index(k[1])))
    for e in evs:
        cierre = dg.CIERRE.match(e.titulo) if e.tipo == 'OTRA' else None
        if cierre:  # nota de cierre del trimestre (del área o de una dimensión): no es una actividad
            if dg.NOTA.match(e.titulo):
                trimestrales[int(cierre[3])] = e
        elif not dg.ARCHIVO.match(e.titulo):  # las de los archivos no tienen fecha propia: solo se listan en su dimensión
            actividades.append(e)

    def pct(n, e):
        return float(n.puntaje) / float(e.puntaje_maximo) * 100 if n is not None and n.estado == 'CALIFICADA' else None

    filas = []
    miembros = db.execute(select(m.Matricula, m.Estudiante.codigo_anonimo).join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id)
        .where(m.Matricula.curso_id == curso.id, m.Matricula.fecha_ingreso <= fecha,
            or_(m.Matricula.fecha_fin == None, m.Matricula.fecha_fin >= fecha)).order_by(m.Estudiante.codigo_anonimo))
    for mat, codigo in miembros:
        # Solo lo aplicado mientras el estudiante estaba matriculado.
        mias = [(e, notas.get((e.id, mat.id))) for e in actividades if e.fecha_aplicacion >= mat.fecha_ingreso]
        vals = [(e, v) for e, n in mias if (v := pct(n, e)) is not None]
        ult = _media([v for e, v in vals if e.fecha_aplicacion > reciente])
        ant = _media([v for e, v in vals if e.fecha_aplicacion <= reciente])
        estados = [entregas.get((t.id, mat.id)) for t in tareas if t.fecha_limite.date() >= mat.fecha_ingreso]
        seguidas = 0
        for x in reversed([x for x in estados if x in ('ENTREGADA', 'NO_ENTREGADA')]):
            if x == 'ENTREGADA':
                break
            seguidas += 1
        filas.append(dict(matricula_id=mat.id, estudiante=codigo, origen=mat.origen,
            por_tipo={t: _media([v for e, v in vals if e.tipo == t]) for t in TIPOS},
            dimensiones={f'{t}-{d}': _media([v for e in con_dimension if (numero.get(e.periodo_id), e.dimension) == (t, d)
                and e.fecha_aplicacion >= mat.fecha_ingreso and (v := pct(notas.get((e.id, mat.id)), e)) is not None]) for t, d in claves},
            promedio=_media([v for _, v in vals]), ultimas=ult, anteriores=ant,
            cambio=round(ult - ant, 1) if ult is not None and ant is not None else None,
            no_presentadas=sum(n is not None and n.estado == 'NO_PRESENTADA' for _, n in mias),
            sin_nota=sum(n is None or n.estado == 'PENDIENTE' for _, n in mias),
            trimestres={k: pct(notas.get((e.id, mat.id)), e) for k, e in trimestrales.items()},
            tareas=dict(entregadas=estados.count('ENTREGADA'), no_entregadas=estados.count('NO_ENTREGADA'),
                por_revisar=sum(x in (None, 'PENDIENTE') for x in estados), seguidas_sin_entregar=seguidas)))

    def del_curso(f):
        return _media([x for x in map(f, filas) if x is not None])
    return dict(fecha=fecha.isoformat(), gestion=g.anio, curso=f'{curso.grado}° {curso.paralelo}', materia=materia.nombre, nota=NOTA_DESGLOSE,
        semanas=SEMANAS, actividades={t: sum(e.tipo == t for e in actividades) for t in TIPOS}, total_actividades=len(actividades),
        total_tareas=len(tareas), trimestres=sorted(trimestrales), dimensiones=[dict(trimestre=t, dimension=d, clave=f'{t}-{d}', con_actividades=(t, d) in con_lista) for t, d in claves], curso_promedio=dict(
            dimensiones={f'{t}-{d}': del_curso(lambda r: r['dimensiones'][f'{t}-{d}']) for t, d in claves}, promedio=del_curso(lambda r: r['promedio']),
            ultimas=del_curso(lambda r: r['ultimas']), por_tipo={t: del_curso(lambda r: r['por_tipo'][t]) for t in TIPOS},
            trimestres={k: del_curso(lambda r: r['trimestres'][k]) for k in trimestrales}), estudiantes=filas)
