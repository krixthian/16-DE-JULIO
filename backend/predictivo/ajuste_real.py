"""Objetivo 2: ajuste de hiperparámetros de XGBoost con validación anidada agrupada por estudiante.

Bucle externo (5 pliegues x repeticiones) para estimar el desempeño; bucle interno (4 pliegues, solo con el
entrenamiento externo) para elegir parámetros por average precision. El modelo base, la regresión logística y la
regla de promedio se evalúan en los MISMOS pliegues externos. La calibración se ajusta con las predicciones
internas fuera de pliegue, nunca con el pliegue externo. El umbral 0,5 no se ajusta.

Criterio de adopción fijado ANTES de ejecutar: se adopta el modelo ajustado solo si el IC 95 % pareado
(bootstrap por estudiante) de la diferencia de AP (ajustado - base) queda entero por encima de 0. Una
calibración se adopta solo si el IC 95 % pareado de la diferencia de Brier (calibrado - sin calibrar) queda
entero por debajo de 0 y su AP no empeora de forma distinguible.
"""
import hashlib
import json
from datetime import datetime
from itertools import product
from pathlib import Path

from predictivo.real_t1 import (FEATURE_NAMES, PARAMS, THRESHOLD, TARGETS, features, fit_logit, load, metrics,
    rule_threshold)

VERSION_AJUSTE = 'ajuste-anidado-v1'
TARGET = TARGETS['abandono']
BASE = dict(max_depth=3, learning_rate=.05, n_estimators=80, min_child_weight=1, subsample=.8, colsample_bytree=.8)
# 108 configuraciones: espacio pequeño y justificado para 11 positivos (árboles poco profundos, pocas rondas).
GRID = [dict(max_depth=d, learning_rate=lr, n_estimators=n, min_child_weight=w, subsample=s, colsample_bytree=s)
    for d, lr, w, s, n in product((2, 3, 4), (.03, .05, .1), (1, 3), (.8, 1.0), (50, 80, 150))]
FIXED = dict(objective='binary:logistic', eval_metric='logloss', tree_method='hist', random_state=1607, n_jobs=2)
PROB_MODELS = ('xgboost_base', 'xgboost_ajustado', 'xgboost_base_sigmoide', 'xgboost_ajustado_sigmoide',
    'xgboost_ajustado_isotonica', 'regresion_logistica')
THRESHOLDS = (.1, .2, .3, .4, .5, .6, .7, .8, .9)


def key(params):
    return f"d{params['max_depth']}-lr{params['learning_rate']}-n{params['n_estimators']}-w{params['min_child_weight']}-s{params['subsample']}"


def fit_xgb(x, y, params):
    import xgboost as xgb
    weight = float((y == 0).sum() / max((y == 1).sum(), 1))
    return xgb.XGBClassifier(**FIXED, **params, scale_pos_weight=weight).fit(x, y)


def predict(model, x, rounds=None):
    return model.predict_proba(x, iteration_range=(0, rounds) if rounds else None)[:, 1]


def inner_oof(x, y, groups, seed, folds=4):
    """Predicciones internas fuera de pliegue para cada configuración (un ajuste de 150 rondas sirve a 50/80/150)."""
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    splits = list(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(x, y, groups))
    oof = {key(p): np.zeros(len(y)) for p in GRID}
    trunks = {}
    for p in GRID:
        trunks.setdefault(tuple((k, v) for k, v in p.items() if k != 'n_estimators'), set()).add(p['n_estimators'])
    for trunk, rounds in sorted(trunks.items()):
        params = {**dict(trunk), 'n_estimators': max(rounds)}
        for tr, te in splits:
            if len(set(y[tr])) < 2:
                raise ValueError('Un pliegue interno quedó sin positivos.')
            model = fit_xgb(x.iloc[tr], y[tr], params)
            for n in sorted(rounds):
                oof[key({**params, 'n_estimators': n})][te] = predict(model, x.iloc[te], n)
    return oof


