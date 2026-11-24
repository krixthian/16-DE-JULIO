"""Agregados para el panel analítico. Todo sale de la base; sin datos personales de estudiantes."""
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from api.alertas import seguimiento, NOTA_PRIORIDAD
from database import get_db
import models as m

router = APIRouter(prefix='/dashboard', tags=['Panel analítico'], dependencies=[Depends(seguimiento)])
# Escala de valoración de primaria (Ley 070).
BANDAS = (('ED', 'En desarrollo (≤ 50)', 0, 50), ('DA', 'Desarrollo aceptable (51-68)', 51, 68),
    ('DO', 'Desarrollo óptimo (69-84)', 69, 84), ('DP', 'Desarrollo pleno (85-100)', 85, 100))
GRUPOS_INTERVENCION = {'PROPUESTA': 'PENDIENTE', 'APROBADA': 'PENDIENTE', 'EN_CURSO': 'PENDIENTE', 'REALIZADA': 'EJECUTADA',
    'CANCELADA': 'CANCELADA'}


def banda(valor):
    return next(code for code, _, low, high in BANDAS if valor <= high or code == 'DP')


def base(gestion=None):
    query = (select(m.Prediccion, m.CortePredictivo, m.Curso, m.Gestion)
        .join(m.CortePredictivo, m.CortePredictivo.id == m.Prediccion.corte_id)
        .join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id))
    modelo = select(func.max(m.ModeloPredictivo.id)).scalar_subquery()
    query = query.where(m.Prediccion.modelo_id == modelo)
    return query.where(m.Gestion.anio == gestion) if gestion else query


def modelo_umbrales(db):
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    return modelo and {'medio': float(modelo.umbral_medio), 'alto': float(modelo.umbral_alto)}


