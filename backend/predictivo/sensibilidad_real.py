"""Análisis de sensibilidad del modelo T1 real; escribe sensibilidad.json junto al artefacto."""
import json
import sys
from pathlib import Path

import numpy as np
from predictivo.real_t1 import load, features, fit_xgb, fit_logit, cross_validate, summarize, metrics, THRESHOLD, TARGETS

TARGET = TARGETS['abandono']


def compact(summary):
    keep = ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'tasa_marcados', 'ic95')
    return {n: {k: v for k, v in m.items() if k in keep} for n, m in summary.items() if n in ('xgboost', 'regresion_logistica', 'regla_promedio_T1')}


def temporal(frame, train_years, test_years):
    tr, te = frame[frame.gestion.isin(train_years)], frame[frame.gestion.isin(test_years)]
    te = te[~te.codigo_anonimo.isin(tr.codigo_anonimo)]  # sin estudiantes compartidos
    out = dict(entrenamiento=len(tr), evaluacion=len(te), positivos_evaluacion=int(te[TARGET].sum()))
    for name, fit in (('xgboost', fit_xgb), ('regresion_logistica', fit_logit)):
        prob = fit(features(tr), tr[TARGET].to_numpy()).predict_proba(features(te))[:, 1]
        out[name] = metrics(te[TARGET].to_numpy(), prob, (prob >= THRESHOLD).astype(int), True)
    return out


def main(excel, directory):
    frame = load(excel)
    absent = (frame['tasa_asistencia_T1'] == 0) & (frame[TARGET] == 1)
    result = {'casos_ausentes_en_T1': int(absent.sum())}
    data, y, groups, runs = cross_validate(frame[~absent], TARGET)
    result['sin_abandono_previo_al_corte'] = dict(filas=len(y), positivos=int(y.sum()), modelos=compact(summarize(y, groups, runs)))
    data, y, groups, runs = cross_validate(frame, TARGET)
    oof = np.mean([s for s, _ in runs['xgboost']], axis=0)
    by_source = {}
    for years, label in (([2021, 2022, 2023], '2021-2023'), ([2024], '2024'), ([2025], '2025')):
        mask = data.gestion.isin(years).to_numpy()
        by_source[label] = dict(filas=int(mask.sum()), positivos=int(y[mask].sum()),
            marcados_xgb=int((oof[mask] >= THRESHOLD).sum()),
            roc_auc_xgb=float(metrics(y[mask], oof[mask], (oof[mask] >= THRESHOLD).astype(int))['roc_auc']) if 0 < y[mask].sum() < mask.sum() else None)
    result['oof_por_periodo'] = by_source
    result['temporal_2021_2023_a_2024'] = temporal(frame, [2021, 2022, 2023], [2024])
    result['separacion_promedio_le_66'] = {f: dict(abandono=int(((frame.gestion.isin(ys)) & (frame.promedio_T1 <= 66) & (frame[TARGET] == 1)).sum()),
        sin_abandono=int(((frame.gestion.isin(ys)) & (frame.promedio_T1 <= 66) & (frame[TARGET] == 0)).sum()))
        for f, ys in (('2021-2023', [2021, 2022, 2023]), ('2024', [2024]), ('2025', [2025]))}
    Path(directory, 'sensibilidad.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:3])
