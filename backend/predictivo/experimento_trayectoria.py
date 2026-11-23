"""Experimento: ¿la trayectoria escolar previa permite anticipar el abandono desde febrero?

Pregunta del autor: si al 30 de abril no hay señal, ¿se puede anticipar con lo que la escuela ya sabe del estudiante
al iniciar el año? Las variables de trayectoria salen de la gestión ANTERIOR del mismo estudiante (vinculado por su
código anónimo), por lo que existen en febrero y no son fuga de información:
- nuevo: no estuvo en la escuela la gestión anterior;
- repite_grado: cursa el mismo grado que la gestión anterior;
- desfase_edad: edad al 31 de marzo menos grado (sobreedad si es >= 7);
- abandono_previo, reprobo_previo, promedio_anual_previo, areas_reprobadas_previo;
- prop_faltas_previo y prop_faltas_t3_previo: faltas en todo el año anterior y en su último trimestre (sep-nov);
- gestiones_previas: cuántas gestiones lleva en la escuela (desde 2021).
Se usan las gestiones 2022-2025 (2021 no tiene gestión anterior registrada).

Conjuntos (fijados antes de correr):
- trayectoria (febrero): las variables de trayectoria + edad y grado;
- global (abril): las 19 del modelo en uso;
- global + trayectoria (abril).
XGBoost (parámetros del modelo en uso) y regresión logística; validación por estudiante 5 x 20, IC 95 % bootstrap por
estudiante, diferencia pareada de AP frente a global|xgboost y comparación con el azar (AP = prevalencia).
Criterio fijado antes: la trayectoria "anticipa" solo si el IC 95 % de su AP queda entero por encima de la
prevalencia. No modifica el modelo de producción ni la base.

Uso (desde backend):
    python -m predictivo.experimento_trayectoria --excel ../data/DATASET_INSTITUCION_2021_2025.xlsx --salida ../docs
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo import experimento_desglosado as ed
from predictivo.real_t1 import FEATURE_NAMES, THRESHOLD, TARGETS, load, summarize

TARGET = TARGETS['abandono']
SEED = 1607
TRAYECTORIA = ['nuevo', 'repite_grado', 'desfase_edad', 'abandono_previo', 'reprobo_previo', 'promedio_anual_previo',
    'areas_reprobadas_previo', 'prop_faltas_previo', 'prop_faltas_t3_previo', 'gestiones_previas', 'edad_31marzo', 'grado']
CONJUNTOS = {
    'trayectoria': TRAYECTORIA,
    'global': FEATURE_NAMES,
    'global_trayectoria': FEATURE_NAMES + [c for c in TRAYECTORIA if c not in FEATURE_NAMES],
}


def trayectoria(excel, asistencia_csv):
    crudo = pd.read_excel(excel, sheet_name='DATOS_REAL')
    asis = pd.read_csv(asistencia_csv, parse_dates=['fecha'])
    asis['falta'] = asis.estado.eq('F')
    faltas = asis.groupby(['codigo_anonimo', 'gestion']).falta.mean().rename('prop_faltas_previo')
    faltas_t3 = asis[asis.fecha.dt.month >= 9].groupby(['codigo_anonimo', 'gestion']).falta.mean().rename('prop_faltas_t3_previo')
    prev = crudo[['codigo_anonimo', 'gestion', 'grado', 'y_abandono_intra_anual', 'y_reprobacion', 'POST_promedio_anual',
        'POST_n_areas_reprobadas']].set_index(['codigo_anonimo', 'gestion']).join(faltas).join(faltas_t3).reset_index()
    prev = prev.rename(columns={'grado': 'grado_previo', 'y_abandono_intra_anual': 'abandono_previo', 'y_reprobacion': 'reprobo_previo',
        'POST_promedio_anual': 'promedio_anual_previo', 'POST_n_areas_reprobadas': 'areas_reprobadas_previo'})
    prev['gestion'] += 1  # lo de la gestión anterior se conoce en febrero de la siguiente
    t = crudo[['codigo_anonimo', 'gestion', 'grado']].merge(prev, on=['codigo_anonimo', 'gestion'], how='left')
    t['nuevo'] = t.grado_previo.isna().astype(int)
    t['repite_grado'] = (t.grado == t.grado_previo).astype(int)
    t['gestiones_previas'] = t.groupby('codigo_anonimo').gestion.rank(method='first').astype(int) - 1
    return t.drop(columns=['grado', 'grado_previo'])


def main():
    import sklearn
    import xgboost
    p = argparse.ArgumentParser()
    p.add_argument('--excel', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    p.add_argument('--salida', default='../docs')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    asistencia_csv = Path(a.excel).with_name(Path(a.excel).stem + '_ASISTENCIA_DIARIA.csv')
    data = load(a.excel).merge(trayectoria(a.excel, asistencia_csv), on=['codigo_anonimo', 'gestion'], validate='one_to_one')
    data = data[data[TARGET].notna() & (data.gestion >= 2022)].reset_index(drop=True)
    data['desfase_edad'] = data.edad_31marzo - data.grado
    if any(c.startswith('POST_') for cols in CONJUNTOS.values() for c in cols):
        raise ValueError('Las columnas POST_* no pueden ser predictores.')
    y = data[TARGET].astype(int)
    descriptivo = {}
    for c in ('nuevo', 'repite_grado', 'abandono_previo', 'reprobo_previo'):
        g = data.groupby(data[c].fillna(-1).astype(int))[TARGET].agg(['size', 'sum'])
        descriptivo[c] = {('sin dato' if k == -1 else str(k)): dict(matriculas=int(r['size']), abandonos=int(r['sum'])) for k, r in g.iterrows()}
    descriptivo['sobreedad (desfase >= 7)'] = dict(matriculas=int((data.desfase_edad >= 7).sum()), abandonos=int(y[data.desfase_edad >= 7].sum()))
    for c in ('promedio_anual_previo', 'prop_faltas_previo', 'prop_faltas_t3_previo', 'desfase_edad'):
        descriptivo[c] = dict(mediana_abandonos=float(data.loc[y == 1, c].median()), mediana_resto=float(data.loc[y == 0, c].median()))
    ed.CONJUNTOS = CONJUNTOS  # mismas funciones de validación, con estos conjuntos
    ed.TARGET = TARGET
    yv, groups, runs = ed.validacion(data, a.repeticiones)
    resumen = summarize(yv, groups, runs)
    prevalencia = float(yv.mean())
    reporte = dict(version='experimento-trayectoria-v1', dataset=Path(a.excel).name, gestiones=[2022, 2023, 2024, 2025],
        matriculas=int(len(yv)), abandonos=int(yv.sum()), estudiantes=int(len(set(groups))), prevalencia_azar=prevalencia,
        variables={c: v for c, v in CONJUNTOS.items()},
        protocolo=f'StratifiedGroupKFold 5 x {a.repeticiones} por estudiante; IC 95 % bootstrap por estudiante; umbral {THRESHOLD}; parámetros fijos.',
        criterio='La trayectoria anticipa solo si el IC 95 % de su AP queda entero por encima de la prevalencia (azar).',
        descriptivo=descriptivo, modelos=resumen, diferencia_ap_vs_global_xgboost=ed.diferencias(yv, groups, runs),
        versiones=dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__))
    Path(a.salida, 'experimento_trayectoria.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
    print('matrículas', reporte['matriculas'], '| abandonos', reporte['abandonos'], '| azar (AP)', f'{prevalencia:.4f}')
    print(json.dumps(descriptivo, ensure_ascii=False, indent=1))
    for k, v in resumen.items():
        ic = v.get('ic95', {})
        f = lambda m: f"{v.get(m, float('nan')):.3f}" + (f" [{ic[m][0]:.3f}-{ic[m][1]:.3f}]" if m in ic else '')
        print(f"{k:30s} AUC {f('roc_auc')}  AP {f('average_precision')}  VP {v.get('verdaderos_positivos', '-')}  FP {v.get('falsos_positivos', '-')}")
    for k, v in reporte['diferencia_ap_vs_global_xgboost'].items():
        print(f"  dif AP {k:28s} {v['media']:+.3f} [{v['ic95'][0]:+.3f}; {v['ic95'][1]:+.3f}]")


if __name__ == '__main__':
    main()
