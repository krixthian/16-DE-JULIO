"""Construye el dataset detallado del 1.er trimestre (anonimizado) a partir de los registros pedagógicos originales.

Uso (desde backend):
    python -m predictivo.construir_detallado --registros "C:/ruta/DATOS_HISTORICO" "C:/ruta/DATOS" --salida ../data/DATASET_DETALLADO_T1.csv

La salida solo contiene el código anónimo y variables numéricas: ningún nombre sale de los registros.
"""
import argparse
from pathlib import Path

import pandas as pd

from predictivo import registros_pedagogicos as rp, emparejar_registros as er, variables_detalladas as vd


def construir(carpetas, excel):
    ds = pd.read_excel(excel, sheet_name='DATOS_REAL')
    filas, informes = [], []
    for carpeta in carpetas:
        for ruta in sorted(Path(carpeta).rglob('REGISTRO_PEDAGOGICO_*.xlsx')):
            registro = rp.leer(ruta)
            pares, informe = er.emparejar(registro, ds)
            informes.append(informe)
            for orden, codigo in pares.items():
                filas.append({'codigo_anonimo': codigo, 'gestion': registro['gestion'], 'grado': registro['grado'],
                    'paralelo': registro['paralelo'], **vd.calcular(registro['estudiantes'][orden])})
    df = pd.DataFrame(filas)
    if df.duplicated(['codigo_anonimo', 'gestion']).any():
        raise ValueError('Un estudiante aparece dos veces en la misma gestión.')
    return df, pd.DataFrame(informes)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--registros', nargs='+', required=True)
    p.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    p.add_argument('--salida', default='../data/DATASET_DETALLADO_T1.csv')
    a = p.parse_args()
    df, inf = construir(a.registros, a.excel)
    df.to_csv(a.salida, index=False)
    print(inf.to_string(index=False))
    print(f'{len(df)} matrículas -> {a.salida}')


if __name__ == '__main__':
    main()
