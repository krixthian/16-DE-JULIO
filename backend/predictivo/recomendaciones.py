"""Reglas RP00-RP10: recomendaciones pedagógicas a partir de los indicadores de una alerta. RP06-RP08 siguen las dimensiones
de predictivo/perfil.py con sus mismos cortes.

Propuesta pendiente de validación con docentes y Dirección. Los umbrales siguen la escala de
valoración de primaria (Ley 070: ED 1-50, DA 51-68, DO 69-84, DP 85-100) y percentiles descriptivos
de asistencia de la escuela; no se ajustaron con las etiquetas de abandono.
"""
from predictivo import perfil as pf

VERSION = 'RP-v2'
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
    t2 = ind.get('promedio_T2')
    partes = [f'promedio_T1 = {v:g}'] if v is not None and v <= 68 else []
    if v is not None and t2 is not None and t2 - v <= -10:
        partes.append(f'el promedio bajó de {v:.0f} a {t2:.0f} en el T2')
    return bool(partes) and ', '.join(partes)


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


def _desempeno(ind, nivel):
    if pf.dimensiones(ind)['Desempeño'] not in ('ROJO', 'AMARILLO'):
        return False
    return pf.detalle(ind, 'Desempeño')


def _actitud(ind, nivel):
    if pf.dimensiones(ind)['Actitud'] not in ('ROJO', 'AMARILLO'):
        return False
    return pf.detalle(ind, 'Actitud')


def _faltas_leves(ind, nivel):
    v = ind.get('prop_faltas')
    return (v is not None and v >= .05 and not _inasistencia(ind, nivel) and not _inasistencia_continua(ind, nivel)
        and f'faltas en el año = {v * 100:.1f} %'.replace('.', ','))


def _por_materia(ind, nivel):
    return bool(ind.get('materias_asistencia_baja')) and f"asistencia por materia: {ind['materias_bajas_detalle']}"


def _citaciones(ind, nivel):
    partes = [ind['citaciones_materia_detalle']] if (ind.get('citaciones_max_una_materia') or 0) >= 3 else []
    if (ind.get('citaciones_direccion_orientacion') or 0) >= 2:
        partes.append(f"{ind['citaciones_direccion_orientacion']:g} citaciones de Dirección u Orientación")
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
    dict(codigo='RP01', nombre='Rendimiento global bajo', condicion='promedio_T1 ≤ 68 (por debajo de "Desarrollo óptimo") o caída de 10 puntos en el T2',
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
    dict(codigo='RP06', nombre='Desempeño en clase', condicion='Dimensión Desempeño en amarillo o rojo (notas de Saber o Hacer < 51, o caída de 10 puntos)',
        recomendacion='El docente revisa las actividades de Saber y Hacer más bajas, da apoyo en clase y evalúa el avance en dos semanas.',
        tipo='REFORZAMIENTO', evaluar=_desempeno),
    dict(codigo='RP07', nombre='Actitud', condicion='Dimensión Actitud en amarillo o rojo (Ser o Decidir < 60)',
        recomendacion='Conversación del docente asesor u Orientación con el estudiante y acuerdo de convivencia o participación.',
        tipo='ENTREVISTA', evaluar=_actitud),
    dict(codigo='RP08', nombre='Faltas leves', condicion='Faltas ≥ 5 % del año, sin llegar a la regla de inasistencia',
        recomendacion='Conversación del docente asesor con el estudiante y aviso a la familia, para prevenir que las faltas aumenten.',
        tipo='ENTREVISTA', evaluar=_faltas_leves),
    dict(codigo='RP09', nombre='Inasistencia en una materia', condicion='Asiste a menos del 80 % de las clases de alguna materia (mínimo 8 clases, sin contar licencias)',
        recomendacion='El docente de la materia conversa con el estudiante para conocer por qué falta a esa clase y acuerda su asistencia; informa al asesor.',
        tipo='ENTREVISTA', evaluar=_por_materia),
    dict(codigo='RP10', nombre='Citaciones repetidas', condicion='3 o más citaciones en una materia, o 2 o más de Dirección u Orientación',
        recomendacion='Revisar los acuerdos de las citaciones anteriores con la familia y coordinar un solo plan entre docente, asesor y Orientación.',
        tipo='REUNION_CASO', evaluar=_citaciones),
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