@router.get('')
def panel(gestion: int | None = None, db: Session = Depends(get_db)):
    filas = db.execute(base(gestion)).all()
    alertas = {a.prediccion_id: a for a in db.scalars(select(m.Alerta).where(m.Alerta.prediccion_id.in_([p.id for p, *_ in filas])))}
    por_curso, distribucion, n_grado = defaultdict(Counter), defaultdict(Counter), Counter()
    matriculas_curso = Counter((g.anio, curso.grado, curso.paralelo) for _, _, curso, g in filas)
    uso = Counter()
    for p, corte, curso, g in filas:
        if p.id in alertas:
            uso['actual' if (p.factores or {}).get('uso') in ('COHORTE_ACTUAL', 'SEGUIMIENTO_A_LA_FECHA') else 'retrospectiva'] += 1
        promedio = ((corte.variables or {}).get('indicadores') or {}).get('promedio_T1')
        if promedio is not None:
            distribucion[curso.grado][banda(promedio)] += 1
            n_grado[curso.grado] += 1
        if p.id in alertas:
            por_curso[(g.anio, curso.grado, curso.paralelo)][p.nivel] += 1
    # Casos: todos los de la gestión, aunque se hayan abierto con un modelo anterior (igual que Alertas y Reportes).
    todos = (select(m.Alerta).join(m.Prediccion, m.Prediccion.id == m.Alerta.prediccion_id)
        .join(m.CortePredictivo, m.CortePredictivo.id == m.Prediccion.corte_id).join(m.Matricula, m.Matricula.id == m.CortePredictivo.matricula_id)
        .join(m.Curso, m.Curso.id == m.Matricula.curso_id).join(m.Gestion, m.Gestion.id == m.Curso.gestion_id))
    casos = db.scalars(todos.where(m.Gestion.anio == gestion) if gestion else todos).all()
    ids = [a.id for a in casos]
    con_intervencion = set(db.scalars(select(m.Intervencion.alerta_id).where(m.Intervencion.alerta_id.in_(ids)))) if ids else set()
    estados_int = Counter()
    if ids:
        for estado, total in db.execute(select(m.Intervencion.estado, func.count()).where(m.Intervencion.alerta_id.in_(ids))
                .group_by(m.Intervencion.estado)):
            estados_int[GRUPOS_INTERVENCION[estado]] += total
    evolucion = defaultdict(lambda: {'predicciones': 0, 'MEDIO': 0, 'ALTO': 0, 'retrospectiva': False})
    todas = db.execute(base()).all()
    con_alerta = set(db.scalars(select(m.Alerta.prediccion_id)))
    for p, _, _, g in todas:
        evolucion[g.anio]['predicciones'] += 1
        evolucion[g.anio]['retrospectiva'] |= (p.factores or {}).get('uso') == 'RETROSPECTIVO_EN_ENTRENAMIENTO'
        if p.id in con_alerta:
            evolucion[g.anio][p.nivel] += 1
    estados_alerta = Counter(a.estado for a in casos)
    niveles = Counter(p.nivel for p, *_ in filas if p.id in alertas)
    bajo = sum(1 for p, *_ in filas if p.nivel == 'BAJO')
    return {
        'gestion': gestion, 'gestiones': sorted(evolucion), 'nota': NOTA_PRIORIDAD,
        'gestiones_con_matricula': sorted(set(db.scalars(select(m.Gestion.anio).join(m.Curso, m.Curso.gestion_id == m.Gestion.id)
            .join(m.Matricula, m.Matricula.curso_id == m.Curso.id)))),
        'umbrales': modelo_umbrales(db),
        'resumen': {'predicciones': len(filas), 'casos': len(casos), 'alertas': len(alertas), 'alto': niveles['ALTO'], 'medio': niveles['MEDIO'], 'bajo': bajo,
            'tasa_alerta': round(len(alertas) / len(filas), 4) if filas else 0, 'retrospectivas': uso['retrospectiva'],
            'cohorte_actual': uso['actual'], 'con_intervencion': len(con_intervencion), 'sin_intervencion': len(casos) - len(con_intervencion),
            'intervenciones_pendientes': estados_int['PENDIENTE'], 'intervenciones_ejecutadas': estados_int['EJECUTADA'],
            'alertas_cerradas': estados_alerta['CERRADA'], 'cursos_con_alerta': len(por_curso), 'cursos': len(matriculas_curso)},
        'alertas_por_curso': [{'gestion': k[0], 'curso': f'{k[1]}° {k[2]}', 'grado': k[1], 'ALTO': v['ALTO'], 'MEDIO': v['MEDIO'],
            'matriculas': matriculas_curso[k]} for k, v in sorted(por_curso.items(), key=lambda kv: (-kv[0][0], kv[0][1], kv[0][2]))],
        'cursos': [{'id': c.id, 'curso': f'{c.grado}° {c.paralelo}', 'gestion': g.anio} for c, g in sorted(
            {curso.id: (curso, g) for _, _, curso, g in filas}.values(), key=lambda x: (x[1].anio, x[0].grado, x[0].paralelo))],
        'bandas': [{'codigo': c, 'etiqueta': e} for c, e, *_ in BANDAS],
        'promedio_por_grado': [{'grado': gr, 'n': n_grado[gr], **{c: distribucion[gr][c] for c, *_ in BANDAS}} for gr in sorted(n_grado)],
        'evolucion': [{'gestion': anio, **v} for anio, v in sorted(evolucion.items())],
        'intervenciones': {k: estados_int[k] for k in ('PENDIENTE', 'EJECUTADA', 'CANCELADA')},
        'estados_alerta': {k: estados_alerta[k] for k in ('NUEVA', 'EN_REVISION', 'EN_SEGUIMIENTO', 'CERRADA')},
    }


@router.get('/semaforo')
def semaforo(gestion: int, db: Session = Depends(get_db)):
    """Alerta combinada de todos los estudiantes de la gestión a su última fecha registrada: los mismos números que Alertas."""
    from predictivo import perfil as pf, seguimiento as sg
    try:
        r = sg.calcular(db, gestion)
    except LookupError as e:
        raise HTTPException(404, str(e))
    cursos, bandas = {}, defaultdict(Counter)
    for a in r['alertas']:
        c = cursos.setdefault(a['curso_id'], {'id': a['curso_id'], 'curso': a['curso'], 'gestion': gestion, 'total': 0, **dict.fromkeys(pf.NIVELES, 0)})
        c['total'] += 1
        c[a['perfil']['nivel']] += 1
        promedio = a['indicadores'].get('promedio_T1')
        if promedio is not None:
            bandas[int(a['curso'].split('°')[0])][banda(promedio)] += 1
    return {'gestion': gestion, 'fecha': r['fecha'], 'total': r['total'], 'simulada': any(a['origen'] == 'SIMULADO' for a in r['alertas']),
        'niveles': {k: sum(c[k] for c in cursos.values()) for k in pf.NIVELES}, 'nota': pf.NOTA,
        'cursos': sorted(cursos.values(), key=lambda c: c['curso']),
        'promedio_por_grado': [{'grado': g, 'n': sum(bandas[g].values()), **{c: bandas[g][c] for c, *_ in BANDAS}} for g in sorted(bandas)]}


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def _mediana(valores):
    from statistics import median
    valores = [v for v in valores if v is not None]
    return round(float(median(valores)), 2) if valores else None


