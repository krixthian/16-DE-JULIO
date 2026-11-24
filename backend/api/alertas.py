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
from predictivo import explicacion as ex
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


def alerta_dict(row, total, puesto, abandonos=frozenset()):
    a, p, mod, c, cur, g, e, u = row
    return {'id': a.id, 'estado': a.estado, 'creada_en': a.creada_en, 'cerrada_en': a.cerrada_en, 'motivo_cierre': a.motivo_cierre,
        'probabilidad': float(p.probabilidad), 'nivel': p.nivel, 'factores': (p.factores or {}).get('principales', []),
        'uso': (p.factores or {}).get('uso'), 'modelo': mod.version, 'fecha_corte': c.fecha_corte, 'gestion': g.anio,
        'curso_id': cur.id, 'curso': f'{cur.grado}° {cur.paralelo}', 'grado': cur.grado, 'estudiante': e.codigo_anonimo,
        'abandono_confirmado': c.matricula_id in abandonos,
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
    abandonos = matriculas_con_abandono(db, [r[3].matricula_id for r in rows])
    return [alerta_dict(r, count.get(r[0].id, 0), puestos[r[0].id], abandonos) for r in rows]


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


REGLA_ACADEMICA = ('Regla RP02: al menos un área con promedio menor a 51 ("en desarrollo", escala de la Ley 070) en el '
    '1.er trimestre, con las notas registradas en el sistema. No es una predicción del modelo: señala bajo rendimiento, que en el '
    'historial casi no se asoció al abandono; sirve para reforzamiento pedagógico.')


NOTA_INASISTENCIA = ('Regla operativa, no es una predicción del modelo. Probada en los archivos recibidos de 2021-2025 (origen '
    'no verificado): con 5 faltas seguidas se marcan 11 de 11 abandonos y 0 de 1878 matrículas que continuaron; en versiones posteriores de esos '
    'archivos, entre 46 y 49 de 1728. La alerta sale unos 84 días antes del cierre del trimestre. Es retrospectivo y el abandono se definió con la asistencia.')


@router.get('/alertas/seguimiento/gestiones')
def seguimiento_por_gestion(db: Session = Depends(get_db)):
    """Resumen por gestión y total: alerta inmediata (5 faltas seguidas) revisada día por día en todo el año, frente al
    abandono confirmado (situaciones escolares). Solo lectura. Una "falsa alarma" es un estudiante que llegó a 5 faltas
    seguidas y no tiene abandono confirmado; en la gestión en curso eso puede cambiar."""
    from collections import defaultdict
    from predictivo import seguimiento as sg
    k = sg.RACHA_ALERTA
    info = {mid: (anio, origen) for mid, anio, origen in db.execute(select(m.Matricula.id, m.Gestion.anio, m.Matricula.origen)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id))}
    dias = defaultdict(list)
    for mid, fecha, estado in db.execute(select(m.Asistencia.matricula_id, m.JornadaClase.fecha, m.Asistencia.estado)
            .join(m.JornadaClase, m.JornadaClase.id == m.Asistencia.jornada_id).where(m.JornadaClase.es_lectiva == True)):
        dias[mid].append((fecha, estado))
    alerta = {}
    for mid, regs in dias.items():
        racha = 0
        for fecha, estado in sorted(regs):
            racha = racha + 1 if estado == 'FALTA' else 0
            if racha >= k:
                alerta[mid] = fecha
                break
    abandono = set(db.scalars(select(m.SituacionEscolar.matricula_id).where(m.SituacionEscolar.tipo == 'ABANDONO_CONFIRMADO')))
    filas = {}
    for mid, (anio, origen) in info.items():
        f = filas.setdefault(anio, dict(gestion=anio, simulada=False, matriculas=0, con_asistencia=0, alertas_inmediatas=0,
            abandonos_confirmados=0, detectados=0, falsas_alarmas=0))
        f['matriculas'] += 1
        f['simulada'] |= origen == 'SIMULADO'
        f['con_asistencia'] += mid in dias
        f['alertas_inmediatas'] += mid in alerta
        f['abandonos_confirmados'] += mid in abandono
        f['detectados'] += mid in alerta and mid in abandono
        f['falsas_alarmas'] += mid in alerta and mid not in abandono
    gestiones = sorted((f for f in filas.values() if f['con_asistencia']), key=lambda f: -f['gestion'])
    for f in gestiones:
        f['en_curso'] = f['simulada'] or f['gestion'] >= date.today().year
        if f['en_curso']:  # el año no cerró: aún no se sabe quién abandonó
            f['detectados'] = f['falsas_alarmas'] = f['abandonos_confirmados'] = None
    reales = [f for f in gestiones if not f['en_curso']]
    total = {c: sum(f[c] for f in reales) for c in ('matriculas', 'con_asistencia', 'alertas_inmediatas', 'abandonos_confirmados', 'detectados', 'falsas_alarmas')}
    return {'racha_alerta': k, 'gestiones': gestiones, 'total_reales': dict(gestiones=[f['gestion'] for f in reales], **total),
        'nota': 'Alerta inmediata revisada día por día en todo el año. El total general suma solo las gestiones no simuladas; '
            'las gestiones simuladas se muestran aparte y no tienen abandonos confirmados registrados.'}


