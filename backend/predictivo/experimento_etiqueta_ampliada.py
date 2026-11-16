"""Experimento: ampliar la etiqueta de abandono (11 casos) a "no aprueba el año" (abandono o reprobación, 35 casos).

No modifica el modelo de producción, los umbrales, las reglas RP01-RP05 ni la base de datos. Reutiliza de real_t1.py
la carga, las 19 variables del corte T1 (sin POST_*), los hiperparámetros, la validación cruzada agrupada por
estudiante (5 pliegues x 20 repeticiones, semillas 1607 a 1626), las líneas base (regresión logística y 3 reglas
simples con umbral elegido en entrenamiento) y el IC 95 % por bootstrap de estudiantes.

La etiqueta ampliada es la columna real y_reprobacion del dataset: incluye los 11 abandonos (todos figuran como
reprobados) y 24 reprobaciones más. Se usa solo como etiqueta; las columnas POST_* nunca son predictores.

Partes:
1. Validación cruzada con la etiqueta ampliada frente a las líneas base.
2. Desglose: cuántos de los 11 abandonos y de los 24 reprobados encuentra el modelo.
3. Comparación sobre los 11 abandonos: ¿el modelo entrenado con 35 casos los ordena mejor que el actual (11)?
4. Prueba temporal: entrenar 2021-2024 y evaluar en 2025 (estudiantes no vistos), que solo es posible con esta etiqueta.
5. Curva de aprendizaje: rendimiento según cuántos casos positivos hay en el entrenamiento.

Uso (desde backend):
    python -m predictivo.experimento_etiqueta_ampliada --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo.real_t1 import (load, features, metrics, cross_validate, summarize, fit_xgb, fit_logit, rule_threshold,
    PARAMS, THRESHOLD, TARGETS, RULES, FEATURE_NAMES)

SEED = 1607
ABANDONO = TARGETS['abandono']
AMPLIADA = 'y_reprobacion'
FRACCIONES = (.25, .5, .75, 1.0)


def cargar(excel):
    frame = load(excel)
    raw = pd.read_excel(excel, sheet_name='DATOS_REAL')
    assert (raw['codigo_anonimo'].to_numpy() == frame['codigo_anonimo'].to_numpy()).all()
    frame[AMPLIADA] = raw[AMPLIADA].astype(int)
    if (frame[ABANDONO] == 1).sum() != ((frame[ABANDONO] == 1) & (frame[AMPLIADA] == 1)).sum():
        raise ValueError('Se esperaba que todos los abandonos figuren como reprobados.')
    assert not any(c.startswith('POST_') for c in FEATURE_NAMES)
    return frame


def resumen_cv(frame, target, repeticiones):
    data, y, groups, runs = cross_validate(frame, target, repeticiones)
    return data, y, groups, runs, summarize(y, groups, runs)


def desglose(data, runs):
    """Detectados (media de repeticiones) entre abandonos y entre reprobados que no abandonaron."""
    ab = data[ABANDONO].to_numpy() == 1
    rep = (data[AMPLIADA].to_numpy() == 1) & ~ab
    out = {}
    for nombre in ('xgboost', 'regresion_logistica', 'regla_n_areas_bajo_51', 'regla_promedio_T1'):
        flags = np.array([f for _, f in runs[nombre]])
        out[nombre] = dict(abandonos_detectados=float(flags[:, ab].sum(1).mean()), abandonos=int(ab.sum()),
            reprobados_detectados=float(flags[:, rep].sum(1).mean()), reprobados=int(rep.sum()),
            falsas_alarmas=float(flags[:, data[AMPLIADA].to_numpy() == 0].sum(1).mean()))
    return out


def sobre_abandonos(data, runs_ampliada, runs_abandono):
    """AP y sensibilidad para los 11 abandonos usando los puntajes de cada modelo (media de repeticiones).
    En el modelo ampliado los 24 reprobados cuentan como 'no abandono' para esta medida."""
    y = data[ABANDONO].to_numpy().astype(int)
    from sklearn.metrics import average_precision_score, roc_auc_score
    out = {}
    for nombre, runs in (('modelo_actual_abandono', runs_abandono['xgboost']), ('modelo_ampliado', runs_ampliada['xgboost'])):
        aps = [average_precision_score(y, s) for s, _ in runs]
        aucs = [roc_auc_score(y, s) for s, _ in runs]
        det = [int(((y == 1) & (f == 1)).sum()) for _, f in runs]
        marc = [int(f.sum()) for _, f in runs]
        out[nombre] = dict(average_precision=float(np.mean(aps)), roc_auc=float(np.mean(aucs)),
            abandonos_detectados=float(np.mean(det)), marcados=float(np.mean(marc)))
    return out


def ic_temporal(y, score, flag, boots=2000, seed=SEED):
    from sklearn.metrics import average_precision_score
    rng = np.random.default_rng(seed)
    aps, sens = [], []
    while len(aps) < boots:
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            aps.append(average_precision_score(y[i], score[i]))
            sens.append(((y[i] == 1) & (flag[i] == 1)).sum() / y[i].sum())
    return dict(average_precision=[float(np.percentile(aps, 2.5)), float(np.percentile(aps, 97.5))],
        sensibilidad=[float(np.percentile(sens, 2.5)), float(np.percentile(sens, 97.5))])


def temporal(frame, estricta):
    """Entrenar con 2021-2024 y evaluar en 2025. Estricta: sin estudiantes que ya estaban en 2021-2024.
    Realista: toda la gestión 2025, como se usaría el sistema (el historial de esos estudiantes es de años anteriores)."""
    tr = frame[frame.gestion.isin([2021, 2022, 2023, 2024])]
    te = frame[(frame.gestion == 2025) & (~frame.codigo_anonimo.isin(tr.codigo_anonimo) if estricta else True)]
    x_tr, y_tr, x_te, y_te = features(tr), tr[AMPLIADA].to_numpy(), features(te), te[AMPLIADA].to_numpy()
    out = dict(entrenamiento=int(len(tr)), positivos_entrenamiento=int(y_tr.sum()), evaluacion=int(len(te)),
        positivos_evaluacion=int(y_te.sum()), excluidos_por_estar_en_entrenamiento=int(((frame.gestion == 2025)).sum() - len(te)),
        modelos={})
    for nombre, fit in (('xgboost', fit_xgb), ('regresion_logistica', fit_logit)):
        prob = fit(x_tr, y_tr).predict_proba(x_te)[:, 1]
        flag = (prob >= THRESHOLD).astype(int)
        out['modelos'][nombre] = {**metrics(y_te, prob, flag), 'ic95': ic_temporal(y_te, prob, flag)}
    for nombre, (col, sign) in RULES.items():
        s_tr, s_te = sign * x_tr[col].to_numpy(), sign * x_te[col].to_numpy()
        cut = rule_threshold(s_tr, y_tr)
        flag = (s_te >= cut).astype(int)
        out['modelos'][nombre] = {**metrics(y_te, s_te, flag), 'umbral_elegido_en_entrenamiento': float(sign * cut),
            'ic95': ic_temporal(y_te, s_te, flag)}
    out['modelos']['azar'] = dict(average_precision=float(y_te.mean()), roc_auc=.5)
    return out


def curva_aprendizaje(frame, target, repeticiones, folds=5):
    """Misma CV por estudiante; en cada pliegue de entrenamiento se conserva solo una fracción de los estudiantes
    positivos (los negativos completos). Se evalúa siempre en el pliegue de prueba completo."""
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame.reset_index(drop=True)
    x, y, groups = features(data), data[target].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    filas = []
    for rep in range(repeticiones):
        rng = np.random.default_rng(SEED + 500 + rep)
        scores = {f: np.zeros(len(y)) for f in FRACCIONES}
        npos = {f: [] for f in FRACCIONES}
        for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED + rep).split(x, y, groups):
            pos_students = np.unique(groups[tr][y[tr] == 1])
            orden = rng.permutation(pos_students)
            for f in FRACCIONES:
                keep = set(orden[:max(2, int(round(f * len(orden))))])
                sel = tr[(y[tr] == 0) | np.isin(groups[tr], list(keep))]
                sel = sel[~((y[sel] == 0) & np.isin(groups[sel], list(set(pos_students) - keep)))]
                npos[f].append(int(y[sel].sum()))
                scores[f][te] = fit_xgb(x.iloc[sel], y[sel]).predict_proba(x.iloc[te])[:, 1]
        for f in FRACCIONES:
            m = metrics(y, scores[f], (scores[f] >= THRESHOLD).astype(int))
            filas.append(dict(repeticion=rep, fraccion=f, positivos_entrenamiento_media=float(np.mean(npos[f])),
                **{k: m[k] for k in ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1')}))
    return pd.DataFrame(filas)


def main():
    import sklearn
    import xgboost
    p = argparse.ArgumentParser()
    p.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    p.add_argument('--salida', default='../docs')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    frame = cargar(a.excel)
    out = Path(a.salida)

    data_a, y_a, g_a, runs_a, sum_a = resumen_cv(frame, AMPLIADA, a.repeticiones)
    data_b, y_b, g_b, runs_b, sum_b = resumen_cv(frame, ABANDONO, a.repeticiones)
    assert (data_a['codigo_anonimo'].to_numpy() == data_b['codigo_anonimo'].to_numpy()).all()
    reporte = dict(
        version='etiqueta-ampliada-v1',
        etiqueta=dict(columna=AMPLIADA, descripcion='No aprueba el año: abandono o reprobación (dato real del dataset).',
            filas=int(len(y_a)), positivos=int(y_a.sum()), estudiantes_positivos=int(len(set(g_a[y_a == 1]))),
            abandonos_incluidos=int(data_a[ABANDONO].sum()), por_gestion={int(k): int(v) for k, v in
                data_a.groupby('gestion')[AMPLIADA].sum().items()}),
        protocolo=f'StratifiedGroupKFold 5 pliegues por estudiante x {a.repeticiones} repeticiones (semillas 1607+); '
            'IC 95 % bootstrap por estudiante (2000). Umbral 0,5 fijo. Mismos 19 predictores T1 e hiperparámetros del modelo en uso.',
        cv_ampliada=sum_a, cv_abandono=sum_b,
        desglose=desglose(data_a, runs_a),
        sobre_los_11_abandonos=sobre_abandonos(data_a, runs_a, runs_b),
        temporal_2025_realista=temporal(frame, False), temporal_2025_estricta=temporal(frame, True),
        versiones=dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__),
        nota='La nota anual incluye la del T1, por eso predecir la reprobación desde el T1 es más fácil que predecir el '
            'abandono; no es fuga (el T1 se conoce en la fecha de corte), pero obliga a comparar con reglas simples.')
    curvas = []
    for nombre, target in (('abandono', ABANDONO), ('ampliada', AMPLIADA)):
        curva = curva_aprendizaje(frame, target, a.repeticiones).assign(etiqueta=nombre)
        curvas.append(curva)
        agg = curva.drop(columns='etiqueta').groupby('fraccion').agg(['mean', 'std']).drop(columns='repeticion', level=0)
        reporte[f'curva_aprendizaje_{nombre}'] = [dict(fraccion=float(f), positivos_entrenamiento=float(r[('positivos_entrenamiento_media', 'mean')]),
            **{k: float(r[(k, 'mean')]) for k in ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1')},
            **{f'{k}_std': float(r[(k, 'std')]) for k in ('average_precision', 'sensibilidad')}) for f, r in agg.iterrows()]
    pd.concat(curvas).to_csv(out / 'experimento_etiqueta_ampliada_curva.csv', index=False)
    (out / 'experimento_etiqueta_ampliada.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')

    def fila(nombre, m):
        ic = m.get('ic95', {})
        f = lambda k: f"{m.get(k, float('nan')):.3f}" + (f" [{ic[k][0]:.2f}-{ic[k][1]:.2f}]" if k in ic else '')
        return f"  {nombre:24s} AUC {f('roc_auc')}  AP {f('average_precision')}  sens {f('sensibilidad')}  prec {f('precision')}  F1 {f('f1')}"
    print('Versiones:', reporte['versiones'])
    print('Etiqueta ampliada:', reporte['etiqueta'])
    for titulo, s in (('CV etiqueta ampliada (35)', sum_a), ('CV abandono (11, modelo actual)', sum_b)):
        print(titulo)
        for n, m in s.items():
            print(fila(n, m))
    print('Desglose:', json.dumps(reporte['desglose'], indent=1))
    print('Sobre los 11 abandonos:', json.dumps(reporte['sobre_los_11_abandonos'], indent=1))
    for clave in ('temporal_2025_realista', 'temporal_2025_estricta'):
        t = reporte[clave]
        print(clave, {k: v for k, v in t.items() if k != 'modelos'})
        for n, m in t['modelos'].items():
            print(fila(n, m), ' VP', m.get('verdaderos_positivos'), ' FP', m.get('falsos_positivos'))
    for nombre in ('abandono', 'ampliada'):
        print('Curva de aprendizaje', nombre)
        for r in reporte[f'curva_aprendizaje_{nombre}']:
            print(f"  fraccion {r['fraccion']:.2f}  positivos ~ {r['positivos_entrenamiento']:.1f}  AP {r['average_precision']:.3f} +- {r['average_precision_std']:.3f}"
                f"  sens {r['sensibilidad']:.3f}  F1 {r['f1']:.3f}")


if __name__ == '__main__':
    main()
