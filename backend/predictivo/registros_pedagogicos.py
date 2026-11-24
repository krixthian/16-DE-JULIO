"""Lectura de los registros pedagógicos originales (Excel de cada curso) para el 1.er trimestre.

Observación del docente revisor (22/11/2026): el análisis con totales trimestrales es superficial. Los registros
originales tienen la asistencia DÍA POR DÍA (A/F/R/L por fecha) y las notas POR ACTIVIDAD en cada dimensión
(SER, SABER, HACER, DECIDIR, autoevaluación). Este módulo extrae ese detalle de febrero a abril.

Privacidad: no se lee la hoja FILIACIÓN (carnet, RUDE, teléfonos, direcciones) y los nombres no se devuelven.
Cada estudiante se identifica luego por su curso y sus notas trimestrales (emparejamiento con el dataset
anonimizado), así que ningún nombre sale del Excel.
"""
import re
from datetime import date

AREAS = ('CNAT', 'LCO', 'SOC', 'APV', 'EFI', 'EMU', 'MAT', 'TTG', 'VER')
MESES_T1 = {'FEB': 2, 'MAR': 3, 'ABR': 4}
GRADOS = {'PRIMERO': 1, 'SEGUNDO': 2, 'TERCERO': 3, 'CUARTO': 4, 'QUINTO': 5, 'SEXTO': 6}
DIMENSIONES = ('SER', 'SABER', 'HACER', 'DECIDIR')
CODIGOS = {'A', 'F', 'R', 'L'}


def _txt(v):
    return '' if v is None else str(v).strip()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _filas_estudiantes(filas, desde):
    """Filas con número de orden y nombre no vacío a partir de la fila de encabezado 'N°'. Devuelve (orden, fila)."""
    out = []
    for f in filas[desde + 1:]:
        if f and isinstance(f[0], (int, float)) and len(f) > 1 and _txt(f[1]):
            out.append((int(f[0]), f))
    return out


def _encabezado(filas, texto):
    for i, f in enumerate(filas):
        if f and _txt(f[0]).upper().startswith(texto):
            return i
    raise ValueError(f'No se encontró el encabezado {texto!r}.')


def curso(wb):
    """Gestión, grado y paralelo desde la hoja de marzo y el centralizador."""
    mar = list(wb['MAR'].iter_rows(values_only=True))
    grado = paralelo = None
    for f in mar[:6]:
        for j, v in enumerate(f):
            t = _txt(v).upper()
            if t in GRADOS:
                grado = GRADOS[t]
            if t.startswith('PARALELO') and paralelo is None:
                paralelo = next((_txt(x) for x in f[j + 1:] if _txt(x)), None)
    gestion = None
    for nombre in wb.sheetnames:
        if nombre.startswith('CENTRA'):
            for f in list(wb[nombre].iter_rows(values_only=True))[:4]:
                for v in f:
                    if re.fullmatch(r'20\d\d', _txt(v).split('.')[0]):
                        gestion = int(_txt(v).split('.')[0])
            break
    return gestion, grado, paralelo


MESES_ANIO = {'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11}


def asistencia_anual(wb, gestion):
    """{orden: [(fecha, código)]} de febrero a noviembre. Solo para la alerta de inasistencia continua y el análisis
    retrospectivo; el modelo del corte T1 nunca usa meses posteriores a abril."""
    return asistencia_t1(wb, gestion, {h: m for h, m in MESES_ANIO.items() if h in wb.sheetnames})


def asistencia_t1(wb, gestion, meses=MESES_T1):
    """{orden: [(fecha, código)]} de febrero a abril (o los meses indicados), en orden cronológico."""
    out = {}
    for hoja, mes in meses.items():
        filas = list(wb[hoja].iter_rows(values_only=True))
        h = _encabezado(filas, 'N°')
        fechas = {}
        for j, v in enumerate(filas[h]):
            m = re.match(r'^(LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES)\s+(\d{1,2})$', _txt(v).upper())
            if m:
                fechas[j] = date(gestion, mes, int(m[2]))
        for orden, f in _filas_estudiantes(filas, h):
            registros = out.setdefault(orden, [])
            for j, d in fechas.items():
                c = _txt(f[j]).upper() if j < len(f) else ''
                if c in CODIGOS:
                    registros.append((d, c))
    return {k: sorted(v) for k, v in out.items()}


def notas_t1(wb, area, trimestre=1):
    """{orden: {'SER': [..], 'SABER': [..], 'HACER': [..], 'DECIDIR': [..], 'promedios': {dim: x},
    'autoevaluacion': x, 'nota': x}} de la hoja '<AREA> 1'. Las actividades quedan en el orden del registro."""
    filas = list(wb[f'{area} {trimestre}'].iter_rows(values_only=True))
    # Fila de dimensiones (SER/5, SABER/45, ...) y fila de actividades (con 'PROMEDIO' al cierre de cada una).
    fd = next(i for i, f in enumerate(filas) if any(_txt(v).upper().startswith('SABER') for v in f))
    inicios = sorted((j, _txt(v).upper().split('/')[0].strip()) for j, v in enumerate(filas[fd])
        if _txt(v).upper().split('/')[0].strip() in DIMENSIONES)
    actividades = filas[fd + 1]
    total = next(j for j, v in enumerate(filas[fd]) if _txt(v).upper() == 'TOTAL')
    cortes = [j for j, _ in inicios[1:]] + [total]
    titulos = filas[fd - 1]
    nota = next((j for j, v in enumerate(titulos) if _txt(v).upper().startswith('CALIFICACI')), None)
    h = _encabezado(filas, 'N°')
    estudiantes = _filas_estudiantes(filas, h)
    # Una actividad es una columna con notas (algunas no tienen título en el encabezado).
    con_notas = {j for _, f in estudiantes for j, v in enumerate(f) if _num(v) is not None}
    columnas = {}
    for (inicio, dim), fin in zip(inicios, cortes):
        prom = next((j for j in range(inicio, fin) if _txt(actividades[j]).upper() == 'PROMEDIO'), None)
        acts = [j for j in range(inicio, prom if prom is not None else fin) if j in con_notas]
        columnas[dim] = (acts, prom)
    out = {}
    for orden, f in estudiantes:
        r = {dim: [x for x in (_num(f[j]) for j in acts) if x is not None] for dim, (acts, _) in columnas.items()}
        r['promedios'] = {dim: _num(f[p]) if p is not None else None for dim, (_, p) in columnas.items()}
        # La autoevaluación tiene SER y DECIDIR (5 pts c/u) y un total; se toma el total.
        r['autoevaluacion'] = _num(f[nota - 1]) if nota is not None else None
        r['nota'] = _num(f[nota]) if nota is not None else None
        out[orden] = r
    return out


def leer(ruta):
    """Lee un registro: {'gestion','grado','paralelo','estudiantes': {orden: {'asistencia': [...], 'areas': {area: notas}}}}."""
    import openpyxl
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    gestion, grado, paralelo = curso(wb)
    if not (gestion and grado and paralelo):
        raise ValueError(f'No se pudo identificar el curso en {ruta}.')
    asis = asistencia_t1(wb, gestion)
    areas = {a: notas_t1(wb, a) for a in AREAS if f'{a} 1' in wb.sheetnames}
    estudiantes = {}
    for orden in sorted(set(asis) | {o for n in areas.values() for o in n}):
        estudiantes[orden] = {'asistencia': asis.get(orden, []), 'areas': {a: n[orden] for a, n in areas.items() if orden in n}}
    wb.close()
    return dict(gestion=gestion, grado=grado, paralelo=paralelo, estudiantes=estudiantes)