@router.get('/alertas/seguimiento')
def seguimiento_continuo(gestion: int | None = None, fecha: date | None = None, db: Session = Depends(get_db)):
    """Riesgo a la fecha (seguimiento continuo): XGBoost del mes en curso con lo registrado hasta `fecha`, más la alerta
    inmediata de 5 faltas seguidas. Solo lectura. Por defecto: la gestión más reciente y su último día con asistencia."""
    from predictivo import seguimiento as sg
    ultima = db.scalar(select(func.max(m.Gestion.anio)))
    gestion = gestion or ultima
    try:
        r = sg.calcular(db, gestion, fecha)
    except LookupError as e:
        raise HTTPException(404, str(e))
    # Apertura automática (decisión de Dirección): solo al mirar HOY la gestión en curso; las fechas pasadas no escriben.
    r['casos_abiertos_ahora'] = 0
    r['gestion_en_curso'] = ultima
    if fecha is None and gestion == ultima and r['alertas']:
        r['casos_abiertos_ahora'] = sg.abrir_inmediatas(db, r)
        db.commit()
    casos = sg.casos_abiertos(db, [a['matricula_id'] for a in r['alertas']])
    for a in r['alertas']:
        c = casos.get(a['matricula_id'])
        a['caso'] = c and {'id': c[0], 'estado': c[1]}
    return r


class AperturaCaso(Entrada):
    matricula_id: int
    gestion: int
    fecha: date | None = None


@router.post('/alertas/seguimiento/abrir', status_code=201)
def abrir_caso(data: AperturaCaso, db: Session = Depends(get_db), user=Depends(seguimiento)):
    """Abre como caso una alerta del seguimiento (prioridad roja o amarilla, o inmediata) para asignar responsable e intervenciones."""
    from predictivo import seguimiento as sg
    mat = db.get(m.Matricula, data.matricula_id)
    if mat is None:
        raise HTTPException(404, 'Matrícula no encontrada.')
    if data.gestion != db.scalar(select(func.max(m.Gestion.anio))):
        raise HTTPException(422, 'Los casos se abren en la gestión en curso; las gestiones pasadas son de consulta.')
    try:
        r = sg.calcular(db, data.gestion, data.fecha, solo_cursos=[mat.curso_id])
    except LookupError as e:
        raise HTTPException(404, str(e))
    fila = next((a for a in r['alertas'] if a['matricula_id'] == mat.id), None)
    if fila is None:
        raise HTTPException(422, 'La matrícula no tiene asistencia registrada a esa fecha.')
    if fila['perfil']['nivel'] == 'VERDE':
        raise HTTPException(422, 'Solo se abren casos con alguna alerta; este estudiante está en verde.')
    caso_id, nuevo = sg.abrir_caso(db, r, fila, user, usuario=user)
    db.commit()
    return {'alerta_id': caso_id, 'nuevo': nuevo, 'alerta': responder(db, [obtener(db, caso_id)])[0]}