def filas_registros(db):
    """Una fila por matrícula 2021-2025 (origen distinto de SIMULADO) con las notas de cada área y la asistencia del 1.er
    trimestre, leídas de evaluaciones, calificaciones y asistencias. La nota del área es su nota trimestral oficial."""
    from predictivo.explicacion import NOMBRES_AREAS
    base_q = (select(m.Matricula.id, m.Gestion.anio, m.Curso.grado).join(m.Curso, m.Curso.id == m.Matricula.curso_id)
        .join(m.Gestion, m.Gestion.id == m.Curso.gestion_id).where(m.Matricula.origen != 'SIMULADO'))
    filas = {mid: dict(gestion=anio, grado_curso=grado, notas=[], dias=Counter()) for mid, anio, grado in db.execute(base_q)}
    for mid, titulo, puntaje, maximo in db.execute(select(m.Calificacion.matricula_id, m.Evaluacion.titulo, m.Calificacion.puntaje, m.Evaluacion.puntaje_maximo)
            .join(m.Evaluacion, m.Evaluacion.id == m.Calificacion.evaluacion_id).join(m.Periodo, m.Periodo.id == m.Evaluacion.periodo_id)
            .where(m.Periodo.numero == 1, m.Calificacion.estado == 'CALIFICADA', m.Evaluacion.titulo.like('Nota %trimestre - %'))):
        area = titulo.rsplit(' - ', 1)[-1]
        if mid in filas and area in NOMBRES_AREAS:
            filas[mid][f'{area}_T1'] = float(puntaje) / float(maximo) * 100
            filas[mid]['notas'].append(filas[mid][f'{area}_T1'])
    for mid, estado, n in db.execute(select(m.Asistencia.matricula_id, m.Asistencia.estado, func.count())
            .join(m.JornadaClase, m.JornadaClase.id == m.Asistencia.jornada_id).join(m.Curso, m.Curso.id == m.JornadaClase.curso_id)
            .join(m.Periodo, (m.Periodo.gestion_id == m.Curso.gestion_id) & (m.Periodo.numero == 1))
            .where(m.JornadaClase.es_lectiva == True, m.JornadaClase.fecha >= m.Periodo.fecha_inicio, m.JornadaClase.fecha <= m.Periodo.fecha_fin)
            .group_by(m.Asistencia.matricula_id, m.Asistencia.estado)):
        if mid in filas:
            filas[mid]['dias'][estado] += n
    for mid, x in filas.items():
        notas, dias = x.pop('notas'), x.pop('dias')
        total = sum(dias.values())
        x.update(matricula_id=mid, promedio_T1=sum(notas) / len(notas) if notas else None)
        if total:
            x.update(faltas_T1=dias['FALTA'], atrasos_T1=dias['ATRASO'], licencias_T1=dias['LICENCIA'],
                tasa_asistencia_T1=(dias['PRESENTE'] + dias['ATRASO']) / total)
    return list(filas.values())


