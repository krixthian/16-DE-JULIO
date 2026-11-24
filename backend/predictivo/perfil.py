"""Perfil de riesgo por dimensiones: regla pedagógica PROPUESTA, no una predicción.

Cortes fijados el 23/11/2026 ANTES de contar a quién marcan: 51 es el límite de "En desarrollo" (Ley 070); 10 % de faltas o
atrasos y 3 faltas en 20 días son los de las reglas RP03 y RP04; 5 faltas seguidas, la alerta inmediata. Los demás (2 áreas,
4 notas, 60 puntos, caída de 10 y 5 % de faltas) son criterio propio por validar con docentes y Dirección.

Nivel de la alerta combinada: las tres dimensiones de notas NO se cuentan tres veces (en los archivos alertan juntas) y 5
faltas seguidas es urgente sin depender de lo demás. El modelo XGBoost no se reentrena: su puntaje ordena dentro de cada
nivel y, si marca a alguien que el perfil deja en verde, lo pasa a amarillo para que no se pierda.
"""
DIMENSIONES = ('Académica', 'Desempeño', 'Actitud', 'Asistencia')


def _num(v):
    return None if v is None or v != v else float(v)


def _color(rojo, amarillo, hay):
    return None if not hay else 'ROJO' if rojo else 'AMARILLO' if amarillo else 'VERDE'


def dimensiones(v):
    """v: las 23 variables del seguimiento. Devuelve {dimensión: ROJO/AMARILLO/VERDE/None (sin dato)}."""
    g = {k: _num(x) for k, x in v.items()}
    m = lambda k: g.get(k)
    si = lambda k, f: m(k) is not None and f(m(k))
    caida = m('promedio_T2') is not None and m('promedio_T1') is not None and m('promedio_T2') - m('promedio_T1') <= -10
    return {
        'Académica': _color(si('n_areas_bajo_51_T1', lambda x: x >= 2), si('n_areas_bajo_51_T1', lambda x: x == 1) or caida, m('promedio_T1') is not None),
        'Desempeño': _color(si('bajas_T1', lambda x: x >= 4), si('bajas_T1', lambda x: x >= 1) or si('cambio_saber_hacer', lambda x: x <= -10), m('saber_T1') is not None),
        'Actitud': _color(si('ser_T1', lambda x: x < 51) or si('decidir_T1', lambda x: x < 51), si('ser_T1', lambda x: x < 60) or si('decidir_T1', lambda x: x < 60), m('ser_T1') is not None),
        'Asistencia': _color(si('prop_faltas', lambda x: x >= .10) or si('racha_actual', lambda x: x >= 5),
            si('prop_faltas', lambda x: x >= .05) or si('faltas_ult20', lambda x: x >= 3) or si('prop_retrasos', lambda x: x >= .10), m('prop_faltas') is not None)}



NIVELES = ('URGENTE', 'ROJO', 'AMARILLO', 'VERDE')
NOTAS = DIMENSIONES[:3]
NOTA = ('Regla pedagógica propuesta, por validar con Dirección: señala a quién apoyar y por qué; no predice quién abandonará.')


def alerta(v, nivel_modelo='BAJO', racha_alerta=5):
    """Alerta combinada: {'nivel', 'colores' por dimensión, 'motivos', 'notas_y_asistencia'} (esta va primero dentro de ROJO)."""
    c = dimensiones(v)
    peso = {'ROJO': 2, 'AMARILLO': 1}
    notas, asis = max(peso.get(c[k], 0) for k in NOTAS), peso.get(c['Asistencia'], 0)
    motivos = [dict(dimension=k, color=c[k]) for k in DIMENSIONES if c[k] in peso]
    racha = _num(v.get('racha_actual'))
    juntas = bool(notas and asis and max(notas, asis) == 2)
    if racha is not None and racha >= racha_alerta:
        nivel = 'URGENTE'
    elif max(notas, asis) == 2:
        nivel = 'ROJO'
    elif notas or asis:
        nivel = 'AMARILLO'
    elif nivel_modelo in ('ALTO', 'MEDIO'):
        nivel = 'AMARILLO'
        motivos = [dict(dimension='Modelo XGBoost', color='AMARILLO')]
    else:
        nivel = 'VERDE'
    return dict(nivel=nivel, colores=c, motivos=motivos, notas_y_asistencia=juntas and nivel == 'ROJO')


def texto(p):
    return ', '.join(f"{x['dimension']} ({x['color'].lower()})" for x in p['motivos']) or 'sin motivos'