@router.get('/alertas/inasistencia')
def inasistencia_continua(dias: int = 5, gestion: int | None = None, db: Session = Depends(get_db)):
    """Alerta operativa (regla, no modelo): estudiantes con `dias` o más faltas seguidas al último registro.

    Usa la asistencia diaria y la asistencia por materia (un día es falta si faltó a todas las horas registradas).
    Probada en los archivos recibidos 2021-2025, de origen no verificado (docs/experimento_seguimiento_mensual.json,
    docs/CONSISTENCIA_REGISTROS.md): 11 de 11 abandonos y 0 de 1878 matrículas que continuaron; retrospectivo.
    """
    from predictivo import asistencia_materia as am
    if not 2 <= dias <= 30:
        raise HTTPException(422, 'La racha debe estar entre 2 y 30 días.')
    if gestion is None:
        gestion = db.scalar(select(func.max(m.Gestion.anio)))
    cursos = select(m.Curso.id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id).where(m.Gestion.anio == gestion)
    jornadas = {j.id: j for j in db.scalars(select(m.JornadaClase).where(m.JornadaClase.es_lectiva == True, m.JornadaClase.curso_id.in_(cursos)))}
    diario, horas = {}, {}
    for a in db.scalars(select(m.Asistencia).where(m.Asistencia.curso_id.in_(cursos))):
        if a.jornada_id in jornadas:
            diario[(a.matricula_id, a.jornada_id)] = a.estado
    sesion_jornada = {s.id: s.jornada_id for s in db.scalars(select(m.SesionClase).where(m.SesionClase.dictada == True, m.SesionClase.curso_id.in_(cursos)))}
    for r in db.scalars(select(m.AsistenciaMateria).where(m.AsistenciaMateria.curso_id.in_(cursos))):
        j = sesion_jornada.get(r.sesion_id)
        if j in jornadas:
            horas.setdefault((r.matricula_id, j), []).append(r.estado)
    por_matricula = {}
    for (mat, j) in set(diario) | set(horas):
        por_matricula.setdefault(mat, set()).add(j)
    out = []
    for mat_id, js in por_matricula.items():
        dias_reg = sorted(((jornadas[j].fecha, am.estado_del_dia(diario.get((mat_id, j)), horas.get((mat_id, j), []))) for j in js),
            key=lambda x: x[0])
        r = am.racha_actual(dias_reg)
        if r['racha'] < dias:
            continue
        mat = db.get(m.Matricula, mat_id)
        if mat.fecha_fin is not None and mat.fecha_fin < r['ultimo_registro']:
            continue
        curso, est = db.get(m.Curso, mat.curso_id), db.get(m.Estudiante, mat.estudiante_id)
        out.append({'matricula_id': mat_id, 'estudiante': est.codigo_anonimo, 'curso_id': curso.id, 'curso': f'{curso.grado}° {curso.paralelo}',
            'gestion': gestion, **r})
    out.sort(key=lambda x: (-x['racha'], x['gestion'], x['curso']))
    return {'dias': dias, 'gestion': gestion, 'total': len(out), 'alertas': out,
        'nota': NOTA_INASISTENCIA}