def select(oof, y):
    """Mayor AP interna; empates a favor del modelo más simple (menor profundidad, menos rondas)."""
    from sklearn.metrics import average_precision_score
    scored = [(round(average_precision_score(y, oof[key(p)]), 10), -p['max_depth'], -p['n_estimators'], p['min_child_weight'], key(p), p)
        for p in GRID]
    return max(scored, key=lambda t: t[:4])[5]


def calibrators(raw, y):
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    import numpy as np
    # Recorte mínimo: uno mayor crearía empates artificiales y bajaría el AUC por un artefacto numérico.
    def logit(p):
        p = np.clip(np.asarray(p, dtype=float), 1e-15, 1 - 1e-15)
        return np.log(p / (1 - p)).reshape(-1, 1)
    platt = LogisticRegression(C=1e6, max_iter=1000).fit(logit(raw), y)
    iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(raw, y)
    return (lambda p: platt.predict_proba(logit(p))[:, 1]), iso.predict


def nested(frame, repetitions=20, folds=5, seed=1607, inner_folds=4):
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame[frame[TARGET].notna()].reset_index(drop=True)
    x, y, groups = features(data), data[TARGET].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    names = [*PROB_MODELS, 'regla_promedio_T1']
    runs = {n: [] for n in names}
    chosen = []
    for rep in range(repetitions):
        score = {n: np.zeros(len(y)) for n in names}
        for fold, (tr, te) in enumerate(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed + rep).split(x, y, groups)):
            xtr, ytr = x.iloc[tr], y[tr]
            oof = inner_oof(xtr, ytr, groups[tr], seed + 1000 * rep + fold, inner_folds)
            best = select(oof, ytr)
            chosen.append({'repeticion': rep, 'pliegue': fold, **best})
            for name, params in (('xgboost_base', BASE), ('xgboost_ajustado', best)):
                score[name][te] = predict(fit_xgb(xtr, ytr, params), x.iloc[te])
            sig, iso = calibrators(oof[key(BASE)], ytr)
            score['xgboost_base_sigmoide'][te] = sig(score['xgboost_base'][te])
            sig, iso = calibrators(oof[key(best)], ytr)
            score['xgboost_ajustado_sigmoide'][te] = sig(score['xgboost_ajustado'][te])
            score['xgboost_ajustado_isotonica'][te] = iso(score['xgboost_ajustado'][te])
            score['regresion_logistica'][te] = fit_logit(xtr, ytr).predict_proba(x.iloc[te])[:, 1]
            s = -x['promedio_T1'].to_numpy()
            cut = rule_threshold(s[tr], ytr)
            score['regla_promedio_T1'][te] = s[te]
            score.setdefault('_corte_regla', np.zeros(len(y)))[te] = cut
        for n in names:
            flag = (score[n] >= (score['_corte_regla'] if n == 'regla_promedio_T1' else THRESHOLD)).astype(int)
            runs[n].append((score[n].copy(), flag))
    return data, y, groups, runs, chosen


def bootstrap_samples(y, groups, boots=2000, seed=1607):
    import numpy as np
    rng = np.random.default_rng(seed)
    students = np.unique(groups)
    index = {s: np.flatnonzero(groups == s) for s in students}
    samples = []
    while len(samples) < boots:
        rows = np.concatenate([index[s] for s in rng.choice(students, len(students))])
        if 0 < y[rows].sum() < len(rows):
            samples.append(rows)
    return samples


