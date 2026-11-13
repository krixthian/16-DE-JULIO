"""Explicación completa de una predicción: aporte de cada variable (SHAP), lectura en lenguaje claro,
comparación con el curso y la gestión, y por qué quedó en su nivel.

Los aportes salen del mismo modelo registrado (se verifica su SHA-256) y suman exactamente el puntaje
guardado: punto de partida + suma de aportes = puntaje del modelo (en escala logit).
"""
import hashlib
import math
from functools import lru_cache

from predictivo.real_t1 import AREAS, FEATURE_NAMES

NOMBRES_AREAS = {'CNAT': 'Ciencias Naturales', 'LCO': 'Comunicación y Lenguajes', 'SOC': 'Ciencias Sociales',
    'APV': 'Artes Plásticas y Visuales', 'EFI': 'Educación Física', 'EMU': 'Educación Musical', 'MAT': 'Matemática',
    'TTG': 'Técnica Tecnológica', 'VER': 'Valores, Espiritualidad y Religiones'}
ETIQUETAS = {**{f'{a}_T1': NOMBRES_AREAS[a] for a in AREAS},
    'promedio_T1': 'Promedio del 1.er trimestre', 'nota_minima_T1': 'Nota más baja', 'n_areas_bajo_51_T1': 'Áreas con nota menor a 51',
    'faltas_T1': 'Faltas', 'atrasos_T1': 'Atrasos', 'licencias_T1': 'Licencias', 'tasa_asistencia_T1': 'Asistencia',
    'edad_31marzo': 'Edad al 31 de marzo', 'grado': 'Grado', 'genero_f': 'Género'}
NOTAS = {f'{a}_T1' for a in AREAS} | {'promedio_T1', 'nota_minima_T1'}
GRUPOS = {**{f'{a}_T1': 'Notas por área' for a in AREAS}, 'promedio_T1': 'Rendimiento general', 'nota_minima_T1': 'Rendimiento general',
    'n_areas_bajo_51_T1': 'Rendimiento general', 'faltas_T1': 'Asistencia y puntualidad', 'atrasos_T1': 'Asistencia y puntualidad',
    'licencias_T1': 'Asistencia y puntualidad', 'tasa_asistencia_T1': 'Asistencia y puntualidad',
    'edad_31marzo': 'Datos del estudiante', 'grado': 'Datos del estudiante', 'genero_f': 'Datos del estudiante'}


def banda(nota):
    """Escala de valoración de primaria (Ley 070)."""
    if nota <= 50:
        return 'En desarrollo'
    if nota <= 68:
        return 'Desarrollo aceptable'
    if nota <= 84:
        return 'Desarrollo óptimo'
    return 'Desarrollo pleno'


def texto_valor(variable, valor):
    if valor is None:
        return 'sin dato'
    if variable in NOTAS:
        return f'{valor:g} · {banda(valor).lower()}'
    if variable == 'tasa_asistencia_T1':
        return f'{valor * 100:.0f} %'
    if variable == 'edad_31marzo':
        return f'{valor:g} años'
    if variable == 'grado':
        return f'{valor:g}.º de primaria'
    if variable == 'genero_f':
        return 'Femenino' if valor == 1 else 'Masculino'
    return f'{valor:g}'


def coma(valor, decimales=3):
    return f'{valor:.{decimales}f}'.replace('.', ',')


def texto_comparado(variable, valor, media):
    """Comparación breve con el promedio del curso, sin juicios sobre variables personales."""
    if valor is None or media is None or variable in ('genero_f', 'grado'):
        return None
    if variable == 'tasa_asistencia_T1':
        return f'curso: {media * 100:.0f} %'
    return f'curso: {media:.1f}'.replace('.', ',')


@lru_cache(maxsize=4)
def cargar_modelo(ruta, sha256):
    import xgboost as xgb
    with open(ruta, 'rb') as handle:
        if hashlib.sha256(handle.read()).hexdigest() != sha256:
            raise ValueError('El archivo del modelo no coincide con el hash registrado.')
    model = xgb.XGBClassifier()
    model.load_model(ruta)
    return model


def aportes(model, indicadores):
    """Aporte SHAP de cada variable y punto de partida, en escala logit."""
    import numpy as np
    import xgboost as xgb
    fila = np.array([[np.nan if indicadores.get(n) is None else float(indicadores[n]) for n in FEATURE_NAMES]])
    contrib = model.get_booster().predict(xgb.DMatrix(fila, feature_names=FEATURE_NAMES), pred_contribs=True)[0]
    return {n: float(v) for n, v in zip(FEATURE_NAMES, contrib[:-1])}, float(contrib[-1])


