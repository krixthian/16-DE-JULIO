"""Extrae de los archivos recibidos (22/11/2026 y 7 cursos de 2025) la nota por dimensión del T1 y el T2, anonimizada.

Uso (desde backend):
    python -m predictivo.extraer_desglose --registros "C:/Users/Cristhian/Documents/DATOS_COMPLETOS" "C:/Users/Cristhian/Documents/DATOS"
No lee nombres ni escribe en la base: recorre los registros en el mismo orden que construir_dataset_institucion y
comprueba, fila por fila, que el curso y las 9 notas del T1 coincidan con el dataset anonimizado. Origen no verificado.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from predictivo import dataset_institucion as di, registros_pedagogicos as rp
from predictivo.desglose import DIMENSIONES

DATOS = Path(__file__).resolve().parents[2] / 'data'
SALIDA = DATOS / 'DESGLOSE_INSTITUCION_2021_2025.csv'


def leer(ruta):
    import openpyxl
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    g, gr, p = rp.curso(wb)
    centra = di.centralizador(wb)
    ordenes = sorted(di.nombres(wb))
    filas = {}
    for area in rp.AREAS:
        for t in (1, 2):
            for orden, n in rp.notas_t1(wb, area, t).items():
                for dim, maximo in DIMENSIONES.items():
                    v = n['autoevaluacion'] if dim == 'Autoevaluación' else n['promedios'][dim.upper()]
                    if v is not None:
                        filas.setdefault(orden, []).append((area, t, dim, v, maximo))
    wb.close()
    return dict(curso=(g, gr, str(p)), ordenes=ordenes, filas=filas,
        t1={o: [centra[o][a][0] if a in centra.get(o, {}) else None for a in rp.AREAS] for o in ordenes})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--registros', nargs='+', required=True)
    a = p.parse_args()
    ds = pd.read_excel(DATOS / 'DATASET_INSTITUCION_2021_2025.xlsx', sheet_name='DATOS_REAL')
    rutas = [r for c in a.registros for r in sorted(Path(c).rglob('REGISTRO_PEDAGOGICO_*.xlsx'))]
    with ProcessPoolExecutor(8) as ex:
        regs = list(ex.map(leer, rutas))
    regs.sort(key=lambda r: r['curso'])
    out, i, fuera = [], 0, 0
    for r in regs:
        for orden in r['ordenes']:
            f = ds.iloc[i]
            i += 1
            assert (int(f.gestion), int(f.grado), str(f.paralelo)) == r['curso'], i
            for area, v in zip(rp.AREAS, r['t1'][orden]):
                assert v is None or float(f[f'{area}_T1']) == v, (r['curso'], area)
            for area, t, dim, v, maximo in r['filas'].get(orden, []):
                if not 0 <= v <= maximo:
                    fuera += 1
                    continue
                out.append((f.codigo_anonimo, int(f.gestion), int(f.grado), str(f.paralelo), area, t, dim, round(v, 2), maximo))
    assert i == len(ds), (i, len(ds))
    df = pd.DataFrame(out, columns=['codigo_anonimo', 'gestion', 'grado', 'paralelo', 'area', 'trimestre', 'dimension', 'puntaje', 'maximo'])
    df.to_csv(SALIDA, index=False)
    print('filas del dataset emparejadas', i, '| notas', len(df), '| fuera de escala (omitidas)', fuera)
    print(df.groupby(['trimestre', 'dimension']).puntaje.agg(['size', 'min', 'mean', 'max']).round(2).to_string())


if __name__ == '__main__':
    main()
