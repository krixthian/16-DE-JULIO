"""Notas desglosadas por dimensión (Ser, Saber, Hacer, Decidir, autoevaluación): variables para el modelo.

Las 8 variables se fijaron el 23/11/2026, ANTES de entrenar o ver algún resultado con ellas, y salen de la misma función
para el entrenamiento y para el sistema. Las del 1.er trimestre se conocen a su cierre y el cambio, al cierre del 2.º;
nada del T3 ni anual (sería fuga). Una casilla sin nota no cuenta como cero. Los archivos de origen no traen la fecha de
cada actividad y su procedencia no está verificada (docs/CONSISTENCIA_REGISTROS.md).
"""
import re
from collections import defaultdict

import numpy as np

# Dimensión -> puntaje máximo en el cuaderno (las actividades que registre el docente pueden usar otra escala).
DIMENSIONES = {'Ser': 5, 'Saber': 45, 'Hacer': 40, 'Decidir': 5, 'Autoevaluación': 10}
CIERRE = re.compile(r'^(Nota|Cierre) (parcial )?del (\d)')  # nota de cierre de un trimestre, no una actividad
NOTA = re.compile(r'^Nota (parcial )?del (\d)')  # nota trimestral del área sobre 100
VARIABLES = {
    'ser_T1': 'Ser: promedio de las áreas (1.er trimestre)', 'saber_T1': 'Saber: promedio de las áreas (1.er trimestre)',
    'hacer_T1': 'Hacer: promedio de las áreas (1.er trimestre)', 'decidir_T1': 'Decidir: promedio de las áreas (1.er trimestre)',
    'autoevaluacion_T1': 'Autoevaluación: promedio de las áreas (1.er trimestre)',
    'dimension_minima_T1': 'Dimensión más baja (1.er trimestre)',
    'bajas_T1': 'Notas de Saber o Hacer por debajo de 51 (1.er trimestre)',
    'cambio_saber_hacer': 'Cambio de Saber y Hacer del 1.er al 2.º trimestre'}
_T1 = {'ser_T1': 'Ser', 'saber_T1': 'Saber', 'hacer_T1': 'Hacer', 'decidir_T1': 'Decidir', 'autoevaluacion_T1': 'Autoevaluación'}


def _por_area(registros):
    """[(área, dimensión, nota sobre 100)] -> {dimensión: [promedio de cada área]}."""
    agrupado = defaultdict(list)
    for area, dimension, nota in registros:
        if dimension in DIMENSIONES and nota is not None:
            agrupado[(dimension, area)].append(nota)
    out = defaultdict(list)
    for (dimension, _), v in agrupado.items():
        out[dimension].append(float(np.mean(v)))
    return out


def variables(t1, t2=None):
    """Las 8 variables (escala 0-100). `t1`/`t2`: registros del trimestre, o None si todavía no cerró."""
    out = dict.fromkeys(VARIABLES)
    a = _por_area(t1 or [])
    for nombre, dimension in _T1.items():
        if a.get(dimension):
            out[nombre] = float(np.mean(a[dimension]))
    cuatro = [out[k] for k in ('ser_T1', 'saber_T1', 'hacer_T1', 'decidir_T1') if out[k] is not None]
    if cuatro:
        out['dimension_minima_T1'] = min(cuatro)
    sh1 = a.get('Saber', []) + a.get('Hacer', [])
    if sh1:
        out['bajas_T1'] = int(sum(x < 51 for x in sh1))
    b = _por_area(t2 or [])
    cambios = [np.mean(b[d]) - np.mean(a[d]) for d in ('Saber', 'Hacer') if a.get(d) and b.get(d)]
    if cambios:
        out['cambio_saber_hacer'] = float(np.mean(cambios))
    return out


def con_desglose(d, csv):
    """Agrega a la tabla mensual de armar() las 8 variables: las de T1 desde abril y el cambio a T2 desde agosto."""
    import pandas as pd
    t = pd.read_csv(csv)
    assert set(t.trimestre) == {1, 2}
    reg = {}
    for r in t.itertuples(index=False):
        reg.setdefault((r.codigo_anonimo, r.gestion), {1: [], 2: []})[r.trimestre].append((r.area, r.dimension, r.puntaje / r.maximo * 100))
    filas = []
    for c, g, m in zip(d.codigo_anonimo, d.gestion, d.mes):
        x = reg.get((c, g), {1: [], 2: []})
        filas.append(variables(x[1] if m >= 4 else None, x[2] if m >= 8 else None))
    return pd.concat([d.reset_index(drop=True), pd.DataFrame(filas, columns=list(VARIABLES)).astype(float)], axis=1)


ARCHIVO = re.compile(r'^Actividad del (\d)')  # actividad de los archivos recibidos: sin fecha propia


def redundantes(evaluaciones):
    """Ids de las actividades que ya están dentro de la nota de cierre de su dimensión Y de la nota del área: no se
    vuelven a contar. evaluaciones: objetos con id, asignacion_id, periodo_id, dimension y titulo."""
    areas = {(e.asignacion_id, e.periodo_id) for e in evaluaciones if NOTA.match(e.titulo)}
    dims = {(e.asignacion_id, e.periodo_id, e.dimension) for e in evaluaciones if e.dimension and CIERRE.match(e.titulo)}
    return {e.id for e in evaluaciones if e.dimension and not CIERRE.match(e.titulo)
        and (e.asignacion_id, e.periodo_id) in areas and (e.asignacion_id, e.periodo_id, e.dimension) in dims}


def notas_de_area(registros):
    """registros: [(clave, título, nota)] de un trimestre. Si una clave tiene su nota trimestral, vale solo esa: sus
    dimensiones y actividades ya están dentro de ella. Si no la tiene, se usan sus actividades. -> [(clave, nota)]."""
    por = defaultdict(list)
    for clave, titulo, nota in registros:
        por[clave].append((bool(NOTA.match(titulo)), nota))
    out = []
    for clave, v in por.items():
        oficiales = [n for es, n in v if es]
        out += [(clave, n) for n in (oficiales or [n for _, n in v])]
    return out
