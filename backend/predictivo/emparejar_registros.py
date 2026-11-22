"""Empareja los estudiantes de los registros pedagógicos con el dataset anonimizado, SIN usar nombres.

Cada estudiante se identifica por su curso (gestión, grado, paralelo) y sus notas del 1.er trimestre en las 9 áreas,
que ya están en el dataset con su código anónimo. Se exige coincidencia exacta y única; si no, se informa y no se
empareja (no se adivina). Además se verifica que las faltas, retrasos y licencias de febrero a abril del registro
coincidan con los totales del dataset.
"""
from collections import Counter

from predictivo.registros_pedagogicos import AREAS


def clave_notas(areas):
    return tuple(None if areas.get(a, {}).get('nota') is None else int(round(areas[a]['nota'])) for a in AREAS)


def emparejar(registro, dataset):
    """registro: salida de registros_pedagogicos.leer(). dataset: DataFrame DATOS_REAL.
    Devuelve ({orden: codigo_anonimo}, informe)."""
    filas = dataset[(dataset.gestion == registro['gestion']) & (dataset.grado == registro['grado'])
        & (dataset.paralelo.astype(str).str.strip() == str(registro['paralelo']).strip())]
    por_clave = {}
    for _, r in filas.iterrows():
        k = tuple(None if r[f'{a}_T1'] != r[f'{a}_T1'] else int(round(r[f'{a}_T1'])) for a in AREAS)
        por_clave.setdefault(k, []).append(r)
    resultado, problemas, verificados = {}, Counter(), 0
    for orden, e in registro['estudiantes'].items():
        candidatos = por_clave.get(clave_notas(e['areas']), [])
        if len(candidatos) != 1:
            problemas['sin_coincidencia' if not candidatos else 'coincidencia_multiple'] += 1
            continue
        r = candidatos[0]
        cuenta = Counter(c for _, c in e['asistencia'])
        if (cuenta['F'], cuenta['R'], cuenta['L']) == (int(r.faltas_T1), int(r.atrasos_T1), int(r.licencias_T1)):
            verificados += 1
        else:
            problemas['asistencia_distinta'] += 1
        resultado[orden] = r.codigo_anonimo
    usados = Counter(resultado.values())
    if any(n > 1 for n in usados.values()):
        raise ValueError('Dos estudiantes del registro se emparejaron con el mismo código.')
    informe = dict(curso=f"{registro['gestion']} {registro['grado']}° {registro['paralelo']}", en_registro=len(registro['estudiantes']),
        en_dataset=len(filas), emparejados=len(resultado), asistencia_verificada=verificados, **problemas)
    return resultado, informe