@router.get('/alertas/academicas')
def academicas(gestion: int | None = None, db: Session = Depends(get_db)):
    """Riesgo académico por regla explícita (solo lectura): matrículas con áreas bajo 51 en el 1.er trimestre, calculado con
    las notas registradas en la base (promedio por área), con el estado de su caso si lo tiene."""
    from collections import defaultdict
    from predictivo import desglose as dg, seguimiento as sg
    q = (select(m.Calificacion.matricula_id, m.Materia.sigla, m.Materia.nombre, m.Evaluacion.titulo, m.Calificacion.puntaje, m.Evaluacion.puntaje_maximo,
            m.Gestion.anio, m.Curso.id, m.Curso.grado, m.Curso.paralelo, m.Estudiante.codigo_anonimo, m.Matricula.origen)
        .join(m.Evaluacion, m.Evaluacion.id == m.Calificacion.evaluacion_id).join(m.Periodo, m.Periodo.id == m.Evaluacion.periodo_id)
        .join(m.AsignacionDocente, m.AsignacionDocente.id == m.Evaluacion.asignacion_id).join(m.Materia, m.Materia.id == m.AsignacionDocente.materia_id)
        .join(m.Matricula, m.Matricula.id == m.Calificacion.matricula_id).join(m.Curso, m.Curso.id == m.Matricula.curso_id)
        .join(m.Gestion, m.Gestion.id == m.Curso.gestion_id).join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id)
        .where(m.Periodo.numero == 1, m.Calificacion.estado == 'CALIFICADA', m.Evaluacion.titulo.not_like('Actividad del %'), m.Evaluacion.titulo.not_like('Cierre del %')))
    if gestion is not None:
        q = q.where(m.Gestion.anio == gestion)
    notas, info = defaultdict(lambda: defaultdict(list)), {}
    registros = defaultdict(list)
    for mid, sigla, nombre, titulo, puntaje, maximo, anio, cid, grado, par, codigo, origen in db.execute(q):
        registros[mid].append(((sigla, nombre), titulo, float(puntaje) / float(maximo) * 100))
        info[mid] = (anio, cid, f'{grado}° {par}', grado, codigo, origen)
    for mid, v in registros.items():
        for area, nota in dg.notas_de_area(v):
            notas[mid][area].append(nota)
    # Respaldo: matrículas sin calificaciones T1 registradas pero con notas por área guardadas en un corte (carga histórica).
    qc = (select(m.CortePredictivo.matricula_id, m.CortePredictivo.variables, m.Gestion.anio, m.Curso.id, m.Curso.grado, m.Curso.paralelo,
            m.Estudiante.codigo_anonimo, m.Matricula.origen)
        .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id).join(m.Curso, m.Curso.id == m.Matricula.curso_id)
        .join(m.Gestion, m.Gestion.id == m.Curso.gestion_id).join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id))
    if gestion is not None:
        qc = qc.where(m.Gestion.anio == gestion)
    for mid, variables, anio, cid, grado, par, codigo, origen in db.execute(qc):
        ind = (variables or {}).get('indicadores') or {}
        if mid in notas or not any(ind.get(f'{a}_T1') is not None for a in ex.NOMBRES_AREAS):
            continue
        for a, nombre in ex.NOMBRES_AREAS.items():
            if ind.get(f'{a}_T1') is not None:
                notas[mid][(a, nombre)].append(float(ind[f'{a}_T1']))
        info[mid] = (anio, cid, f'{grado}° {par}', grado, codigo, origen)
    casos_ab = sg.casos_abiertos(db, list(notas))
    casos = []
    for mid, por_area in notas.items():
        areas = {k: round(sum(v) / len(v)) for k, v in por_area.items()}
        bajas = sorted(((n, v) for (_, n), v in areas.items() if v < 51), key=lambda x: x[1])
        if not bajas:
            continue
        anio, cid, curso, grado, codigo, origen = info[mid]
        caso = casos_ab.get(mid)
        casos.append({'matricula_id': mid, 'estudiante': codigo, 'origen': origen, 'gestion': anio, 'curso_id': cid, 'curso': curso, 'grado': grado,
            'areas_bajo_51': [{'area': n, 'nota': v} for n, v in bajas], 'promedio_T1': round(sum(areas.values()) / len(areas)),
            'caso': caso and {'id': caso[0], 'estado': caso[1]}, 'reglas': ['RP02'] + (['RP01'] if sum(areas.values()) / len(areas) <= 68 else [])})
    casos.sort(key=lambda c: (-c['gestion'], -len(c['areas_bajo_51']), c['promedio_T1'], c['matricula_id']))
    return {'criterio': REGLA_ACADEMICA, 'total': len(casos), 'sin_caso': sum(1 for c in casos if not c['caso']),
        'gestiones': sorted({c['gestion'] for c in casos}, reverse=True), 'casos': casos}


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


def matriculas_con_abandono(db, matriculas):
    """Matrículas con abandono confirmado (situaciones_escolares), que es la etiqueta real con la que se entrenó."""
    if not matriculas:
        return frozenset()
    return frozenset(db.scalars(select(m.SituacionEscolar.matricula_id).where(m.SituacionEscolar.tipo == 'ABANDONO_CONFIRMADO',
        m.SituacionEscolar.matricula_id.in_(set(matriculas)))))


