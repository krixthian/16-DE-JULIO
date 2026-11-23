"""Construye el dataset completo 2021-2025 desde los registros de la institución (anonimizado).

Uso (desde backend):
    python -m predictivo.construir_dataset_institucion \
        --registros "C:/Users/Cristhian/Documents/DATOS_COMPLETOS" "C:/Users/Cristhian/Documents/DATOS" \
        --anterior "C:/Users/Cristhian/Documents/DATOS_HISTORICO" "C:/Users/Cristhian/Documents/DATOS" \
        --salida ../data/DATASET_INSTITUCION_2021_2025.xlsx

Códigos anónimos: el mismo estudiante se vincula entre gestiones por su nombre (solo en memoria). Si ya tenía código
en el dataset anterior se reutiliza; si no, recibe uno nuevo (EST-2001 en adelante, en orden de aparición).
La salida no contiene nombres, carnet, RUDE, fechas de nacimiento ni datos de contacto.
"""
import argparse
from pathlib import Path

import pandas as pd

from predictivo import dataset_institucion as di, registros_pedagogicos as rp, emparejar_registros as er


def rutas(carpetas):
    out = []
    for c in carpetas:
        out += sorted(Path(c).rglob('REGISTRO_PEDAGOGICO_*.xlsx'))
    return out


def codigos_anteriores(carpetas, excel):
    """{nombre normalizado: código} desde la versión anterior (emparejada sin nombres con el dataset anterior)."""
    import openpyxl
    ds = pd.read_excel(excel, sheet_name='DATOS_REAL')
    out, dudosos = {}, set()
    for ruta in rutas(carpetas):
        pares, _ = er.emparejar(rp.leer(ruta), ds)
        wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        nom = di.nombres(wb)
        wb.close()
        for orden, cod in pares.items():
            n = nom.get(orden)
            if n is None:
                continue
            if n in out and out[n] != cod:
                dudosos.add(n)
            out[n] = cod
    for n in dudosos:
        out.pop(n, None)
    return out


def construir(carpetas, previos):
    registros = [di.leer_registro(r) for r in rutas(carpetas)]
    registros.sort(key=lambda r: (r['gestion'], r['grado'], str(r['paralelo'])))
    siguiente = 2001
    asignados = dict(previos)
    usados = set(previos.values())
    filas, asistencia, reutilizados = [], [], 0
    # Homónimos: el mismo nombre dos veces en una gestión son niños distintos; para esos nombres el vínculo usa además
    # la generación (gestión - grado). El resto se vincula solo por nombre, para no perder a quienes repiten de grado.
    vistos, homonimos = {}, set()
    for reg in registros:
        for n in reg['nombres'].values():
            if (reg['gestion'], n) in vistos:
                homonimos.add(n)
            vistos[(reg['gestion'], n)] = True
    for reg in registros:
        for orden in sorted(reg['nombres']):
            nombre = reg['nombres'][orden]
            if nombre in homonimos:
                nombre = (nombre, reg['gestion'] - reg['grado'])
            if nombre in asignados:
                reutilizados += nombre in previos
            else:
                while f'EST-{siguiente:04d}' in usados:
                    siguiente += 1
                asignados[nombre] = f'EST-{siguiente:04d}'
                usados.add(asignados[nombre])
            filas.append({'codigo_anonimo': asignados[nombre], **di.fila(reg, orden), 'origen_dato': 'REAL_INSTITUCION'})
            asistencia += [(asignados[nombre], reg['gestion'], d.isoformat(), c) for d, c in reg['asistencia'].get(orden, [])]
    df = pd.DataFrame(filas)
    # No continúa la gestión siguiente: solo 2024 (grados 1-5), igual que antes; 2025 tiene cursos incompletos.
    en_2025 = set(df[df.gestion == 2025].codigo_anonimo)
    df['y_no_continua_siguiente'] = [int(c not in en_2025) if g == 2024 and gr < 6 else None
        for c, g, gr in zip(df.codigo_anonimo, df.gestion, df.grado)]
    if df.duplicated(['codigo_anonimo', 'gestion']).any():
        raise ValueError('Un mismo estudiante aparece dos veces en la misma gestión (nombres repetidos).')
    return df, reutilizados, pd.DataFrame(asistencia, columns=['codigo_anonimo', 'gestion', 'fecha', 'estado'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--registros', nargs='+', required=True)
    p.add_argument('--anterior', nargs='+', required=True)
    p.add_argument('--excel-anterior', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    p.add_argument('--salida', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    a = p.parse_args()
    previos = codigos_anteriores(a.anterior, a.excel_anterior)
    df, reutilizados, asistencia = construir(a.registros, previos)
    leeme = pd.DataFrame({'DATASET INSTITUCION 2021-2025': [
        'Construido desde los registros pedagógicos completos entregados por la institución (18 paralelos por gestión 2021-2024; 2025: 7 cursos).',
        'Sin nombres, carnet, RUDE, fecha de nacimiento ni contactos. Códigos anónimos vinculan al mismo estudiante entre gestiones.',
        'Columnas sin prefijo POST_: disponibles al cierre del T1 (febrero-abril). POST_*: T2, T3 y anual (NO usar como predictores).',
        'y_abandono_intra_anual = 1 si no asistió ningún día del T3 o sus notas del T3 quedan en 18. trimestre_caida = T2 o T3.',
        'Variables desglosadas: <ÁREA>_ser/_saber/_hacer/_decidir/_auto (0 a 1), <ÁREA>_tendencia, <ÁREA>_bajas, y asistencia día por día.',
        'Constructor validado: reproduce el dataset anterior 790 de 790 filas en todas las columnas desde sus registros.']})
    with pd.ExcelWriter(a.salida) as w:
        leeme.to_excel(w, sheet_name='LEEME', index=False)
        df.to_excel(w, sheet_name='DATOS_REAL', index=False)
    print('matriculas', len(df), '| estudiantes', df.codigo_anonimo.nunique(), '| codigos reutilizados', reutilizados)
    print(df.groupby('gestion').agg(matriculas=('codigo_anonimo', 'size'), cursos=('paralelo', lambda s: len(set(zip(df.loc[s.index, 'grado'], s)))),
        abandonos=('y_abandono_intra_anual', 'sum'), reprobados=('y_reprobacion', 'sum')).to_string())
    salida_asis = Path(a.salida).with_name(Path(a.salida).stem + '_ASISTENCIA_DIARIA.csv')
    asistencia.to_csv(salida_asis, index=False)
    print('->', a.salida, '|', len(asistencia), 'registros diarios ->', salida_asis)


if __name__ == '__main__':
    main()
