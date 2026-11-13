"""Agregados para el panel analítico. Todo sale de la base; sin datos personales de estudiantes."""
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends
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
            uso['actual' if (p.factores or {}).get('uso') == 'COHORTE_ACTUAL' else 'retrospectiva'] += 1
        promedio = ((corte.variables or {}).get('indicadores') or {}).get('promedio_T1')
        if promedio is not None:
            distribucion[curso.grado][banda(promedio)] += 1
            n_grado[curso.grado] += 1
        if p.id in alertas:
            por_curso[(g.anio, curso.grado, curso.paralelo)][p.nivel] += 1
    ids = [a.id for a in alertas.values()]
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
    estados_alerta = Counter(a.estado for a in alertas.values())
    niveles = Counter(p.nivel for p, *_ in filas if p.id in alertas)
    return {
        'gestion': gestion, 'gestiones': sorted(evolucion), 'nota': NOTA_PRIORIDAD,
        'umbrales': modelo_umbrales(db),
        'resumen': {'predicciones': len(filas), 'alertas': len(alertas), 'alto': niveles['ALTO'], 'medio': niveles['MEDIO'],
            'tasa_alerta': round(len(alertas) / len(filas), 4) if filas else 0, 'retrospectivas': uso['retrospectiva'],
            'cohorte_actual': uso['actual'], 'con_intervencion': len(con_intervencion), 'sin_intervencion': len(alertas) - len(con_intervencion),
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


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def _mediana(valores):
    from statistics import median
    valores = [v for v in valores if v is not None]
    return round(float(median(valores)), 2) if valores else None


@router.get('/dataset')
def dataset(db: Session = Depends(get_db)):
    """Análisis descriptivo del dataset real: desbalance, abandono por gestión y grado, y desglose por materia.

    Variables del corte T1 (cortes_predictivos del modelo vigente) y etiqueta registrada en situaciones_escolares
    (ABANDONO_CONFIRMADO). Es descriptivo: con pocos abandonos, una diferencia no prueba una causa.
    """
    from predictivo.explicacion import NOMBRES_AREAS
    abandonos = set(db.scalars(select(m.SituacionEscolar.matricula_id).where(m.SituacionEscolar.tipo == 'ABANDONO_CONFIRMADO')))
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
            grupo = [f for f in filas if f.get(col) is not None and low <= f[col] <= high]
            bandas.append({'banda': b, 'etiqueta': etiqueta, 'matriculas': len(grupo), 'abandonos': sum(f['abandono'] for f in grupo)})
        m_sal, m_sig = _media([f.get(col) for f in sal]), _media([f.get(col) for f in sig])
        materias.append({'codigo': codigo, 'materia': nombre, 'media_abandonaron': m_sal, 'media_continuaron': m_sig,
            'mediana_abandonaron': _mediana([f.get(col) for f in sal]), 'mediana_continuaron': _mediana([f.get(col) for f in sig]),
            'diferencia': None if None in (m_sal, m_sig) else round(m_sal - m_sig, 2),
            'bajo_51_abandonaron': sum(1 for f in sal if (f.get(col) or 100) < 51),
            'bajo_51_continuaron': sum(1 for f in sig if (f.get(col) or 100) < 51), 'bandas': bandas})
    rangos = [(0, 50), (51, 55), (56, 60), (61, 65), (66, 70), (71, 75), (76, 80), (81, 85), (86, 100)]
    histograma = [{'rango': f'{a}-{b}' if a else f'≤ {b}', 'continuaron': sum(1 for f in sig if a <= (f.get('promedio_T1') or -1) <= b),
        'abandonaron': sum(1 for f in sal if a <= (f.get('promedio_T1') or -1) <= b)} for a, b in rangos]
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
        'nota': ('Análisis descriptivo de las matrículas reales al corte del 1.er trimestre. Con pocos abandonos, una diferencia '
            'entre grupos no prueba que una materia cause el abandono.'),
        'fuente': 'Base de datos: cortes_predictivos (variables T1) y situaciones_escolares (ABANDONO_CONFIRMADO).',
    }