def lectura(db, corte, indicadores, uso, anio):
    """Ayuda para leer la alerta en lenguaje simple, con cifras de la base: si es un caso histórico y a quiénes se parece."""
    from statistics import median
    filas = db.execute(select(m.CortePredictivo.variables, m.CortePredictivo.matricula_id, m.Matricula.estudiante_id)
        .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .where(m.CortePredictivo.version_variables == corte.version_variables)).all()
    abandonos = matriculas_con_abandono(db, [f[1] for f in filas])
    propio = db.get(m.Matricula, corte.matricula_id)
    datos = [(((v or {}).get('indicadores') or {}), mat in abandonos, est) for v, mat, est in filas]
    datos = [(ind.get('promedio_T1'), ind.get('n_areas_bajo_51_T1'), ab, est) for ind, ab, est in datos if ind.get('promedio_T1') is not None]
    historico = uso == 'RETROSPECTIVO_EN_ENTRENAMIENTO'
    abandono = corte.matricula_id in abandonos
    if historico and abandono:
        caso = dict(tipo='historico_abandono', titulo=f'Caso histórico: este estudiante abandonó en {anio}.',
            texto='Esta matrícula se usó para entrenar el modelo; por eso su prioridad es alta. La alerta muestra que el modelo '
                'reconoce el caso. No requiere acción: sirve como ejemplo de cómo eran los estudiantes que abandonaron.')
    elif historico:
        caso = dict(tipo='historico_continuo', titulo=f'Caso histórico: este estudiante no abandonó en {anio}.',
            texto='Esta matrícula se usó para entrenar el modelo y aun así quedó marcada: es una falsa alarma. No requiere acción.')
    else:
        caso = dict(tipo='actual', titulo=f'Gestión actual ({anio}): la escuela todavía puede actuar.',
            texto='Revise el caso con el docente y la familia antes de decidir una acción.')
    ab = [d for d in datos if d[2]]
    continuaron = [d[0] for d in datos if not d[2]]
    texto = ['La prioridad no mide si las notas son malas: mide cuánto se parece el estudiante a los que abandonaron en años anteriores.']
    if ab and continuaron:
        aceptable = sum(1 for d in ab if 51 <= d[0] <= 68 and not d[1])
        texto.append(f'De los {len(ab)} estudiantes que abandonaron, {aceptable} tenían un promedio de desarrollo aceptable (51 a 68) '
            f'y ninguna área por debajo de 51. El estudiante típico que continuó tiene {median(continuaron):g} de promedio.')
    prom = indicadores.get('promedio_T1')
    if prom is not None:
        lo, hi = prom - 2, prom + 2
        cerca = [d for d in datos if lo <= d[0] <= hi and d[3] != propio.estudiante_id]
        if cerca:
            texto.append(f'Este estudiante tiene {prom:g}. Entre los demás estudiantes con promedio de {lo:g} a {hi:g}, '
                f'{sum(1 for d in cerca if d[2])} de {len(cerca)} abandonaron.')
        else:
            texto.append(f'Este estudiante tiene {prom:g}. No hay otros estudiantes con promedio de {lo:g} a {hi:g}.')
    if not historico:
        texto.append('Qué hacer: conversar con el docente y la familia para saber si hay señales recientes (inasistencias, cambio '
            'de domicilio, situación familiar). La alerta orienta la revisión; no es un diagnóstico.')
    return dict(caso=caso, como_leer=texto, abandono_confirmado=abandono)


def indicadores_de(db, *condiciones):
    rows = db.scalars(select(m.CortePredictivo.variables).join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).where(*condiciones)).all()
    return [(v or {}).get('indicadores') or {} for v in rows]


@router.get('/alertas/{alert_id}/explicacion')
def explicacion(alert_id: int, db: Session = Depends(get_db)):
    """Por qué la alerta tiene ese nivel: todos los aportes del modelo, en lenguaje claro y comparados con el curso."""
    row = obtener(db, alert_id)
    alerta, pred, modelo, corte, curso, gestion = row[:6]
    if modelo.version.startswith('seguimiento'):
        from predictivo import seguimiento as sg
        try:
            curso_hoy = sg.calcular(db, gestion.anio, corte.fecha_corte, solo_cursos=[curso.id])['alertas']
            return sg.explicar(corte, pred, float(modelo.umbral_medio), float(modelo.umbral_alto), f'{curso.grado}° {curso.paralelo}', gestion.anio,
                companeros=[a['indicadores'] for a in curso_hoy if a['matricula_id'] != corte.matricula_id],
                vigente=next((a['indicadores'] for a in curso_hoy if a['matricula_id'] == corte.matricula_id), None),
                dia_regla=sg.dia_de_la_regla(db, db.get(m.Matricula, corte.matricula_id), corte.fecha_corte))
        except LookupError as error:
            raise HTTPException(503, str(error))
    try:
        model = ex.cargar_modelo(modelo.artefacto_uri, modelo.artefacto_sha256)
    except (OSError, ValueError) as error:
        raise HTTPException(503, f'No se pudo cargar el modelo registrado para explicar la alerta: {error}')
    indicadores = (corte.variables or {}).get('indicadores') or {}
    contrib, base = ex.aportes(model, indicadores)
    misma_version = m.CortePredictivo.version_variables == corte.version_variables
    otros = m.CortePredictivo.id != corte.id
    return {**ex.construir(indicadores, contrib, base, float(pred.probabilidad), pred.nivel, float(modelo.umbral_medio),
        float(modelo.umbral_alto), indicadores_de(db, m.Curso.id == curso.id, misma_version, otros),
        indicadores_de(db, m.Curso.gestion_id == gestion.id, misma_version, otros), ranking(db, [row])[alerta.id],
        f'{curso.grado}° {curso.paralelo}', gestion.anio),
        **lectura(db, corte, indicadores, (pred.factores or {}).get('uso'), gestion.anio)}


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