def sigmoide(x):
    return 1 / (1 + math.exp(-x))


def media(filas, variable):
    valores = [f[variable] for f in filas if f.get(variable) is not None]
    return sum(valores) / len(valores) if valores else None


def construir(indicadores, contrib, base, puntaje_guardado, nivel, umbral_medio, umbral_alto, curso, gestion, puesto, curso_txt, anio):
    """Arma la explicación completa. `curso` y `gestion` son listas de indicadores de los demás cortes."""
    puntaje = sigmoide(base + sum(contrib.values()))
    variables = []
    for n in FEATURE_NAMES:
        valor, aporte = indicadores.get(n), contrib[n]
        media_curso = media(curso, n)
        variables.append(dict(variable=n, etiqueta=ETIQUETAS[n], grupo=GRUPOS[n], valor=valor, valor_texto=texto_valor(n, valor),
            media_curso=media_curso, media_gestion=media(gestion, n), comparacion=texto_comparado(n, valor, media_curso),
            aporte=round(aporte, 4), efecto='sube' if aporte > 0.005 else 'baja' if aporte < -0.005 else 'neutro'))
    variables.sort(key=lambda v: -abs(v['aporte']))
    suben = [v for v in variables if v['efecto'] == 'sube']
    bajan = [v for v in variables if v['efecto'] == 'baja']
    total_sube = sum(v['aporte'] for v in suben) or 1
    for v in suben:
        v['peso_relativo'] = round(100 * v['aporte'] / total_sube, 1)
    if nivel == 'ALTO':
        motivo = (f'Su puntaje ({coma(puntaje_guardado)}) supera el umbral de prioridad ALTA ({coma(umbral_alto, 1)}). '
            f'Es el puesto {puesto[0]} de {puesto[1]} en {anio}.')
    elif nivel == 'MEDIO':
        motivo = (f'Su puntaje ({coma(puntaje_guardado)}) supera el umbral de alerta ({coma(umbral_medio, 1)}) pero no el de '
            f'prioridad ALTA ({coma(umbral_alto, 1)}). Es el puesto {puesto[0]} de {puesto[1]} en {anio}.')
    else:
        motivo = f'Su puntaje ({coma(puntaje_guardado)}) está por debajo del umbral de alerta ({coma(umbral_medio, 1)}).'
    principales = ', '.join(f"{v['etiqueta'].lower() if v['grupo'] != 'Notas por área' else v['etiqueta']} ({v['valor_texto']})"
        for v in suben[:3])
    resumen = f'Lo que más eleva la prioridad: {principales}.' if suben else 'Ninguna variable eleva la prioridad.'
    if bajan:
        resumen += ' Lo que la reduce: ' + ', '.join(f"{v['etiqueta'].lower() if v['grupo'] != 'Notas por área' else v['etiqueta']}"
            f" ({v['valor_texto']})" for v in bajan[:2]) + '.'
    criticas = [v for v in variables if v['variable'] in {f'{a}_T1' for a in AREAS} and v['valor'] is not None and v['valor'] < 51]
    return dict(
        nivel=dict(nivel=nivel, puntaje=round(puntaje_guardado, 6), umbral_medio=umbral_medio, umbral_alto=umbral_alto,
            puesto=puesto[0], de=puesto[1], motivo=motivo,
            nota='El puntaje no está calibrado: ordena la prioridad de revisión, no es la probabilidad real de abandono.'),
        resumen=resumen, curso=curso_txt, gestion=anio, estudiantes_en_curso=len(curso) + 1,
        areas_en_desarrollo=[dict(etiqueta=v['etiqueta'], valor=v['valor']) for v in criticas],
        punto_partida=round(sigmoide(base), 6), puntaje_recalculado=round(puntaje, 6),
        coincide_con_guardado=abs(puntaje - puntaje_guardado) < 1e-5, variables=variables,
        metodo=('Aportes SHAP del modelo XGBoost registrado, en escala logit: punto de partida + suma de aportes = puntaje. '
            'El punto de partida es alto porque el modelo se entrenó con scale_pos_weight; los datos del estudiante lo suben o lo bajan.'),
        advertencia=('Los aportes muestran lo que el modelo aprendió con 11 abandonos: algunos pueden ser poco intuitivos '
            '(por ejemplo, una nota baja que no eleva la prioridad). Úsalos como orientación junto con el criterio docente.'))
