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


@router.get('')
def panel(gestion: int | None = None, db: Session = Depends(get_db)):
    filas = db.execute(base(gestion)).all()
    alertas = {a.prediccion_id: a for a in db.scalars(select(m.Alerta).where(m.Alerta.prediccion_id.in_([p.id for p, *_ in filas])))}
    por_curso, distribucion, n_grado = defaultdict(Counter), defaultdict(Counter), Counter()
    for p, corte, curso, g in filas:
        promedio = ((corte.variables or {}).get('indicadores') or {}).get('promedio_T1')
        if promedio is not None:
            distribucion[curso.grado][banda(promedio)] += 1
            n_grado[curso.grado] += 1
        if p.id in alertas:
            por_curso[(g.anio, curso.grado, curso.paralelo)][p.nivel] += 1
    ids = [a.id for a in alertas.values()]
    estados_int = Counter()
    if ids:
        for estado, total in db.execute(select(m.Intervencion.estado, func.count()).where(m.Intervencion.alerta_id.in_(ids))
                .group_by(m.Intervencion.estado)):
            estados_int[GRUPOS_INTERVENCION[estado]] += total
    evolucion = defaultdict(lambda: {'predicciones': 0, 'MEDIO': 0, 'ALTO': 0})
    todas = db.execute(base()).all()
    con_alerta = set(db.scalars(select(m.Alerta.prediccion_id)))
    for p, _, _, g in todas:
        evolucion[g.anio]['predicciones'] += 1
        if p.id in con_alerta:
            evolucion[g.anio][p.nivel] += 1
    estados_alerta = Counter(a.estado for a in alertas.values())
    niveles = Counter(p.nivel for p, *_ in filas if p.id in alertas)
    return {
        'gestion': gestion, 'gestiones': sorted(evolucion), 'nota': NOTA_PRIORIDAD,
        'resumen': {'predicciones': len(filas), 'alertas': len(alertas), 'alto': niveles['ALTO'], 'medio': niveles['MEDIO'],
            'intervenciones_pendientes': estados_int['PENDIENTE'], 'intervenciones_ejecutadas': estados_int['EJECUTADA'],
            'alertas_cerradas': estados_alerta['CERRADA']},
        'alertas_por_curso': [{'gestion': k[0], 'curso': f'{k[1]}° {k[2]}', 'grado': k[1], 'ALTO': v['ALTO'], 'MEDIO': v['MEDIO']}
            for k, v in sorted(por_curso.items())],
        'cursos': [{'id': c.id, 'curso': f'{c.grado}° {c.paralelo}', 'gestion': g.anio} for c, g in sorted(
            {curso.id: (curso, g) for _, _, curso, g in filas}.values(), key=lambda x: (x[1].anio, x[0].grado, x[0].paralelo))],
        'bandas': [{'codigo': c, 'etiqueta': e} for c, e, *_ in BANDAS],
        'promedio_por_grado': [{'grado': gr, 'n': n_grado[gr], **{c: distribucion[gr][c] for c, *_ in BANDAS}} for gr in sorted(n_grado)],
        'evolucion': [{'gestion': anio, **v} for anio, v in sorted(evolucion.items())],
        'intervenciones': {k: estados_int[k] for k in ('PENDIENTE', 'EJECUTADA', 'CANCELADA')},
        'estados_alerta': {k: estados_alerta[k] for k in ('NUEVA', 'EN_REVISION', 'EN_SEGUIMIENTO', 'CERRADA')},
    }
