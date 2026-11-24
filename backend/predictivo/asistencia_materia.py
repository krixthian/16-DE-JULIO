"""Asistencia por materia, licencia parcial y citaciones por origen (funciones puras, sin acceso a la base).

Observación del docente revisor (22/11/2026): la asistencia no puede analizarse de forma plana. Cada materia tiene
una frecuencia semanal distinta (Religión 1 vez, Lenguaje varias), así que el porcentaje se calcula por materia:
clases asistidas / clases registradas de ESA materia. Un registro ausente es desconocido, no una falta.
"""
from collections import defaultdict

ASISTE = ('PRESENTE', 'ATRASO')
UMBRAL_MATERIA = .8  # criterio técnico inicial para "asistencia baja en una materia"; requiere validación institucional


def por_materia(sesiones, registros):
    """sesiones: dicts con id, materia_id, dictada. registros: dicts con sesion_id y estado (de UNA matrícula).
    Devuelve {materia_id: {dictadas, observadas, presentes, atrasos, faltas, licencias, porcentaje}}."""
    dictadas = {s['id']: s for s in sesiones if s['dictada']}
    out = defaultdict(lambda: dict(dictadas=0, observadas=0, presentes=0, atrasos=0, faltas=0, licencias=0, porcentaje=None))
    for s in dictadas.values():
        out[s['materia_id']]['dictadas'] += 1
    for r in registros:
        s = dictadas.get(r['sesion_id'])
        if s is None:
            continue
        m = out[s['materia_id']]
        m['observadas'] += 1
        m[{'PRESENTE': 'presentes', 'ATRASO': 'atrasos', 'FALTA': 'faltas', 'LICENCIA': 'licencias'}[r['estado']]] += 1
    for m in out.values():
        m['porcentaje'] = (m['presentes'] + m['atrasos']) / m['observadas'] if m['observadas'] else None
    return dict(out)


MINIMO_CLASES = 8  # con menos clases registradas en la materia no se juzga (una falta en Religión no debe alertar)


def senales(sesiones, registros, citaciones, nombres):
    """Señales por materia para la alerta combinada (regla propuesta; el modelo no las usa). La licencia no cuenta ni a favor
    ni en contra: porcentaje = asistidas / (registradas - licencias). None = sin registro por materia o sin citaciones."""
    bajas, hay = [], False
    for mid, x in por_materia(sesiones, registros).items():
        n = x['observadas'] - x['licencias']
        if n < MINIMO_CLASES:
            continue
        hay = True
        p = (x['presentes'] + x['atrasos']) / n
        if p < UMBRAL_MATERIA:
            bajas.append((p, nombres.get(mid, 'materia')))
    por = defaultdict(int)
    for c in citaciones:
        por[c['materia_id']] += 1
    externas = por.pop(None, 0)
    mayor = max(por.items(), key=lambda kv: kv[1], default=(None, 0))
    return dict(materias_asistencia_baja=len(bajas) if hay else None,
        materias_bajas_detalle=(', '.join(f'{n} {p * 100:.0f} %' for p, n in sorted(bajas)[:3]) + (f' y {len(bajas) - 3} más' if len(bajas) > 3 else '')) or None,
        citaciones_max_una_materia=mayor[1] if citaciones else None,
        citaciones_materia_detalle=f'{mayor[1]} citaciones en {nombres.get(mayor[0], "una materia")}' if mayor[1] else None,
        citaciones_direccion_orientacion=externas if citaciones else None)


def licencias_parciales(sesiones, registros):
    """Días en que el estudiante asistió a una o más horas y después tuvo licencia (llegó y se retiró)."""
    por_sesion = {s['id']: s for s in sesiones if s['dictada']}
    dias = defaultdict(list)
    for r in registros:
        s = por_sesion.get(r['sesion_id'])
        if s is not None:
            dias[s['jornada_id']].append((s['periodo'], r['estado']))
    total = 0
    for horas in dias.values():
        horas.sort()
        primera_asistencia = next((p for p, e in horas if e in ASISTE), None)
        if primera_asistencia is not None and any(e == 'LICENCIA' and p > primera_asistencia for p, e in horas):
            total += 1
    return total


