"""Experimento: ¿un algoritmo más sencillo rinde igual que XGBoost? (observación del docente revisor, 22/11/2026).

Compara, con el MISMO protocolo y las mismas 19 variables del modelo en uso (sin POST_*):
- árbol de decisión (profundidad 3), Random Forest, regresión logística y XGBoost (modelo en uso);
- más las reglas simples y el azar como referencia.
Hiperparámetros fijados ANTES de ejecutar, sin búsqueda (con 11 casos, ajustar cada modelo sería elegir a posteriori).
Validación: StratifiedGroupKFold de 5 pliegues por estudiante x 20 repeticiones (semillas 1607+), IC 95 % por bootstrap
de estudiantes, diferencia pareada de AP frente a XGBoost y prueba temporal 2021-2023 -> 2024.
No modifica el modelo de producción ni la base.

Uso (desde backend):
    python -m predictivo.experimento_algoritmos --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
"""
import argparse
import json
from pathlib import Path

import numpy as np

from predictivo.real_t1 import load, features, metrics, summarize, fit_xgb, fit_logit, rule_threshold, RULES, THRESHOLD, TARGETS

TARGET = TARGETS['abandono']
SEED = 1607
NOMBRES = {'xgboost': 'XGBoost (modelo en uso)', 'regresion_logistica': 'Regresión logística', 'random_forest': 'Random Forest',
    'arbol_decision': 'Árbol de decisión (profundidad 3)', 'regla_promedio_T1': 'Regla: promedio T1', 'regla_n_areas_bajo_51': 'Regla: áreas bajo 51',
    'regla_faltas_T1': 'Regla: faltas T1', 'siempre_continuidad': 'Azar ("nadie abandona")'}


def fit_arbol(x, y):
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.tree import DecisionTreeClassifier
    return make_pipeline(SimpleImputer(strategy='median'), DecisionTreeClassifier(max_depth=3, min_samples_leaf=5,
        class_weight='balanced', random_state=SEED)).fit(x, y)


def fit_bosque(x, y):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    return make_pipeline(SimpleImputer(strategy='median'), RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
        class_weight='balanced_subsample', random_state=SEED, n_jobs=2)).fit(x, y)


MODELOS = {'xgboost': fit_xgb, 'regresion_logistica': fit_logit, 'random_forest': fit_bosque, 'arbol_decision': fit_arbol}


def validacion(frame, repeticiones, folds=5):
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame[frame[TARGET].notna()].reset_index(drop=True)
    x, y, groups = features(data), data[TARGET].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    names = [*MODELOS, *RULES]
    runs = {n: [] for n in names}
    for rep in range(repeticiones):
        score = {n: np.zeros(len(y)) for n in names}
        flag = {n: np.zeros(len(y), dtype=int) for n in names}
        for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED + rep).split(x, y, groups):
            assert not set(groups[tr]) & set(groups[te])
            for name, fit in MODELOS.items():
                prob = fit(x.iloc[tr], y[tr]).predict_proba(x.iloc[te])[:, 1]
                score[name][te], flag[name][te] = prob, (prob >= THRESHOLD).astype(int)
            for name, (column, sign) in RULES.items():
                s = sign * x[column].to_numpy()
                cut = rule_threshold(s[tr], y[tr])
                score[name][te], flag[name][te] = s[te], (s[te] >= cut).astype(int)
        for n in names:
            runs[n].append((score[n], flag[n]))
    return y, groups, runs


def diferencia_pareada(y, groups, runs, boots=2000):
    """IC 95 % de AP(modelo) - AP(XGBoost) remuestreando estudiantes; cada réplica usa una repetición distinta."""
    from sklearn.metrics import average_precision_score
    rng = np.random.default_rng(SEED)
    students = np.unique(groups)
    index = {s: np.flatnonzero(groups == s) for s in students}
    out = {}
    for name in [n for n in MODELOS if n != 'xgboost']:
        diffs, b = [], 0
        while len(diffs) < boots:
            rows = np.concatenate([index[s] for s in rng.choice(students, len(students))])
            if y[rows].sum() == 0:
                continue
            r = b % len(runs['xgboost'])
            diffs.append(average_precision_score(y[rows], runs[name][r][0][rows]) - average_precision_score(y[rows], runs['xgboost'][r][0][rows]))
            b += 1
        out[name] = dict(media=float(np.mean(diffs)), ic95=[float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))])
    return out


