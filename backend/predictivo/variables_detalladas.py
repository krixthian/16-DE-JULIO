"""Variables detalladas del 1.er trimestre (febrero a abril) desde los registros pedagógicos originales.

Responden a la observación del docente revisor: en lugar de totales trimestrales, miran CÓMO evoluciona el
estudiante dentro del trimestre (asistencia día por día y notas actividad por actividad) e incorporan la
dimensión cualitativa SER (respeto, interés, asistencia a clases) y la autoevaluación.
Todas usan solo información disponible al 30 de abril: no hay fuga de información.
"""
from statistics import mean, pstdev

from predictivo.registros_pedagogicos import AREAS

# Puntaje máximo de cada actividad por dimensión (encabezados del registro: SER/5, SABER/45, HACER/40, DECIDIR/5).
MAXIMO = {'SER': 5, 'SABER': 45, 'HACER': 40, 'DECIDIR': 5}
ASISTE = ('A', 'R')

DESCRIPCIONES = {
    'faltas_feb': 'Proporción de días con falta en febrero.',
    'faltas_abr': 'Proporción de días con falta en abril.',
    'tendencia_faltas': 'Pendiente semanal de la proporción de faltas (positiva = falta cada vez más).',
    'faltas_ultimas_4_semanas': 'Proporción de faltas en las últimas 4 semanas del trimestre.',
    'cambio_faltas_final_inicio': 'Faltas de las últimas 4 semanas menos las de las primeras 4 (proporción).',
    'racha_max_faltas': 'Mayor cantidad de días seguidos con falta.',
    'racha_final_faltas': 'Días seguidos con falta al cierre del trimestre (0 si el último día asistió).',
    'faltas_lunes_viernes': 'Proporción de las faltas que caen en lunes o viernes (vacío si no tiene faltas).',
    'retrasos_ultimas_4_semanas': 'Proporción de días con retraso en las últimas 4 semanas.',
    'ser_media': 'Dimensión SER (respeto, interés, asistencia a clases): media de los indicadores, 0 a 1.',
    'ser_minimo': 'Indicador de SER más bajo entre las áreas, 0 a 1.',
    'saber_media': 'Dimensión SABER: media de las evaluaciones de conocimiento, 0 a 1.',
    'hacer_media': 'Dimensión HACER: media de las actividades prácticas, 0 a 1.',
    'decidir_media': 'Dimensión DECIDIR: media, 0 a 1.',
    'autoevaluacion_media': 'Autoevaluación del estudiante (0 a 10), media de las áreas.',
    'tendencia_actividades': 'Pendiente media de las notas de SABER y HACER de una actividad a la siguiente (negativa = cae).',
    'areas_en_caida': 'Áreas cuya última actividad está 10 puntos (de 100) o más por debajo de la primera.',
    'actividades_bajas': 'Actividades de SABER y HACER con menos del 51 % del puntaje.',
    'dispersion_areas': 'Desviación estándar de las notas trimestrales entre áreas (rendimiento desigual).',
}
NOMBRES = list(DESCRIPCIONES)


def _pendiente(y):
    n = len(y)
    if n < 2:
        return None
    x = range(n)
    mx, my = (n - 1) / 2, mean(y)
    den = sum((i - mx) ** 2 for i in x)
    return sum((i - mx) * (v - my) for i, v in zip(x, y)) / den if den else None


def _prop(codigos, valor):
    return sum(c == valor for c in codigos) / len(codigos) if codigos else None


def asistencia(registros):
    """registros: [(fecha, código)] ordenados de febrero a abril."""
    if not registros:
        return {k: None for k in NOMBRES if k in ('faltas_feb', 'faltas_abr', 'tendencia_faltas', 'faltas_ultimas_4_semanas',
            'cambio_faltas_final_inicio', 'racha_max_faltas', 'racha_final_faltas', 'faltas_lunes_viernes', 'retrasos_ultimas_4_semanas')}
    codigos = [c for _, c in registros]
    por_mes = {m: [c for d, c in registros if d.month == m] for m in (2, 4)}
    semanas = {}
    for d, c in registros:
        semanas.setdefault(d.isocalendar()[:2], []).append(c)
    tasas = [_prop(v, 'F') for _, v in sorted(semanas.items())]
    ultimas, primeras = codigos[-20:], codigos[:20]  # ~4 semanas de clases
    racha = maximo = 0
    for c in codigos:
        racha = racha + 1 if c == 'F' else 0
        maximo = max(maximo, racha)
    faltas = [d for d, c in registros if c == 'F']
    return dict(
        faltas_feb=_prop(por_mes[2], 'F'), faltas_abr=_prop(por_mes[4], 'F'), tendencia_faltas=_pendiente(tasas),
        faltas_ultimas_4_semanas=_prop(ultimas, 'F'), cambio_faltas_final_inicio=_prop(ultimas, 'F') - _prop(primeras, 'F'),
        racha_max_faltas=maximo, racha_final_faltas=racha,
        faltas_lunes_viernes=sum(d.weekday() in (0, 4) for d in faltas) / len(faltas) if faltas else None,
        retrasos_ultimas_4_semanas=_prop(ultimas, 'R'))


def notas(areas):
    """areas: {área: salida de registros_pedagogicos.notas_t1 para un estudiante}."""
    def norm(dim):
        return [v / MAXIMO[dim] for a in areas.values() for v in a.get(dim, [])]
    ser = norm('SER')
    tendencias, caidas, bajas = [], 0, 0
    for a in areas.values():
        secuencia = [v / MAXIMO['SABER'] for v in a.get('SABER', [])] + [v / MAXIMO['HACER'] for v in a.get('HACER', [])]
        for dim in ('SABER', 'HACER'):
            p = _pendiente([v / MAXIMO[dim] for v in a.get(dim, [])])
            if p is not None:
                tendencias.append(p)
        if len(secuencia) >= 2 and secuencia[-1] <= secuencia[0] - .10:
            caidas += 1
        bajas += sum(v < .51 for v in secuencia)
    notas_area = [a['nota'] for a in areas.values() if a.get('nota') is not None]
    autos = [a['autoevaluacion'] for a in areas.values() if a.get('autoevaluacion') is not None]
    media = lambda xs: mean(xs) if xs else None
    return dict(
        ser_media=media(ser), ser_minimo=min(ser) if ser else None, saber_media=media(norm('SABER')), hacer_media=media(norm('HACER')),
        decidir_media=media(norm('DECIDIR')), autoevaluacion_media=media(autos), tendencia_actividades=media(tendencias),
        areas_en_caida=caidas if areas else None, actividades_bajas=bajas if areas else None,
        dispersion_areas=pstdev(notas_area) if len(notas_area) > 1 else None)


def calcular(estudiante):
    return {**asistencia(estudiante['asistencia']), **notas(estudiante['areas'])}
