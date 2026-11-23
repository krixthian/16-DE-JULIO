"""Construye el dataset consolidado DIRECTAMENTE desde los registros pedagógicos de la institución.

Contexto (22/11/2026): la institución entregó la versión completa de los registros 2021-2024 (los 18 paralelos de
cada gestión), que difiere de la versión parcial usada antes. Este módulo arma, para cada estudiante y gestión:
- las mismas columnas del dataset consolidado anterior (notas T1 por área, promedio, nota mínima, áreas < 51, faltas,
  atrasos, licencias, días asistidos y lectivos, edad, género, resultados POST_* y etiquetas), y
- las variables DESGLOSADAS del 1.er trimestre (por materia y dimensión, su evolución y la asistencia día por día),
  pedidas por el revisor ("solo valores globales").

Privacidad: de la hoja de filiación solo se leen el género y la fecha de nacimiento (no carnet, RUDE, teléfono ni
dirección). El nombre se usa solo en memoria para vincular al mismo estudiante entre gestiones y asignar un código
anónimo; nunca se escribe en la salida.
Trimestres según el calendario de los registros: T1 febrero-abril, T2 mayo-agosto, T3 septiembre-noviembre.
"""
import math
from datetime import date, datetime
from pathlib import Path
from statistics import mean, pstdev

from predictivo import registros_pedagogicos as rp, variables_detalladas as vd

T1, T2, T3 = (2, 3, 4), (5, 6, 7, 8), (9, 10, 11)
NOTA_ABANDONO = 18  # nota con la que el registro marca a quien dejó de asistir


def _txt(v):
    return '' if v is None else ' '.join(str(v).split())


def redondeo(x):
    """Redondeo del cuaderno (mitad hacia arriba)."""
    return int(math.floor(x + .5))


def _tabla(ws):
    filas = list(ws.iter_rows(values_only=True))
    h = next(i for i, f in enumerate(filas) if f and _txt(f[0]).upper().startswith('N°'))
    return filas, h


def filiacion(wb):
    """{orden: (género, fecha_nacimiento)}; no lee carnet, RUDE, teléfono ni dirección."""
    filas, h = _tabla(wb['FILIACION'])
    out = {}
    for f in filas[h + 1:]:
        if f and isinstance(f[0], (int, float)) and _txt(f[1]):
            nac = f[5]
            if isinstance(nac, str):
                try:
                    nac = datetime.strptime(nac.strip()[:10], '%d/%m/%Y')
                except ValueError:
                    nac = None
            out[int(f[0])] = (_txt(f[2]).upper()[:1] or None, nac.date() if isinstance(nac, datetime) else nac)
    return out


def nombres(wb):
    """{orden: nombre normalizado} desde la hoja de marzo (solo para vincular en memoria)."""
    filas, h = _tabla(wb['MAR'])
    return {int(f[0]): _txt(f[1]).upper() for f in filas[h + 1:] if f and isinstance(f[0], (int, float)) and _txt(f[1])}


def centralizador(wb):
    """{orden: {área: (nota T1, nota T2, nota T3, anual)}} desde las hojas CENTRA <ÁREA>."""
    out = {}
    for area in rp.AREAS:
        nombre = f'CENTRA {area}'
        if nombre not in wb.sheetnames:
            continue
        filas, h = _tabla(wb[nombre])
        for f in filas[h + 1:]:
            if f and isinstance(f[0], (int, float)) and _txt(f[1]):
                num = lambda j: float(f[j]) if j < len(f) and isinstance(f[j], (int, float)) else None
                out.setdefault(int(f[0]), {})[area] = (num(11), num(14), num(17), num(19))
    return out


def leer_registro(ruta):
    import openpyxl
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    gestion, grado, paralelo = rp.curso(wb)
    t1_detalle = {a: rp.notas_t1(wb, a) for a in rp.AREAS if f'{a} 1' in wb.sheetnames}
    anual = rp.asistencia_anual(wb, gestion)
    out = dict(gestion=gestion, grado=grado, paralelo=paralelo, fuente=f'REGISTRO-INSTITUCION-{gestion}',
        nombres=nombres(wb), filiacion=filiacion(wb), centra=centralizador(wb), detalle=t1_detalle, asistencia=anual,
        dias=sorted({d for v in anual.values() for d, _ in v}))
    wb.close()
    return out


def _conteo(registros, meses, codigos):
    return sum(1 for d, c in registros if d.month in meses and c in codigos)