@router.get('/dataset')
def dataset(db: Session = Depends(get_db)):
    """Análisis descriptivo del dataset real: desbalance, abandono por gestión y grado, y desglose por materia.

    Variables del corte T1 (cortes_predictivos del modelo vigente) y etiqueta registrada en situaciones_escolares
    (ABANDONO_CONFIRMADO). Es descriptivo: con pocos abandonos, una diferencia no prueba una causa.
    """
    from predictivo.explicacion import NOMBRES_AREAS
    abandonos = set(db.scalars(select(m.SituacionEscolar.matricula_id).where(m.SituacionEscolar.tipo == 'ABANDONO_CONFIRMADO')))
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    if modelo is not None and modelo.version.startswith('seguimiento'):
        # El modelo vigente solo guarda los casos abiertos: el análisis usa todas las matrículas registradas.
        filas = [dict(x, abandono=x['matricula_id'] in abandonos) for x in filas_registros(db)]
    else:
        filas = []
        for p, corte, curso, g in db.execute(base()).all():
            ind = (corte.variables or {}).get('indicadores') or {}
            filas.append(dict(ind, gestion=g.anio, grado_curso=curso.grado, abandono=corte.matricula_id in abandonos))
    if not filas:
        return {'resumen': None}
    sal, sig = [f for f in filas if f['abandono']], [f for f in filas if not f['abandono']]

    def conteo(clave):
        out = defaultdict(lambda: [0, 0])
        for f in filas:
            out[f[clave]][0] += 1
            out[f[clave]][1] += f['abandono']
        return [{'valor': k, 'matriculas': v[0], 'abandonos': v[1]} for k, v in sorted(out.items())]

    materias = []
    for codigo, nombre in [*NOMBRES_AREAS.items(), ('promedio', 'Promedio del 1.er trimestre')]:
        col = 'promedio_T1' if codigo == 'promedio' else f'{codigo}_T1'
        bandas = []
        for b, etiqueta, low, high in BANDAS:
            grupo = [f for f in filas if f.get(col) is not None and banda(int(f[col])) == b]
            bandas.append({'banda': b, 'etiqueta': etiqueta, 'matriculas': len(grupo), 'abandonos': sum(f['abandono'] for f in grupo)})
        m_sal, m_sig = _media([f.get(col) for f in sal]), _media([f.get(col) for f in sig])
        materias.append({'codigo': codigo, 'materia': nombre, 'media_abandonaron': m_sal, 'media_continuaron': m_sig,
            'mediana_abandonaron': _mediana([f.get(col) for f in sal]), 'mediana_continuaron': _mediana([f.get(col) for f in sig]),
            'diferencia': None if None in (m_sal, m_sig) else round(m_sal - m_sig, 2),
            'bajo_51_abandonaron': sum(1 for f in sal if (f.get(col) or 100) < 51),
            'bajo_51_continuaron': sum(1 for f in sig if (f.get(col) or 100) < 51), 'bandas': bandas})
    rangos = [(0, 50), (51, 55), (56, 60), (61, 65), (66, 70), (71, 75), (76, 80), (81, 85), (86, 100)]
    histograma = [{'rango': f'{a}-{b}' if a else f'≤ {b}', 'continuaron': sum(1 for f in sig if f.get('promedio_T1') is not None and a <= int(f['promedio_T1']) <= b),
        'abandonaron': sum(1 for f in sal if f.get('promedio_T1') is not None and a <= int(f['promedio_T1']) <= b)} for a, b in rangos]
    asistencia = [{'variable': k, 'etiqueta': e, 'abandonaron': _media([f.get(k) for f in sal]), 'continuaron': _media([f.get(k) for f in sig]),
        'mediana_abandonaron': _mediana([f.get(k) for f in sal]), 'mediana_continuaron': _mediana([f.get(k) for f in sig])}
        for k, e in (('faltas_T1', 'Faltas en T1'), ('atrasos_T1', 'Atrasos en T1'), ('licencias_T1', 'Licencias en T1'),
            ('tasa_asistencia_T1', 'Tasa de asistencia'))]
    return {
        'resumen': {'matriculas': len(filas), 'abandonos': len(sal), 'continuaron': len(sig),
            'tasa_abandono': round(len(sal) / len(filas), 4), 'proporcion': f'1 de cada {round(len(filas) / len(sal))}' if sal else None},
        'por_gestion': conteo('gestion'), 'por_grado': conteo('grado_curso'),
        'materias': sorted(materias, key=lambda r: (r['codigo'] != 'promedio', r['diferencia'] if r['diferencia'] is not None else 0)),
        'histograma_promedio': histograma, 'asistencia': asistencia, 'bandas': [{'codigo': c, 'etiqueta': e} for c, e, *_ in BANDAS],
        'nota': ('Análisis descriptivo de las matrículas 2021-2025 (archivos proporcionados por la institución) al corte del 1.er trimestre. Con pocos abandonos, una diferencia '
            'entre grupos no prueba que una materia cause el abandono.'),
        'fuente': 'Base de datos: calificaciones y asistencias del 1.er trimestre y situaciones_escolares (ABANDONO_CONFIRMADO).',
    }
