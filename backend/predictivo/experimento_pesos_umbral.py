"""Experimento: ¿mejora elegir el peso de clase (scale_pos_weight) y el umbral con validación?

No modifica el modelo de producción. Reutiliza de real_t1.py la carga, las 19 variables del corte T1, los
hiperparámetros (PARAMS) y la partición StratifiedGroupKFold por estudiante (5 pliegues × 20 repeticiones,
semilla 1607 + repetición).

- Línea base: el modelo en uso, peso = negativos / positivos del entrenamiento y umbral 0,5.
- Anidado: dentro de cada pliegue de entrenamiento, una CV interna de 4 pliegues por estudiante elige la
  combinación (peso, umbral) con mayor F1; se mide solo en el pliegue externo, que nunca participa en la elección.
- Rejilla fija (descriptiva): cada combinación evaluada en los pliegues externos, sin selección; no sirve para elegir.

Criterio fijado antes de ejecutar: proponer un cambio solo si el IC 95 % pareado (bootstrap por estudiante) de
F1 (anidado − base) queda entero por encima de 0.

Uso (desde backend):
    python -m predictivo.experimento_pesos_umbral --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo.real_t1 import load, features, metrics, PARAMS, THRESHOLD, TARGETS

TARGET = TARGETS['abandono']
SEED = 1607
PESOS = (1, 5, 10, 20, 35, 'balanceado', 140)  # 'balanceado' = negativos / positivos del entrenamiento (≈ 70,8)
UMBRALES = (.1, .2, .3, .4, .5, .6, .7)
METRICAS = ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'verdaderos_positivos', 'falsos_positivos')


def peso(w, y):
    return float((y == 0).sum() / max((y == 1).sum(), 1)) if w == 'balanceado' else float(w)


def entrenar(x, y, w):
    import xgboost as xgb
    return xgb.XGBClassifier(**PARAMS, scale_pos_weight=peso(w, y)).fit(x, y)


def f1(y, flag):
    tp = int(((y == 1) & flag).sum())
    fp, fn = int(((y == 0) & flag).sum()), int(((y == 1) & ~flag).sum())
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def elegir(x, y, groups, seed, folds=4):
    """CV interna por estudiante sobre el entrenamiento externo: (peso, umbral) con mayor F1.
    Empates: el umbral más alto (menos alertas) y luego el peso más cercano al balanceado."""
    from sklearn.model_selection import StratifiedGroupKFold
    oof = {w: np.zeros(len(y)) for w in PESOS}
    for tr, va in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(x, y, groups):
        if len(set(y[tr])) < 2:
            raise ValueError('Un pliegue interno quedó sin positivos.')
        for w in PESOS:
            oof[w][va] = entrenar(x.iloc[tr], y[tr], w).predict_proba(x.iloc[va])[:, 1]
    balanceado = peso('balanceado', y)
    candidatos = [(f1(y, oof[w] >= t), t, -abs(np.log(peso(w, y) / balanceado)), w) for w in PESOS for t in UMBRALES]
    mejor = max(candidatos, key=lambda c: c[:3])
    return mejor[3], mejor[1], mejor[0]


def validacion_cruzada(frame, repeticiones, folds=5):
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame[frame[TARGET].notna()].reset_index(drop=True)
    x, y, groups = features(data), data[TARGET].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    filas, elecciones, corridas = [], [], {'base': [], 'anidado': []}
    for rep in range(repeticiones):
        seed = SEED + rep
        score = {k: np.zeros(len(y)) for k in ('base', 'anidado')}
        flag = {k: np.zeros(len(y), dtype=bool) for k in ('base', 'anidado')}
        rejilla = {w: np.zeros(len(y)) for w in PESOS}
        for f, (tr, te) in enumerate(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(x, y, groups)):
            assert not set(groups[tr]) & set(groups[te]), 'Un estudiante quedó en entrenamiento y prueba.'
            modelos = {w: entrenar(x.iloc[tr], y[tr], w) for w in PESOS}
            for w, model in modelos.items():
                rejilla[w][te] = model.predict_proba(x.iloc[te])[:, 1]
            score['base'][te] = rejilla['balanceado'][te]
            flag['base'][te] = score['base'][te] >= THRESHOLD
            w, t, f1_interno = elegir(x.iloc[tr], y[tr], groups[tr], seed + 1000 * (f + 1))
            score['anidado'][te], flag['anidado'][te] = rejilla[w][te], rejilla[w][te] >= t
            elecciones.append(dict(repeticion=rep, pliegue=f, peso=str(w), peso_valor=round(peso(w, y[tr]), 2), umbral=t,
                f1_interno=round(f1_interno, 4), positivos_entrenamiento=int(y[tr].sum())))
        for k in ('base', 'anidado'):
            m = metrics(y, score[k], flag[k].astype(int))
            filas.append(dict(esquema='cv_agrupada_5x', variante=k, peso='balanceado' if k == 'base' else 'elegido',
                umbral=THRESHOLD if k == 'base' else 'elegido', repeticion=rep, semilla=seed, **{c: m[c] for c in METRICAS}))
            corridas[k].append(flag[k].astype(int))
        for w in PESOS:
            for t in UMBRALES:
                m = metrics(y, rejilla[w], (rejilla[w] >= t).astype(int))
                filas.append(dict(esquema='rejilla_fija_descriptiva', variante=f'peso={w}|umbral={t}', peso=str(w), umbral=t,
                    repeticion=rep, semilla=seed, **{c: m[c] for c in METRICAS}))
    return data, y, groups, filas, elecciones, corridas


def bootstrap_pareado(y, groups, corridas, boots=2000, seed=SEED):
    """IC 95 % de F1 (anidado − base) remuestreando estudiantes; cada réplica usa una repetición distinta."""
    rng = np.random.default_rng(seed)
    students = np.unique(groups)
    index = {s: np.flatnonzero(groups == s) for s in students}
    diffs, b = [], 0
    while len(diffs) < boots:
        rows = np.concatenate([index[s] for s in rng.choice(students, len(students))])
        if y[rows].sum() == 0:
            continue
        r = b % len(corridas['base'])
        diffs.append(f1(y[rows], corridas['anidado'][r][rows].astype(bool)) - f1(y[rows], corridas['base'][r][rows].astype(bool)))
        b += 1
    return float(np.mean(diffs)), [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]


def temporal(frame):
    """Entrenar con 2021-2023 y evaluar en 2024 sin estudiantes compartidos; la elección usa solo 2021-2023."""
    tr = frame[frame.gestion.isin([2021, 2022, 2023])]
    te = frame[frame.gestion.isin([2024])]
    te = te[~te.codigo_anonimo.isin(tr.codigo_anonimo)]
    x_tr, y_tr, g_tr = features(tr), tr[TARGET].astype(int).to_numpy(), tr['codigo_anonimo'].to_numpy()
    x_te, y_te = features(te), te[TARGET].astype(int).to_numpy()
    w, t, _ = elegir(x_tr, y_tr, g_tr, SEED)
    filas = []
    for nombre, (wi, ti) in (('base', ('balanceado', THRESHOLD)), ('anidado', (w, t))):
        prob = entrenar(x_tr, y_tr, wi).predict_proba(x_te)[:, 1]
        m = metrics(y_te, prob, (prob >= ti).astype(int))
        filas.append(dict(esquema='temporal_2021_2023_a_2024', variante=nombre, peso=str(wi), umbral=ti, repeticion=0, semilla=SEED,
            **{c: m[c] for c in METRICAS}))
    return filas, dict(entrenamiento=len(tr), positivos_entrenamiento=int(y_tr.sum()), evaluacion=len(te),
        positivos_evaluacion=int(y_te.sum()), eleccion=dict(peso=str(w), umbral=t))


def main():
    import sklearn
    import xgboost
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    parser.add_argument('--salida', default='../docs')
    parser.add_argument('--repeticiones', type=int, default=20)
    args = parser.parse_args()
    frame = load(args.excel)
    data, y, groups, filas, elecciones, corridas = validacion_cruzada(frame, args.repeticiones)
    t_filas, t_info = temporal(frame)
    resultados = pd.DataFrame(filas + t_filas)
    out = Path(args.salida)
    resultados.to_csv(out / 'experimento_pesos_umbral_resultados.csv', index=False)
    pd.DataFrame(elecciones).to_csv(out / 'experimento_pesos_umbral_elecciones.csv', index=False)
    media, ic = bootstrap_pareado(y, groups, corridas)
    cv = resultados[resultados.esquema == 'cv_agrupada_5x']
    print('Versiones:', dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__))
    print(cv.groupby('variante')[list(METRICAS)].agg(['mean', 'std']).round(3).T.to_string())
    print(f'ΔF1 anidado − base: {media:+.3f}  IC 95 % [{ic[0]:+.3f}; {ic[1]:+.3f}]  ->',
        'PROPONER CAMBIO' if ic[0] > 0 else 'sin mejora distinguible: se mantiene el modelo en uso')
    e = pd.DataFrame(elecciones)
    print('Elecciones (peso, umbral):', Counter(zip(e.peso, e.umbral)).most_common(6), '| distintas:', len(set(zip(e.peso, e.umbral))))
    print('Temporal:', t_info)
    print(resultados[resultados.esquema == 'temporal_2021_2023_a_2024'][['variante', 'peso', 'umbral', 'average_precision', 'sensibilidad',
        'precision', 'verdaderos_positivos', 'falsos_positivos']].to_string(index=False))
    rej = resultados[resultados.esquema == 'rejilla_fija_descriptiva'].groupby(['peso', 'umbral'])[['f1', 'verdaderos_positivos', 'falsos_positivos', 'average_precision']].mean()
    rej.round(3).to_csv(out / 'experimento_pesos_umbral_rejilla.csv')
    print('Mejor F1 de la rejilla fija (descriptivo, elegido a posteriori, NO usar para decidir):', rej.f1.idxmax(), round(rej.f1.max(), 3))
    (out / 'experimento_pesos_umbral_ic.txt').write_text(f'delta_f1_media={media}\nic95={ic}\n', encoding='utf-8')


if __name__ == '__main__':
    main()
