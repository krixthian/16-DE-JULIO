"""Experimento con el dataset completo de la institución: variables globales frente a desglosadas.

Observación del revisor: "al contemplar todas las materias debe tener muchas variables; toma en cuenta solo valores
globales". Se comparan, con el MISMO protocolo del modelo en uso, tres conjuntos de variables del 1.er trimestre:
- global (19): las del modelo en uso (notas por área, promedio, mínima, áreas < 51, faltas, atrasos, licencias,
  asistencia, edad, grado, género);
- dimensiones (38): global + agregados por dimensión (SER, SABER, HACER, DECIDIR, autoevaluación, evolución de las
  actividades) y asistencia día por día;
- desglosado (~91): global + asistencia día por día + cada área por dimensión, autoevaluación, tendencia y
  actividades bajas.
Para cada conjunto: XGBoost (parámetros del modelo en uso) y regresión logística. Validación por estudiante
5 pliegues x 20 repeticiones, IC 95 % bootstrap de estudiantes, diferencia pareada de AP frente al global, y prueba
temporal 2021-2023 -> 2024 sin estudiantes compartidos. Criterio fijado antes: adoptar un conjunto solo si el IC 95 %
de su diferencia de AP frente al global queda entero por encima de 0. No modifica el modelo de producción ni la base.

Uso (desde backend):
    python -m predictivo.experimento_desglosado --excel ../data/DATASET_INSTITUCION_2021_2025.xlsx --salida ../docs
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo import variables_detalladas as vd
from predictivo.dataset_institucion import DESGLOSE
from predictivo.real_t1 import FEATURE_NAMES, PARAMS, THRESHOLD, TARGETS, load, metrics, summarize

TARGET = TARGETS['abandono']
SEED = 1607
ASISTENCIA_DIA = ['faltas_feb', 'faltas_abr', 'tendencia_faltas', 'faltas_ultimas_4_semanas', 'cambio_faltas_final_inicio',
    'racha_max_faltas', 'racha_final_faltas', 'faltas_lunes_viernes', 'retrasos_ultimas_4_semanas']
CONJUNTOS = {
    'global': FEATURE_NAMES,
    'dimensiones': FEATURE_NAMES + [n for n in vd.NOMBRES if n not in ASISTENCIA_DIA] + ASISTENCIA_DIA,
    'desglosado': FEATURE_NAMES + ASISTENCIA_DIA + DESGLOSE,
}


def cargar(excel):
    base = load(excel)
    crudo = pd.read_excel(excel, sheet_name='DATOS_REAL')
    extra = [c for c in set(sum(CONJUNTOS.values(), [])) if c not in base.columns]
    return base.merge(crudo[['codigo_anonimo', 'gestion', *extra]], on=['codigo_anonimo', 'gestion'], validate='one_to_one')


def ajustar(nombre, x, y):
    if nombre == 'xgboost':
        import xgboost as xgb
        return xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y == 0).sum() / max((y == 1).sum(), 1))).fit(x, y)
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=4000)).fit(x, y)


def validacion(data, repeticiones, folds=5):
    from sklearn.model_selection import StratifiedGroupKFold
    y, groups = data[TARGET].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    runs = {f'{c}|{m}': [] for c in CONJUNTOS for m in ('xgboost', 'logistica')}
    for rep in range(repeticiones):
        score = {k: np.zeros(len(y)) for k in runs}
        for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED + rep).split(data, y, groups):
            assert not set(groups[tr]) & set(groups[te])
            for c, cols in CONJUNTOS.items():
                x = data[cols].astype(float)
                for m in ('xgboost', 'logistica'):
                    score[f'{c}|{m}'][te] = ajustar(m, x.iloc[tr], y[tr]).predict_proba(x.iloc[te])[:, 1]
        for k in runs:
            runs[k].append((score[k], (score[k] >= THRESHOLD).astype(int)))
    return y, groups, runs


def diferencias(y, groups, runs, boots=2000):
    from sklearn.metrics import average_precision_score
    rng = np.random.default_rng(SEED)
    students = np.unique(groups)
    index = {s: np.flatnonzero(groups == s) for s in students}
    out = {}
    for k in runs:
        if k == 'global|xgboost':
            continue
        diffs, b = [], 0
        while len(diffs) < boots:
            rows = np.concatenate([index[s] for s in rng.choice(students, len(students))])
            if y[rows].sum() == 0:
                continue
            r = b % len(runs[k])
            diffs.append(average_precision_score(y[rows], runs[k][r][0][rows]) - average_precision_score(y[rows], runs['global|xgboost'][r][0][rows]))
            b += 1
        out[k] = dict(media=float(np.mean(diffs)), ic95=[float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))])
    return out


def temporal(data, estricta=False):
    """Entrenar 2021-2023 y evaluar en 2024. Realista: toda la gestión 2024 (como se usaría el sistema).
    Estricta: sin estudiantes que ya estaban en 2021-2023."""
    tr = data[data.gestion.isin([2021, 2022, 2023])]
    te = data[(data.gestion == 2024) & (~data.codigo_anonimo.isin(tr.codigo_anonimo) if estricta else True)]
    y_tr, y_te = tr[TARGET].astype(int).to_numpy(), te[TARGET].astype(int).to_numpy()
    out = dict(entrenamiento=int(len(tr)), positivos_entrenamiento=int(y_tr.sum()), evaluacion=int(len(te)), positivos_evaluacion=int(y_te.sum()), modelos={})
    if y_te.sum() == 0:
        return out
    for c, cols in CONJUNTOS.items():
        for m in ('xgboost', 'logistica'):
            prob = ajustar(m, tr[cols].astype(float), y_tr).predict_proba(te[cols].astype(float))[:, 1]
            out['modelos'][f'{c}|{m}'] = metrics(y_te, prob, (prob >= THRESHOLD).astype(int))
    return out


def main():
    import sklearn
    import xgboost
    p = argparse.ArgumentParser()
    p.add_argument('--excel', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    p.add_argument('--salida', default='../docs')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    data = cargar(a.excel)
    data = data[data[TARGET].notna()].reset_index(drop=True)
    if any(c.startswith('POST_') for cols in CONJUNTOS.values() for c in cols):
        raise ValueError('Las columnas POST_* no pueden ser predictores.')
    y, groups, runs = validacion(data, a.repeticiones)
    resumen = summarize(y, groups, runs)
    reporte = dict(version='experimento-desglosado-v1', dataset=Path(a.excel).name, matriculas=int(len(y)), abandonos=int(y.sum()),
        estudiantes=int(len(set(groups))), variables={c: len(v) for c, v in CONJUNTOS.items()},
        protocolo=f'StratifiedGroupKFold 5 x {a.repeticiones} por estudiante; IC 95 % bootstrap por estudiante; umbral 0,5; parámetros fijos.',
        criterio='Adoptar un conjunto solo si el IC 95 % de su diferencia de AP frente a global|xgboost queda entero por encima de 0.',
        modelos=resumen, diferencia_ap_vs_global_xgboost=diferencias(y, groups, runs), temporal_2024_realista=temporal(data), temporal_2024_estricta=temporal(data, True),
        versiones=dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__))
    Path(a.salida, 'experimento_desglosado.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Dataset:', reporte['dataset'], '| matrículas', reporte['matriculas'], '| abandonos', reporte['abandonos'], '| variables', reporte['variables'])
    for k, v in resumen.items():
        ic = v.get('ic95', {})
        f = lambda m: f"{v.get(m, float('nan')):.3f}" + (f" [{ic[m][0]:.2f}-{ic[m][1]:.2f}]" if m in ic else '')
        print(f"{k:24s} AUC {f('roc_auc')}  AP {f('average_precision')}  sens {f('sensibilidad')}  prec {f('precision')}  F1 {f('f1')}"
            f"  VP {v.get('verdaderos_positivos', '-')}  FP {v.get('falsos_positivos', '-')}")
    print('Diferencia de AP frente a global|xgboost:')
    for k, v in reporte['diferencia_ap_vs_global_xgboost'].items():
        print(f"  {k:24s} {v['media']:+.3f} [{v['ic95'][0]:+.3f}; {v['ic95'][1]:+.3f}]")
    for clave in ('temporal_2024_realista', 'temporal_2024_estricta'):
        t = reporte[clave]
        print(clave, {k: v for k, v in t.items() if k != 'modelos'})
        for k, v in t['modelos'].items():
            print(f"  {k:24s} AP {v['average_precision']:.3f}  detectados {v['verdaderos_positivos']}  falsas alarmas {v['falsos_positivos']}")


if __name__ == '__main__':
    main()