def summarize(y, groups, runs, boots=2000, seed=1607):
    """Media entre repeticiones, IC 95 % bootstrap por estudiante y diferencias pareadas."""
    import numpy as np
    samples = bootstrap_samples(y, groups, boots, seed)
    keys = ('roc_auc', 'average_precision', 'precision', 'sensibilidad', 'f1', 'brier')
    draws = {}
    summary = {}
    for name, reps in runs.items():
        probability = name in PROB_MODELS
        per_rep = [metrics(y, s, f, probability) for s, f in reps]
        point = {k: float(np.mean([m[k] for m in per_rep])) for k in per_rep[0]}
        draws[name] = {k: [] for k in keys if probability or k != 'brier'}
        for b, rows in enumerate(samples):
            s, f = reps[b % len(reps)]
            m = metrics(y[rows], s[rows], f[rows], probability)
            for k in draws[name]:
                draws[name][k].append(m[k])
        point['ic95'] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws[name].items()}
        summary[name] = point
    summary['siempre_continuidad'] = {'average_precision': float(y.mean()), 'roc_auc': .5, 'sensibilidad': 0.0,
        'precision': 0.0, 'f1': 0.0, 'tasa_marcados': 0.0}
    pairs = {}
    for a, b in (('xgboost_ajustado', 'xgboost_base'), ('xgboost_base', 'regresion_logistica'),
            ('xgboost_ajustado', 'regresion_logistica'), ('xgboost_base_sigmoide', 'xgboost_base'),
            ('xgboost_ajustado_sigmoide', 'xgboost_ajustado'), ('xgboost_ajustado_isotonica', 'xgboost_ajustado')):
        diff = {}
        for k in ('roc_auc', 'average_precision', 'brier'):
            if k in draws[a] and k in draws[b]:
                d = np.array(draws[a][k]) - np.array(draws[b][k])
                diff[k] = {'media': float(summary[a][k] - summary[b][k]), 'ic95': [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        pairs[f'{a} - {b}'] = diff
    return summary, pairs


def stability(chosen):
    from collections import Counter
    total = len(chosen)
    configs = Counter(key(c) for c in chosen)
    return {'pliegues_externos': total, 'configuraciones_distintas': len(configs),
        'mas_frecuentes': [{'config': k, 'veces': v, 'proporcion': v / total} for k, v in configs.most_common(5)],
        'por_parametro': {p: {str(k): v / total for k, v in sorted(Counter(c[p] for c in chosen).items())}
            for p in ('max_depth', 'learning_rate', 'n_estimators', 'min_child_weight', 'subsample')},
        'base_elegida': configs.get(key(BASE), 0) / total}


def calibration_table(y, runs, bins=(0, .05, .1, .2, .3, .5, .7, .9, 1.0001)):
    import numpy as np
    out = {}
    for name in PROB_MODELS:
        prob = np.mean([s for s, _ in runs[name]], axis=0)
        rows = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            mask = (prob >= lo) & (prob < hi)
            if mask.any():
                rows.append({'desde': lo, 'hasta': min(hi, 1.0), 'n': int(mask.sum()), 'prob_media': float(prob[mask].mean()),
                    'tasa_observada': float(y[mask].mean()), 'positivos': int(y[mask].sum())})
        out[name] = {'tabla': rows, 'prob_media_global': float(prob.mean()), 'tasa_observada_global': float(y.mean())}
    return out


def threshold_table(y, runs, name):
    import numpy as np
    out = []
    for t in THRESHOLDS:
        per = [metrics(y, s, (s >= t).astype(int)) for s, _ in runs[name]]
        out.append({'umbral': t, **{k: float(np.mean([m[k] for m in per])) for k in
            ('sensibilidad', 'precision', 'tasa_marcados', 'verdaderos_positivos', 'falsos_positivos')}})
    return out


def temporal(frame, train_years=(2021, 2022, 2023), test_years=(2024,), seed=1607):
    tr, te = frame[frame.gestion.isin(train_years)], frame[frame.gestion.isin(test_years)]
    te = te[~te.codigo_anonimo.isin(tr.codigo_anonimo)]
    xtr, ytr, xte, yte = features(tr), tr[TARGET].astype(int).to_numpy(), features(te), te[TARGET].astype(int).to_numpy()
    oof = inner_oof(xtr, ytr, tr['codigo_anonimo'].to_numpy(), seed)
    best = select(oof, ytr)
    out = dict(entrenamiento=len(tr), evaluacion=len(te), positivos_evaluacion=int(yte.sum()), parametros_ajustados=best)
    for name, prob in (('xgboost_base', predict(fit_xgb(xtr, ytr, BASE), xte)), ('xgboost_ajustado', predict(fit_xgb(xtr, ytr, best), xte)),
            ('regresion_logistica', fit_logit(xtr, ytr).predict_proba(xte)[:, 1])):
        out[name] = {f'umbral_{t}': metrics(yte, prob, (prob >= t).astype(int), True) for t in (.5, .8)}
    s = -xtr['promedio_T1'].to_numpy()
    cut = rule_threshold(s, ytr)
    se = -xte['promedio_T1'].to_numpy()
    out['regla_promedio_T1'] = metrics(yte, se, (se >= cut).astype(int))
    return out


def decide(pairs, summary):
    ap = pairs['xgboost_ajustado - xgboost_base']['average_precision']['ic95']
    tuned = ap[0] > 0
    candidate = 'xgboost_ajustado' if tuned else 'xgboost_base'
    calib = None
    for method in ('sigmoide', 'isotonica'):
        name = f'{candidate}_{method}'
        pair = pairs.get(f'{name} - {candidate}')
        if pair and pair['brier']['ic95'][1] < 0 and pair['average_precision']['ic95'][0] > -0.05:
            calib = calib or method
    return {'criterio': 'Ajustado si IC 95 % pareado de AP (ajustado - base) > 0; calibración si IC 95 % de Brier (calibrado - sin calibrar) < 0 sin empeorar AP de forma distinguible.',
        'adoptar_ajustado': tuned, 'ic95_diferencia_ap': ap, 'calibracion_adoptada': calib,
        'conclusion': ('El ajuste mejora la AP de forma distinguible: se adopta.' if tuned else
            'El ajuste no mejora de forma distinguible: se ajustó y el modelo base resultó adecuado.')}


def run(excel, output, repetitions=20):
    import numpy as np
    import sklearn
    import xgboost as xgb
    frame = load(excel)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    data, y, groups, runs, chosen = nested(frame, repetitions)
    summary, pairs = summarize(y, groups, runs)
    decision = decide(pairs, summary)
    adopted = 'xgboost_ajustado' if decision['adoptar_ajustado'] else 'xgboost_base'
    report = dict(version=VERSION_AJUSTE, generado_en=datetime.now().isoformat(timespec='seconds'), origen='REAL',
        protocolo=f'Validación anidada: externo StratifiedGroupKFold 5 x {repetitions} repeticiones (semilla 1607+rep); interno '
            'StratifiedGroupKFold 4 por estudiante sobre el entrenamiento externo, selección por AP. Calibración ajustada con '
            'predicciones internas fuera de pliegue. Umbral 0,5 fijo. IC 95 % bootstrap por estudiante (2000), pareado.',
        espacio=dict(max_depth=[2, 3, 4], learning_rate=[.03, .05, .1], n_estimators=[50, 80, 150], min_child_weight=[1, 3],
            subsample_y_colsample=[.8, 1.0], configuraciones=len(GRID), scale_pos_weight='negativos/positivos del entrenamiento'),
        base=BASE, filas=int(len(y)), positivos=int(y.sum()), estudiantes=int(len(set(groups))),
        elegidos=chosen, estabilidad=stability(chosen), modelos=summary, diferencias_pareadas=pairs, decision=decision,
        calibracion=calibration_table(y, runs), umbrales={n: threshold_table(y, runs, n) for n in ('xgboost_base', 'xgboost_ajustado')},
        temporal_2021_2023_a_2024=temporal(frame), modelo_recomendado=adopted,
        dataset_sha256=hashlib.sha256(Path(excel).read_bytes()).hexdigest(),
        versiones={'xgboost': xgb.__version__, 'sklearn': sklearn.__version__, 'numpy': np.__version__})
    (out / 'reporte_ajuste.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    # Predicciones fuera de pliegue (sin códigos) para las figuras de curvas con IC.
    ids = {g: i for i, g in enumerate(np.unique(groups))}
    np.savez_compressed(out / 'oof_ajuste.npz', y=y, grupo=np.array([ids[g] for g in groups]),
        **{n: np.array([s for s, _ in runs[n]]) for n in runs})
    return report


def print_report(directory, excel=None):
    directory = Path(directory)
    report = json.loads((directory / 'reporte_ajuste.json').read_text(encoding='utf-8'))
    print(f"Ajuste {report['version']} · generado {report['generado_en']} · origen {report['origen']} · {report['filas']} filas, {report['positivos']} positivos")
    if excel:
        ok = hashlib.sha256(Path(excel).read_bytes()).hexdigest() == report['dataset_sha256']
        print(f"SHA-256 dataset: {report['dataset_sha256'][:16]}…  {'OK, mismo Excel' if ok else 'NO COINCIDE: el Excel cambió'}")
    print(f"Protocolo: {report['protocolo']}\nEspacio: {report['espacio']['configuraciones']} configuraciones · base {key(report['base'])}")
    st = report['estabilidad']
    print(f"\n== Estabilidad: {st['configuraciones_distintas']} configuraciones distintas en {st['pliegues_externos']} pliegues externos; base elegida {st['base_elegida']:.0%}")
    for c in st['mas_frecuentes']:
        print(f"  {c['config']:32} {c['veces']:3d} veces ({c['proporcion']:.0%})")
    for p, dist in st['por_parametro'].items():
        print(f"  {p:18} " + '  '.join(f"{k}: {v:.0%}" for k, v in dist.items()))
    print(f"\n{'Modelo':28}{'ROC-AUC':>8} {'IC 95 %':>13}{'AP':>8} {'IC 95 %':>13}{'Sens.':>7}{'Prec.':>7}{'F1':>7}{'%marc.':>8}{'Brier':>8}")
    for name, m in report['modelos'].items():
        ic = m.get('ic95', {})
        ci = lambda k: f"[{ic[k][0]:.2f}-{ic[k][1]:.2f}]" if k in ic else ''
        brier = f"{m['brier']:8.4f}" if 'brier' in m else ''
        print(f"{name:28}{m['roc_auc']:8.3f} {ci('roc_auc'):>13}{m['average_precision']:8.3f} {ci('average_precision'):>13}"
            f"{m['sensibilidad']:7.2f}{m['precision']:7.2f}{m['f1']:7.2f}{m['tasa_marcados'] * 100:7.1f}%{brier}")
    print('\n== Diferencias pareadas (IC 95 %)')
    for pair, diff in report['diferencias_pareadas'].items():
        print(f"  {pair:50} " + '  '.join(f"{k} {d['media']:+.3f} [{d['ic95'][0]:+.3f}, {d['ic95'][1]:+.3f}]" for k, d in diff.items()))
    t = report['temporal_2021_2023_a_2024']
    print(f"\n== Temporal 2021-2023 -> 2024: {t['evaluacion']} matrículas, {t['positivos_evaluacion']} abandonos; ajustado eligió {key(t['parametros_ajustados'])}")
    for name in ('xgboost_base', 'xgboost_ajustado', 'regresion_logistica'):
        m = t[name]['umbral_0.5']
        print(f"  {name:22} AUC {m['roc_auc']:.3f} · AP {m['average_precision']:.3f} · sens {m['sensibilidad']:.2f} · prec {m['precision']:.2f} · "
            f"{m['verdaderos_positivos']} detectados, {m['falsos_positivos']} falsas alarmas (umbral 0,5)")
    d = report['decision']
    print(f"\n== Decisión: {d['conclusion']}\n   IC 95 % de AP (ajustado - base): [{d['ic95_diferencia_ap'][0]:+.3f}, {d['ic95_diferencia_ap'][1]:+.3f}] · calibración adoptada: {d['calibracion_adoptada'] or 'ninguna'}")
    if not excel:
        return True
    print('\nRecalculando la validación anidada desde el Excel…')
    import numpy as np
    frame = load(excel)
    reps = len({c['repeticion'] for c in report['elegidos']})
    _, y, groups, runs, chosen = nested(frame, reps)
    summary, _ = summarize(y, groups, runs)
    same = [key(c) for c in chosen] == [key(c) for c in report['elegidos']]
    print(f"  parámetros elegidos por pliegue        {'idénticos' if same else 'DIFIEREN'}")
    for name, m in report['modelos'].items():
        diff = max(abs(summary[name][k] - m[k]) for k in ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'tasa_marcados'))
        same &= diff < 1e-9
        print(f"  {name:38}{'idéntico' if diff < 1e-9 else f'difiere ({diff:.2e})'}")
    print('RESULTADO: ajuste reproducido exactamente.' if same else 'RESULTADO: hay diferencias, revisar versiones o datos.')
    return same
