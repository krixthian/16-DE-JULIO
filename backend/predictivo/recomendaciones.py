"""Reglas RP01-RP05: recomendaciones pedagógicas a partir de los indicadores T1 de una alerta.

Propuesta pendiente de validación con docentes y Dirección. Los umbrales siguen la escala de
valoración de primaria (Ley 070: ED 1-50, DA 51-68, DO 69-84, DP 85-100) y percentiles descriptivos
de asistencia de la escuela; no se ajustaron con las etiquetas de abandono.
"""
VERSION = 'RP-v1'
VALIDACION = 'Propuesta pendiente de validación con docentes y Dirección'
AREAS = {'CNAT': 'Ciencias Naturales', 'LCO': 'Comunicación y Lenguajes', 'SOC': 'Ciencias Sociales',
    'APV': 'Artes Plásticas y Visuales', 'EFI': 'Educación Física', 'EMU': 'Educación Musical', 'MAT': 'Matemática',
    'TTG': 'Técnica Tecnológica', 'VER': 'Valores, Espiritualidad y Religiones'}
TIPOS_ACCION = {'CITACION': 'Citación al apoderado', 'REFORZAMIENTO': 'Reforzamiento pedagógico', 'ENTREVISTA': 'Entrevista',
    'REUNION_CASO': 'Reunión de caso', 'DERIVACION': 'Derivación', 'OTRA': 'Otra acción'}


def _inasistencia_continua(ind, nivel):
    v = ind.get('racha_actual')
    return v is not None and v >= 5 and f'{v:g} faltas seguidas hasta la fecha'


def _bajo_promedio(ind, nivel):
    v = ind.get('promedio_T1')
    return v is not None and v <= 68 and f'promedio_T1 = {v:g}'


def _areas_bajas(ind, nivel):
    bajas = [f'{AREAS[a]} ({ind[f"{a}_T1"]:g})' for a in AREAS if ind.get(f'{a}_T1') is not None and ind[f'{a}_T1'] < 51]
    if not bajas and ind.get('n_areas_bajo_51_T1'):  # seguimiento: solo se guarda el conteo
        return f"{ind['n_areas_bajo_51_T1']:g} área(s) < 51 en el T1"
    return bool(bajas) and 'Áreas < 51: ' + ', '.join(bajas)


def _inasistencia(ind, nivel):
    faltas, tasa = ind.get('faltas_T1'), ind.get('tasa_asistencia_T1')
    partes = [f'faltas_T1 = {faltas:g}'] if faltas is not None and faltas >= 3 else []
    if tasa is not None and tasa < .90:
        partes.append(f'asistencia = {tasa * 100:.0f} %')
    if ind.get('faltas_ult20') is not None and ind['faltas_ult20'] >= 3:  # seguimiento a la fecha
        partes.append(f"{ind['faltas_ult20']:g} faltas en los últimos 20 días de clase")
    if ind.get('prop_faltas') is not None and ind['prop_faltas'] >= .10:
        partes.append(f"faltas en el año = {ind['prop_faltas'] * 100:.0f} %")
    return bool(partes) and ', '.join(partes)


def _atrasos(ind, nivel):
    v = ind.get('atrasos_T1')
    if v is None and ind.get('prop_retrasos') is not None:  # seguimiento a la fecha
        return ind['prop_retrasos'] >= .10 and f"atrasos = {ind['prop_retrasos'] * 100:.0f} % de los días"
    return v is not None and v >= 4 and f'atrasos_T1 = {v:g}'


REGLAS = [
    dict(codigo='RP00', nombre='Inasistencia continua', condicion='5 o más faltas seguidas hasta la fecha (alerta inmediata)',
        recomendacion='Contactar hoy a la familia (llamada o visita domiciliaria) para conocer la causa y acordar el retorno; '
            'si no hay respuesta en 2 días, informar a Dirección para la reunión de caso.',
        tipo='CITACION', evaluar=_inasistencia_continua),
    dict(codigo='RP01', nombre='Rendimiento global bajo', condicion='promedio_T1 ≤ 68 (por debajo de "Desarrollo óptimo")',
        recomendacion='Plan de reforzamiento con el docente asesor y citación al apoderado para acordar apoyo en casa.',
        tipo='REFORZAMIENTO', evaluar=_bajo_promedio),
    dict(codigo='RP02', nombre='Áreas en desarrollo', condicion='Alguna área con nota < 51 ("En desarrollo")',
        recomendacion='Reforzamiento específico en las áreas indicadas, con tareas graduadas y revisión quincenal.',
        tipo='REFORZAMIENTO', evaluar=_areas_bajas),
    dict(codigo='RP03', nombre='Inasistencia', condicion='faltas_T1 ≥ 3 (≈ percentil 95) o asistencia < 90 %',
        recomendacion='Citación al apoderado para conocer las causas de las faltas y acordar un compromiso de asistencia.',
        tipo='CITACION', evaluar=_inasistencia),
    dict(codigo='RP04', nombre='Atrasos frecuentes', condicion='atrasos_T1 ≥ 4 (≈ percentil 95)',
        recomendacion='Entrevista con el estudiante y el apoderado sobre rutina y traslado; registrar acuerdos de puntualidad.',
        tipo='ENTREVISTA', evaluar=_atrasos),
    dict(codigo='RP05', nombre='Revisión de caso', condicion='Prioridad ALTA, o alerta sin otra regla activa',
        recomendacion='Reunión de caso (docente asesor, orientación y Dirección) para revisar la situación y definir seguimiento.',
        tipo='REUNION_CASO', evaluar=None),
]


def evaluar(indicadores, nivel):
    """Reglas activas para una alerta, con el dato que las dispara. Siempre devuelve al menos RP05."""
    ind = indicadores or {}
    activas = []
    for regla in REGLAS[:-1]:
        dato = regla['evaluar'](ind, nivel)
        if dato:
            activas.append((regla, dato))
    if nivel == 'ALTO' or not activas:
        activas.append((REGLAS[-1], f'nivel = {nivel}' + ('' if nivel == 'ALTO' else ', sin otra regla activa')))
    return [{'codigo': r['codigo'], 'nombre': r['nombre'], 'condicion': r['condicion'], 'dato': dato, 'recomendacion': r['recomendacion'],
        'tipo_accion': r['tipo'], 'regla_version': f"{r['codigo']}@{VERSION}", 'validacion': VALIDACION} for r, dato in activas]
