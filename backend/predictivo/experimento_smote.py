"""Experimento: ¿mejora SMOTE el tratamiento del desbalance frente a scale_pos_weight?

No modifica el modelo de producción. Reutiliza de real_t1.py la carga, las 19 variables del corte T1,
los hiperparámetros (PARAMS), el umbral fijo 0,5, las métricas y la partición StratifiedGroupKFold
por estudiante (5 pliegues, semilla 1607 + repetición). El remuestreo se aplica SOLO al pliegue de
entrenamiento; el pliegue de prueba y el año de prueba nunca se tocan.

Uso (desde backend):
    python -m predictivo.experimento_smote --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
"""
import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo.real_t1 import load, features, metrics, PARAMS, THRESHOLD, TARGETS

TARGET = TARGETS['abandono']
SEED = 1607
VARIANTS = {  # nombre: (método de remuestreo, usar scale_pos_weight después)
    'a_sin_balanceo': (None, False),
    'b_scale_pos_weight': (None, True),  # línea base: lo que usa hoy real_t1.fit_xgb
    'c_smote': ('smote', False),
    'd_borderline_smote': ('borderline', False),
    'e_adasyn': ('adasyn', False),
    'f_smote_parcial_mas_pesos': ('smote_parcial', True),  # SMOTE hasta 10 % de la clase mayoritaria + pesos
}
METRICS = ['roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'verdaderos_positivos', 'falsos_positivos', 'brier']


def neighbors(n_pos):
    """k menor que los positivos de entrenamiento: min(5, n_pos - 1)."""
    return min(5, n_pos - 1)


def resample(method, x, y, seed):
    """Devuelve (x, y, k usado, estado). Si el método no puede generar muestras, entrena sin remuestreo."""
    from imblearn.over_sampling import SMOTE, BorderlineSMOTE, ADASYN
    if method is None:
        return x, y, None, 'sin_remuestreo'
    k = neighbors(int(y.sum()))
    if k < 1:
        return x, y, k, 'omitido_pocos_positivos'
    sampler = {'smote': lambda: SMOTE(k_neighbors=k, random_state=seed),
        'borderline': lambda: BorderlineSMOTE(k_neighbors=k, m_neighbors=10, kind='borderline-1', random_state=seed),
        'adasyn': lambda: ADASYN(n_neighbors=k, random_state=seed),
        'smote_parcial': lambda: SMOTE(sampling_strategy=.10, k_neighbors=k, random_state=seed)}[method]()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            xr, yr = sampler.fit_resample(x, y)
    except (ValueError, RuntimeError) as error:  # p. ej. ADASYN sin vecinos de la clase mayoritaria
        return x, y, k, f'fallo:{type(error).__name__}'
    return xr, yr, k, 'ok' if len(yr) > len(y) else 'sin_muestras_nuevas'


def fit_predict(variant, x_tr, y_tr, x_te, seed):
    import xgboost as xgb
    method, weights = VARIANTS[variant]
    xr, yr, k, status = resample(method, x_tr, y_tr, seed)
    spw = float((yr == 0).sum() / max((yr == 1).sum(), 1)) if weights else 1.0
    model = xgb.XGBClassifier(**PARAMS, scale_pos_weight=spw).fit(xr, yr)
    return model.predict_proba(x_te)[:, 1], dict(k_neighbors=k, estado=status, positivos_entrenamiento=int(y_tr.sum()),
        filas_entrenamiento_tras_remuestreo=int(len(yr)), scale_pos_weight=round(spw, 3))


def cross_validation(frame, repetitions, folds=5):
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame[frame[TARGET].notna()].reset_index(drop=True)
    x, y, groups = features(data), data[TARGET].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    if x.isna().any().any():
        raise ValueError('Hay valores faltantes: SMOTE no los admite; revisar antes de comparar.')
    rows, folds_log = [], []
    for rep in range(repetitions):
        seed = SEED + rep
        splits = list(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(x, y, groups))
        for variant in VARIANTS:
            score = np.zeros(len(y))
            for f, (tr, te) in enumerate(splits):
                assert not set(groups[tr]) & set(groups[te]), 'Un estudiante quedó en entrenamiento y prueba.'
                score[te], info = fit_predict(variant, x.iloc[tr], y[tr], x.iloc[te], seed)
                folds_log.append(dict(esquema='cv', variante=variant, repeticion=rep, semilla_particion=seed, pliegue=f, **info))
            m = metrics(y, score, (score >= THRESHOLD).astype(int), probability=True)
            rows.append(dict(esquema='cv_agrupada_5x', variante=variant, repeticion=rep, semilla=seed, positivos_total=int(y.sum()),
                **{k: m[k] for k in METRICS}))
    return rows, folds_log


def temporal(frame, repetitions):
    """Entrenar con 2021-2023 y evaluar en 2024 sin estudiantes compartidos (igual que sensibilidad_real.py)."""
    tr = frame[frame.gestion.isin([2021, 2022, 2023])]
    te = frame[frame.gestion.isin([2024])]
    te = te[~te.codigo_anonimo.isin(tr.codigo_anonimo)]
    x_tr, y_tr, x_te, y_te = features(tr), tr[TARGET].astype(int).to_numpy(), features(te), te[TARGET].astype(int).to_numpy()
    rows, folds_log = [], []
    for variant in VARIANTS:
        stochastic = VARIANTS[variant][0] is not None
        for rep in range(repetitions if stochastic else 1):  # sin remuestreo el resultado es determinista
            seed = SEED + rep
            prob, info = fit_predict(variant, x_tr, y_tr, x_te, seed)
            m = metrics(y_te, prob, (prob >= THRESHOLD).astype(int), probability=True)
            rows.append(dict(esquema='temporal_2021_2023_a_2024', variante=variant, repeticion=rep, semilla=seed,
                positivos_total=int(y_te.sum()), **{k: m[k] for k in METRICS}))
            folds_log.append(dict(esquema='temporal', variante=variant, repeticion=rep, semilla_particion=seed, pliegue=0, **info))
    return rows, folds_log, dict(entrenamiento=len(tr), positivos_entrenamiento=int(y_tr.sum()), evaluacion=len(te),
        positivos_evaluacion=int(y_te.sum()))


def summary_table(results):
    """Media y desviación estándar entre repeticiones, más la diferencia pareada de AP contra la línea base."""
    out = []
    for (scheme, variant), g in results.groupby(['esquema', 'variante'], sort=False):
        row = dict(esquema=scheme, variante=variant, repeticiones=len(g))
        for k in METRICS:
            row[f'{k}_media'], row[f'{k}_de'] = g[k].mean(), g[k].std(ddof=1) if len(g) > 1 else 0.0
        base = results[(results.esquema == scheme) & (results.variante == 'b_scale_pos_weight')].set_index('repeticion')['average_precision']
        diff = g.set_index('repeticion')['average_precision'] - base.reindex(g.repeticion).fillna(base.iloc[0]).to_numpy()
        row['delta_ap_vs_base_media'], row['delta_ap_vs_base_de'] = diff.mean(), diff.std(ddof=1) if len(diff) > 1 else 0.0
        row['repeticiones_ap_mayor_que_base'] = int((diff > 1e-12).sum())
        out.append(row)
    return pd.DataFrame(out)


def main():
    import imblearn
    import sklearn
    import xgboost
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    parser.add_argument('--salida', default='../docs')
    parser.add_argument('--repeticiones', type=int, default=20)
    args = parser.parse_args()
    frame = load(args.excel)
    cv_rows, cv_log = cross_validation(frame, args.repeticiones)
    t_rows, t_log, t_info = temporal(frame, args.repeticiones)
    results = pd.DataFrame(cv_rows + t_rows)
    log = pd.DataFrame(cv_log + t_log)
    table = summary_table(results)
    out = Path(args.salida)
    results.to_csv(out / 'experimento_smote_resultados.csv', index=False)
    table.to_csv(out / 'experimento_smote_resumen_tabla.csv', index=False)
    log.to_csv(out / 'experimento_smote_pliegues.csv', index=False)
    versions = dict(imblearn=imblearn.__version__, sklearn=sklearn.__version__, xgboost=xgboost.__version__)
    print('Versiones:', versions)
    print('Temporal:', t_info)
    print('k_neighbors usados:', log.groupby(['esquema', 'variante'])['k_neighbors'].agg(['min', 'max']).dropna().to_dict('index'))
    print('Estados del remuestreo:', log.groupby(['variante', 'estado']).size().to_dict())
    pd.set_option('display.width', 220)
    cols = ['esquema', 'variante', 'roc_auc_media', 'roc_auc_de', 'average_precision_media', 'average_precision_de', 'sensibilidad_media',
        'precision_media', 'f1_media', 'verdaderos_positivos_media', 'falsos_positivos_media', 'delta_ap_vs_base_media',
        'repeticiones_ap_mayor_que_base']
    print(table[cols].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
