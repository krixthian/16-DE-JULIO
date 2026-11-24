"""Seguimiento mensual con y sin las 8 variables del desglose de notas (15 frente a 23), misma validación.

Criterio fijado el 23/11/2026 ANTES de ver resultados: se adopta solo si el IC 95 % de la diferencia de AP (23 - 15) queda
por encima de cero en mayo, junio o julio y en ningún mes queda por debajo de cero. Validación: StratifiedGroupKFold
5 x 20 por estudiante, mismos pliegues para ambos; IC por bootstrap de estudiantes pareado. Mismos hiperparámetros.
Los archivos de origen no están verificados (docs/CONSISTENCIA_REGISTROS.md): es una prueba técnica.

Uso (desde backend): python -m predictivo.experimento_desglose
"""
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from predictivo import desglose as dg
from predictivo.experimento_seguimiento_mensual import MESES, NOMBRE_MES, armar
from predictivo.extraer_desglose import DATOS, SALIDA
from predictivo.real_t1 import PARAMS, THRESHOLD
from predictivo.seguimiento import VARIABLES_V1 as VARIABLES

DOCS = DATOS.parent / 'docs'
NUEVAS = list(dg.VARIABLES)
REP, FOLDS, SEED, BOOT = 20, 5, 1607, 1000
CLAVE = ('may', 'jun', 'jul')


def ap(y, s):
    o = np.argsort(-s, kind='mergesort')
    y, s = y[o], s[o]
    tp = np.cumsum(y)
    fin = np.r_[s[1:] != s[:-1], True]  # empates: un solo punto, como en scikit-learn
    tp, n = tp[fin], (np.arange(len(y)) + 1)[fin]
    return float(np.sum(np.diff(np.r_[0, tp]) * tp / n) / tp[-1])


def mes(args):
    import xgboost as xgb
    from sklearn.model_selection import StratifiedGroupKFold
    nombre, dm = args
    y, groups = dm.y.to_numpy(), dm.codigo_anonimo.to_numpy()
    conj = {'15': VARIABLES, '23': VARIABLES + NUEVAS}
    S = {k: [] for k in conj}
    for rep in range(REP):
        s = {k: np.zeros(len(y)) for k in conj}
        for tr, te in StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=SEED + rep).split(dm, y, groups):
            assert not set(groups[tr]) & set(groups[te])
            for k, cols in conj.items():
                x = dm[cols].astype(float)
                mod = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y[tr] == 0).sum() / max(y[tr].sum(), 1))).fit(x.iloc[tr], y[tr])
                s[k][te] = mod.predict_proba(x.iloc[te])[:, 1]
        for k in conj:
            S[k].append(s[k])
    out = dict(mes=nombre, azar=float(y.mean()))
    for k in conj:
        out[k] = dict(ap=float(np.mean([ap(y, s) for s in S[k]])), vp=float(np.mean([((s >= THRESHOLD) & (y == 1)).sum() for s in S[k]])),
            fa=float(np.mean([((s >= THRESHOLD) & (y == 0)).sum() for s in S[k]])))
    idx = {}
    for i, g in enumerate(groups):
        idx.setdefault(g, []).append(i)
    est = [np.array(v) for v in idx.values()]
    rng = np.random.default_rng(SEED)
    difs, aps = [], {k: [] for k in conj}
    for _ in range(BOOT):
        b = np.concatenate([est[j] for j in rng.integers(0, len(est), len(est))])
        if y[b].sum() == 0:
            continue
        v = {k: np.mean([ap(y[b], s[b]) for s in S[k]]) for k in conj}
        difs.append(v['23'] - v['15'])
        for k in conj:
            aps[k].append(v[k])
    out['diferencia'] = out['23']['ap'] - out['15']['ap']
    out['ic95_diferencia'] = [float(x) for x in np.percentile(difs, [2.5, 97.5])]
    for k in conj:
        out[k]['ic95'] = [float(x) for x in np.percentile(aps[k], [2.5, 97.5])]
    x = dm[conj['23']].astype(float)
    fin = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y == 0).sum() / y.sum())).fit(x, y)
    g = fin.get_booster().get_score(importance_type='total_gain')
    out['peso_desglose'] = {k: round(g[k] / sum(g.values()), 4) for k in NUEVAS if k in g}
    return out


def main():
    d = dg.con_desglose(armar(DATOS / 'DATASET_INSTITUCION_2021_2025.xlsx', DATOS / 'DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv'), SALIDA)
    with ProcessPoolExecutor(5) as ex:
        res = list(ex.map(mes, [(NOMBRE_MES[m], d[d.mes == m].reset_index(drop=True)) for m in MESES]))
    mejora = [r['mes'] for r in res if r['mes'] in CLAVE and r['ic95_diferencia'][0] > 0]
    empeora = [r['mes'] for r in res if r['ic95_diferencia'][1] < 0]
    final = dict(criterio=__doc__.split('\n\n')[1], variables_nuevas=dg.VARIABLES, matriculas=int(len(d[d.mes == 5])), abandonos=int(d[d.mes == 5].y.sum()),
        meses=res, mejora_clara=mejora, empeora_claro=empeora, se_adopta=bool(mejora and not empeora))
    (DOCS / 'experimento_desglose.json').write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in res:
        print(f"{r['mes']}: azar {r['azar']:.3f} | 15: AP {r['15']['ap']:.3f} VP {r['15']['vp']:.1f} FA {r['15']['fa']:.1f} | 23: AP {r['23']['ap']:.3f} VP {r['23']['vp']:.1f} FA {r['23']['fa']:.1f}"
            f" | dif {r['diferencia']:+.3f} IC [{r['ic95_diferencia'][0]:+.3f}, {r['ic95_diferencia'][1]:+.3f}] | peso {sum(r['peso_desglose'].values()):.1%} {r['peso_desglose']}")
    print('mejora clara:', mejora, '| empeora claro:', empeora, '| SE ADOPTA:', final['se_adopta'])


if __name__ == '__main__':
    main()
