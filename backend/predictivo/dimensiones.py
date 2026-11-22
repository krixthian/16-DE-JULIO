"""Variables de riesgo agrupadas en dimensiones (observación del docente revisor, 22/11/2026).

Las 9 notas por área no son 9 riesgos distintos: forman UNA dimensión académica. Lo mismo con la asistencia,
el seguimiento (citaciones, convivencia) y el contexto. Esta clasificación es la que usan la pantalla
"Resultados del modelo" y el documento, para que ambos digan lo mismo.

- Modelo actual (real-t1-v1): 19 variables que existen en los registros históricos 2021-2025.
- Sistema (primaria-materia-v2): variables que el sistema calcula desde sus módulos; se usarán para reentrenar
  cuando la escuela acumule registros (los históricos no traen asistencia por materia ni citaciones).
"""
from predictivo.explicacion import GRUPOS

DIMENSIONES = {
    'academica': ('Académica', 'Rendimiento en las áreas: notas, promedio, nota más baja, áreas reprobadas, evolución y tareas.'),
    'asistencia': ('Asistencia', 'Faltas, atrasos y licencias; porcentaje de asistencia por materia y licencias parciales.'),
    'seguimiento': ('Seguimiento y convivencia', 'Citaciones por origen (docente de materia, dirección, orientación) e incidentes de convivencia.'),
    'contexto': ('Contexto del estudiante', 'Edad, grado, género y ficha de permanencia escolar.'),
}

# Modelo actual: dimensión de cada una de las 19 variables, a partir de su grupo.
_GRUPO_A_DIMENSION = {'Notas por área': 'academica', 'Rendimiento general': 'academica',
    'Asistencia y puntualidad': 'asistencia', 'Datos del estudiante': 'contexto'}


def dimension_modelo(variable):
    return _GRUPO_A_DIMENSION[GRUPOS[variable]]


def dimension_sistema(variable):
    """Dimensión de una variable de predictivo/features.py (versión primaria-materia-v2)."""
    if variable.startswith(('citaciones_', 'materias_con_citacion', 'incidentes_', 'contexto_reuniones_', 'contexto_contactos_',
            'contexto_acuerdos_')):
        return 'seguimiento'
    if variable.startswith('contexto_') or variable in ('grado', 'antiguedad_contexto_dias'):
        return 'contexto'
    if variable.startswith(('jornadas_', 'asistencia', 'cobertura_asistencia', 'proporcion_faltas', 'proporcion_atrasos', 'racha_',
            'clases_materia', 'materias_asistencia', 'dias_licencia')):
        return 'asistencia'
    return 'academica'