def temporal(frame):
    tr = frame[frame.gestion.isin([2021, 2022, 2023])]
    te = frame[(frame.gestion == 2024) & ~frame.codigo_anonimo.isin(tr.codigo_anonimo)]
    x_tr, y_tr, x_te, y_te = features(tr), tr[TARGET].astype(int).to_numpy(), features(te), te[TARGET].astype(int).to_numpy()
    out = {}
    for name, fit in MODELOS.items():
        prob = fit(x_tr, y_tr).predict_proba(x_te)[:, 1]
        out[name] = metrics(y_te, prob, (prob >= THRESHOLD).astype(int))
    return dict(evaluacion=int(len(te)), positivos=int(y_te.sum()), modelos=out)


def main():
    import sklearn
    import xgboost
    p = argparse.ArgumentParser()
    p.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    p.add_argument('--salida', default='../docs')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    frame = load(a.excel)
    y, groups, runs = validacion(frame, a.repeticiones)
    resumen = summarize(y, groups, runs)
    reporte = dict(version='experimento-algoritmos-v1', protocolo=f'StratifiedGroupKFold 5 pliegues por estudiante x {a.repeticiones} '
        'repeticiones; IC 95 % bootstrap por estudiante (2000); umbral 0,5; hiperparámetros fijados antes, sin búsqueda.',
        hiperparametros={'arbol_decision': 'max_depth=3, min_samples_leaf=5, class_weight=balanced',
            'random_forest': 'n_estimators=300, min_samples_leaf=3, class_weight=balanced_subsample',
            'regresion_logistica': 'estandarizada, class_weight=balanced', 'xgboost': 'parámetros del modelo en uso'},
        modelos={k: {'nombre': NOMBRES[k], **v} for k, v in resumen.items()},
        diferencia_ap_vs_xgboost=diferencia_pareada(y, groups, runs), temporal_2021_2023_a_2024=temporal(frame),
        versiones=dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__),
        nota='Con 11 abandonos y notas T1 registradas de forma estándar para quienes abandonaron (docs/HALLAZGO_REGISTROS_PEDAGOGICOS.md), '
            'cualquier método que use el promedio separa casi igual: las diferencias entre algoritmos no son distinguibles.')
    Path(a.salida, 'experimento_algoritmos.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Versiones:', reporte['versiones'])
    for k, v in reporte['modelos'].items():
        ic = v.get('ic95', {})
        f = lambda m: f"{v.get(m, float('nan')):.3f}" + (f" [{ic[m][0]:.2f}-{ic[m][1]:.2f}]" if m in ic else '')
        print(f"{v['nombre']:36s} AUC {f('roc_auc')}  AP {f('average_precision')}  sens {f('sensibilidad')}  prec {f('precision')}  F1 {f('f1')}"
            f"  VP {v.get('verdaderos_positivos', '-')}  FP {v.get('falsos_positivos', '-')}")
    print('Diferencia de AP frente a XGBoost:', json.dumps(reporte['diferencia_ap_vs_xgboost']))
    t = reporte['temporal_2021_2023_a_2024']
    print('Temporal 2021-2023 -> 2024:', t['evaluacion'], 'matrículas,', t['positivos'], 'abandonos')
    for k, v in t['modelos'].items():
        print(f"  {NOMBRES[k]:36s} AP {v['average_precision']:.3f}  detectados {v['verdaderos_positivos']}  falsas alarmas {v['falsos_positivos']}")


if __name__ == '__main__':
    main()