def fila(reg, orden):
    """Una fila del dataset (sin nombre) para el estudiante `orden` del registro."""
    g = reg['gestion']
    asis = reg['asistencia'].get(orden, [])
    centra = reg['centra'].get(orden, {})
    genero, nac = reg['filiacion'].get(orden, (None, None))
    t1 = {a: centra[a][0] for a in rp.AREAS if a in centra and centra[a][0] is not None}
    if len(t1) != len(rp.AREAS):  # respaldo: nota trimestral de la hoja del área
        t1.update({a: reg['detalle'][a][orden]['nota'] for a in rp.AREAS if a not in t1 and orden in reg['detalle'].get(a, {})})
    t2 = [centra[a][1] for a in rp.AREAS if a in centra and centra[a][1] is not None]
    t3 = [centra[a][2] for a in rp.AREAS if a in centra and centra[a][2] is not None]
    anual = [centra[a][3] for a in rp.AREAS if a in centra and centra[a][3] is not None]
    dias_t1 = [d for d in reg['dias'] if d.month in T1]
    asistio = lambda meses: _conteo(asis, meses, ('A', 'R'))  # vino al colegio (con o sin retraso)
    asistidos = lambda meses: _conteo(asis, meses, ('A',))  # 'días asistidos' del cuaderno: solo A
    prom2 = redondeo(mean(t2)) if t2 else None
    prom3 = redondeo(mean(t3)) if t3 else None
    abandono = int(asistio(T3) == 0 or (prom3 is not None and prom3 <= NOTA_ABANDONO))
    caida = None
    if abandono:
        caida = 'T2' if (prom2 is not None and prom2 <= NOTA_ABANDONO) or asistio(T2) == 0 else 'T3'
    edad = None
    if isinstance(nac, date):
        corte = date(g, 3, 31)
        edad = corte.year - nac.year - ((corte.month, corte.day) < (nac.month, nac.day))
    notas = [t1[a] for a in rp.AREAS if a in t1]
    out = dict(gestion=g, grado=reg['grado'], paralelo=reg['paralelo'], genero=genero, edad_31marzo=edad,
        **{f'{a}_T1': t1.get(a) for a in rp.AREAS},
        **{f'POST_{a}_T2': centra[a][1] if a in centra else None for a in rp.AREAS},
        **{f'POST_{a}_T3': centra[a][2] if a in centra else None for a in rp.AREAS},
        promedio_T1=redondeo(mean(notas)) if notas else None, nota_minima_T1=min(notas) if notas else None,
        n_areas_bajo_51_T1=sum(n < 51 for n in notas) if notas else None,
        faltas_T1=_conteo(asis, T1, ('F',)), atrasos_T1=_conteo(asis, T1, ('R',)), licencias_T1=_conteo(asis, T1, ('L',)),
        dias_asistidos_T1=asistidos(T1), dias_lectivos_T1=len(dias_t1),
        POST_promedio_T2=prom2, POST_promedio_T3=prom3, POST_dias_asistidos_T2=asistidos(T2), POST_dias_asistidos_T3=asistidos(T3),
        POST_promedio_anual=redondeo(mean(anual)) if anual else None, POST_n_areas_reprobadas=sum(x < 51 for x in anual) if anual else None,
        y_abandono_intra_anual=abandono, trimestre_caida=caida,
        y_reprobacion=int(any(x < 51 for x in anual)) if anual else None, fuente=reg['fuente'])
    # Variables detalladas agregadas (asistencia día por día y dimensiones) y desglose por materia.
    est = {'asistencia': [(d, c) for d, c in asis if d.month in T1],
        'areas': {a: reg['detalle'][a][orden] for a in rp.AREAS if orden in reg['detalle'].get(a, {})}}
    out.update(vd.calcular(est))
    out.update(desglose_materias(est['areas']))
    return out


def desglose_materias(areas):
    """Por cada área: SER, SABER, HACER, DECIDIR (0 a 1), autoevaluación (0 a 1), tendencia de las actividades y
    actividades bajas. Son las variables 'por materia' que pidió el revisor."""
    out = {}
    for a in rp.AREAS:
        n = areas.get(a, {})
        for dim in rp.DIMENSIONES:
            vals = n.get(dim, [])
            out[f'{a}_{dim.lower()}'] = mean(v / vd.MAXIMO[dim] for v in vals) if vals else None
        out[f'{a}_auto'] = n['autoevaluacion'] / 10 if n.get('autoevaluacion') is not None else None
        seq = [v / vd.MAXIMO['SABER'] for v in n.get('SABER', [])] + [v / vd.MAXIMO['HACER'] for v in n.get('HACER', [])]
        out[f'{a}_tendencia'] = vd._pendiente(seq)
        out[f'{a}_bajas'] = sum(v < .51 for v in seq) if seq else None
    return out


DESGLOSE = [f'{a}_{s}' for a in rp.AREAS for s in ('ser', 'saber', 'hacer', 'decidir', 'auto', 'tendencia', 'bajas')]