def estado_del_dia(diario, horas):
    """Estado de un día para la alerta de inasistencia continua.
    diario: estado de la asistencia diaria (o None). horas: estados por hora (asistencia por materia) de ese día.
    Devuelve 'FALTA', 'ASISTE', 'LICENCIA' o None (sin registro). La asistencia diaria manda si existe."""
    if diario is not None:
        return 'ASISTE' if diario in ASISTE else diario
    if not horas:
        return None
    if any(e in ASISTE for e in horas):
        return 'ASISTE'
    return 'FALTA' if all(e == 'FALTA' for e in horas) else 'LICENCIA'


def racha_actual(dias):
    """dias: [(fecha, estado_del_dia)] ordenados. Racha de FALTAS seguidas al final del registro, desde cuándo y la
    última fecha en que asistió. Los días sin registro se omiten (no cortan ni suman la racha)."""
    conocidos = [(f, e) for f, e in dias if e is not None]
    racha, desde = 0, None
    for f, e in reversed(conocidos):
        if e != 'FALTA':
            break
        racha, desde = racha + 1, f
    ultima = max((f for f, e in conocidos if e == 'ASISTE'), default=None)
    return dict(racha=racha, desde=desde, ultima_asistencia=ultima, ultimo_registro=conocidos[-1][0] if conocidos else None)


def indicadores(sesiones, registros, citaciones):
    """Indicadores condensados para el modelo; cada uno es None si no hay registros que lo sustenten."""
    materias = por_materia(sesiones, registros)
    pct = [m['porcentaje'] for m in materias.values() if m['porcentaje'] is not None]
    por_origen = defaultdict(int)
    por_materia_cit = defaultdict(int)
    for c in citaciones:
        por_origen[c['origen']] += 1
        if c.get('materia_id') is not None:
            por_materia_cit[c['materia_id']] += 1
    observadas = sum(m['observadas'] for m in materias.values())
    return dict(
        clases_materia_observadas=observadas,
        asistencia_materia_media=sum(pct) / len(pct) if pct else None,
        asistencia_materia_minima=min(pct) if pct else None,
        materias_asistencia_baja=sum(p < UMBRAL_MATERIA for p in pct) if pct else None,
        dias_licencia_parcial=licencias_parciales(sesiones, registros) if observadas else None,
        citaciones_total=len(citaciones),
        citaciones_direccion=por_origen['DIRECCION'],
        citaciones_orientacion=por_origen['ORIENTACION'],
        citaciones_docente_materia=por_origen['DOCENTE_MATERIA'],
        materias_con_citacion=len(por_materia_cit),
        citaciones_max_una_materia=max(por_materia_cit.values()) if por_materia_cit else 0,
    )


DESCRIPCIONES = {
    'clases_materia_observadas': 'Clases (horas) con asistencia por materia registrada hasta el corte.',
    'asistencia_materia_media': 'Media de los porcentajes de asistencia de cada materia (cada materia pesa igual, sin importar cuántas clases tenga por semana).',
    'asistencia_materia_minima': 'Porcentaje de asistencia de la materia con menor asistencia.',
    'materias_asistencia_baja': f'Materias con asistencia menor a {UMBRAL_MATERIA:.0%} (criterio técnico inicial).',
    'dias_licencia_parcial': 'Días en que asistió a una o más horas y luego tuvo licencia en horas siguientes.',
    'citaciones_total': 'Citaciones registradas hasta el corte (cero = ninguna registrada).',
    'citaciones_direccion': 'Citaciones originadas por dirección.',
    'citaciones_orientacion': 'Citaciones originadas por orientación.',
    'citaciones_docente_materia': 'Citaciones originadas por un docente por su materia.',
    'materias_con_citacion': 'Cantidad de materias distintas con al menos una citación.',
    'citaciones_max_una_materia': 'Mayor cantidad de citaciones en una misma materia (distingue 5 de una materia de 7 repartidas).',
}
