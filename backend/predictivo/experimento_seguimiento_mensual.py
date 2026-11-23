"""Experimento: seguimiento continuo (un corte al final de cada mes) en lugar de un único corte al 30 de abril.

Propuesta del autor y del revisor: el riesgo debe recalcularse a medida que avanza el año con lo que se sabe hasta
cada fecha (asistencia día por día, faltas recientes, rachas, notas de los trimestres ya cerrados).

Para cada gestión y cada fin de mes (febrero a octubre) se arman las variables SOLO con datos hasta ese día:
- asistencia acumulada (proporción de faltas, retrasos y licencias), faltas en los últimos 10 y 20 días registrados,
  racha actual de faltas, racha máxima, días de clase desde la última asistencia, tendencia semanal de las faltas;
- notas del T1 (promedio, mínima, áreas < 51, SER, SABER, HACER, autoevaluación, evolución) solo desde fin de abril;
- promedio del T2 solo desde fin de agosto; edad y grado (el género se excluye por no ser accionable).
Por cada corte se entrena un XGBoost (parámetros del modelo en uso) con validación por estudiante 5 x repeticiones,
y se compara con la regla operativa "k faltas seguidas" (k = 3 y 5).

Se mide en qué corte se detecta a cada abandono, si fue ANTES de que dejara de asistir (anticipación) o DESPUÉS
(detección del abandono en curso), y cuántos días antes del cierre del trimestre en que la escuela lo registra.
No modifica el modelo de producción ni la base.

Uso (desde backend):
    python -m predictivo.experimento_seguimiento_mensual --excel ../data/DATASET_INSTITUCION_2021_2025.xlsx --salida ../docs
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from predictivo.real_t1 import PARAMS, THRESHOLD

SEED = 1607
MESES = (2, 3, 4, 5, 6, 7, 8, 9, 10)
NOMBRE_MES = {2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun', 7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct'}
NOTAS_T1 = ['promedio_T1', 'nota_minima_T1', 'n_areas_bajo_51_T1', 'ser_media', 'saber_media', 'hacer_media', 'autoevaluacion_media',
    'tendencia_actividades', 'areas_en_caida']
ASIS = ['prop_faltas', 'prop_retrasos', 'prop_licencias', 'faltas_ult10', 'faltas_ult20', 'racha_actual', 'racha_max',
    'dias_desde_asistencia', 'tendencia_faltas', 'dias_registrados']
CONTEXTO = ['edad_31marzo', 'grado']


def pendiente(y):
    n = len(y)
    if n < 2:
        return 0.0
    x = np.arange(n)
    return float(np.polyfit(x, y, 1)[0])


def variables_asistencia(regs):
    """regs: [(fecha, estado)] ordenados hasta el corte."""
    if not regs:
        return {k: np.nan for k in ASIS}
    est = [e for _, e in regs]
    n = len(est)
    racha = maximo = 0
    for e in est:
        racha = racha + 1 if e == 'F' else 0
        maximo = max(maximo, racha)
    asistio = [i for i, e in enumerate(est) if e in ('A', 'R')]
    semanas = defaultdict(list)
    for d, e in regs:
        semanas[d.isocalendar()[:2]].append(e == 'F')
    return dict(prop_faltas=est.count('F') / n, prop_retrasos=est.count('R') / n, prop_licencias=est.count('L') / n,
        faltas_ult10=est[-10:].count('F'), faltas_ult20=est[-20:].count('F'), racha_actual=racha, racha_max=maximo,
        dias_desde_asistencia=(n - 1 - asistio[-1]) if asistio else n,
        tendencia_faltas=pendiente([np.mean(v) for _, v in sorted(semanas.items())]), dias_registrados=n)


def armar(excel, asistencia_csv):
    ds = pd.read_excel(excel, sheet_name='DATOS_REAL')
    ds = ds[ds.y_abandono_intra_anual.notna()].reset_index(drop=True)
    asis = pd.read_csv(asistencia_csv, parse_dates=['fecha'])
    por = defaultdict(list)
    for c, g, f, e in asis.itertuples(index=False):
        por[(c, g)].append((f.date(), e))
    for k in por:
        por[k].sort()
    cortes = {}
    for g, grupo in asis.groupby('gestion'):
        fechas = sorted(grupo.fecha.dt.date.unique())
        cortes[g] = {m: max(d for d in fechas if d.month == m) for m in MESES if any(d.month == m for d in fechas)}
    filas = []
    for r in ds.itertuples(index=False):
        regs = por.get((r.codigo_anonimo, r.gestion), [])
        asistio = [d for d, e in regs if e in ('A', 'R')]
        ultima = max(asistio) if asistio else None
        for m, corte in cortes[r.gestion].items():
            v = variables_asistencia([x for x in regs if x[0] <= corte])
            if m >= 4:  # las notas del T1 se conocen al cierre del trimestre (fin de abril)
                v.update({k: getattr(r, k) for k in NOTAS_T1})
            else:
                v.update({k: np.nan for k in NOTAS_T1})
            v['promedio_T2'] = r.POST_promedio_T2 if m >= 8 else np.nan  # el T2 cierra en agosto
            filas.append(dict(codigo_anonimo=r.codigo_anonimo, gestion=r.gestion, mes=m, corte=corte, y=int(r.y_abandono_intra_anual),
                trimestre_caida=r.trimestre_caida, ultima_asistencia=ultima, edad_31marzo=r.edad_31marzo, grado=r.grado, **v))
    return pd.DataFrame(filas)


def cierre_trimestre(g, trimestre):
    return date(g, 8, 31) if trimestre == 'T2' else date(g, 11, 30)


def evaluar_corte(d, repeticiones, folds=5):
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold
    cols = ASIS + NOTAS_T1 + ['promedio_T2'] + CONTEXTO
    x, y, groups = d[cols].astype(float), d.y.to_numpy(), d.codigo_anonimo.to_numpy()
    scores, aps, aucs, det, fa = np.zeros(len(y)), [], [], [], []
    for rep in range(repeticiones):
        s = np.zeros(len(y))
        for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED + rep).split(x, y, groups):
            mod = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y[tr] == 0).sum() / max(y[tr].sum(), 1))).fit(x.iloc[tr], y[tr])
            s[te] = mod.predict_proba(x.iloc[te])[:, 1]
        scores += s / repeticiones
        aps.append(average_precision_score(y, s))
        aucs.append(roc_auc_score(y, s))
        det.append(int(((s >= THRESHOLD) & (y == 1)).sum()))
        fa.append(int(((s >= THRESHOLD) & (y == 0)).sum()))
    reglas = {k: dict(detectados=int(((d.racha_actual >= k) & (d.y == 1)).sum()), falsas_alarmas=int(((d.racha_actual >= k) & (d.y == 0)).sum()))
        for k in (3, 5)}
    return scores, dict(average_precision=float(np.mean(aps)), average_precision_de=float(np.std(aps)), roc_auc=float(np.mean(aucs)),
        detectados=float(np.mean(det)), falsas_alarmas=float(np.mean(fa)), azar=float(y.mean()), regla=reglas)


def monitoreo_diario(asistencia_csv, ds, ks=(3, 5, 10)):
    """Revisión DIARIA de la regla 'k faltas seguidas' en todo el año: días de clase entre la última asistencia y la
    alerta, días de anticipación frente al cierre del trimestre en que se registra el abandono, y falsas alarmas
    (estudiantes que continuaron y alguna vez acumularon k faltas seguidas)."""
    asis = pd.read_csv(asistencia_csv, parse_dates=['fecha'])
    lab = {(r.codigo_anonimo, r.gestion): (int(r.y_abandono_intra_anual), r.trimestre_caida) for r in ds.itertuples(index=False)}
    por = defaultdict(list)
    for c, g, f, e in asis.itertuples(index=False):
        por[(c, g)].append((f.date(), e))
    out = {}
    for k in ks:
        demoras, anticipacion, detectados, falsas, rachas_continuan = [], [], 0, 0, defaultdict(int)
        for key, regs in por.items():
            if key not in lab:
                continue
            regs.sort()
            y, trim = lab[key]
            racha, alerta, maximo = 0, None, 0
            for i, (d, e) in enumerate(regs):
                racha = racha + 1 if e == 'F' else 0
                maximo = max(maximo, racha)
                if racha >= k and alerta is None:
                    alerta = (i, d)
            if y == 1:
                if alerta:
                    detectados += 1
                    asistio = [i for i, (_, e) in enumerate(regs) if e in ('A', 'R') and i < alerta[0]]
                    demoras.append(alerta[0] - asistio[-1] if asistio else alerta[0] + 1)
                    anticipacion.append((cierre_trimestre(key[1], trim) - alerta[1]).days)
            else:
                falsas += alerta is not None
                rachas_continuan[min(maximo, 10)] += 1
        out[f'{k}_faltas'] = dict(detectados=detectados, abandonos=sum(v[0] for v in lab.values()), falsas_alarmas=falsas,
            continuaron=sum(1 for v in lab.values() if v[0] == 0),
            dias_de_clase_desde_ultima_asistencia_mediana=float(np.median(demoras)) if demoras else None,
            dias_antes_del_cierre_del_trimestre_mediana=float(np.median(anticipacion)) if anticipacion else None,
            dias_antes_del_cierre_del_trimestre_min=int(min(anticipacion)) if anticipacion else None)
    out['continuaron_racha_maxima_de_faltas'] = {str(k): v for k, v in sorted(rachas_continuan.items())}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--excel', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    p.add_argument('--asistencia', default='../data/DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv')
    p.add_argument('--salida', default='../docs')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    d = armar(a.excel, a.asistencia)
    por_corte, puntajes = {}, {}
    for m in MESES:
        dm = d[d.mes == m].reset_index(drop=True)
        if dm.empty or dm.y.sum() == 0:
            continue
        s, res = evaluar_corte(dm, a.repeticiones)
        por_corte[NOMBRE_MES[m]] = res
        for (c, g), v in zip(zip(dm.codigo_anonimo, dm.gestion), s):
            puntajes[(c, g, m)] = v
    # Primera detección de cada abandono: modelo (puntaje medio >= 0,5) y regla de 5 faltas seguidas.
    casos = []
    for r in d[(d.y == 1)].drop_duplicates(['codigo_anonimo', 'gestion']).itertuples(index=False):
        filas = d[(d.codigo_anonimo == r.codigo_anonimo) & (d.gestion == r.gestion)].sort_values('mes')
        cierre = cierre_trimestre(r.gestion, r.trimestre_caida)
        modelo = next((f for f in filas.itertuples() if puntajes.get((f.codigo_anonimo, f.gestion, f.mes), 0) >= THRESHOLD), None)
        regla = next((f for f in filas.itertuples() if f.racha_actual >= 5), None)
        def info(f):
            if f is None:
                return None
            return dict(mes=NOMBRE_MES[f.mes], corte=f.corte.isoformat(),
                momento='antes de dejar de asistir' if r.ultima_asistencia is not None and f.corte < r.ultima_asistencia else 'después de dejar de asistir',
                dias_antes_del_cierre_del_trimestre=(cierre - f.corte).days)
        casos.append(dict(gestion=int(r.gestion), trimestre=r.trimestre_caida, ultima_asistencia=None if r.ultima_asistencia is None else r.ultima_asistencia.isoformat(),
            modelo=info(modelo), regla_5_faltas=info(regla)))
    reporte = dict(version='seguimiento-mensual-v1', dataset=Path(a.excel).name, matriculas=int(d.drop_duplicates(['codigo_anonimo', 'gestion']).shape[0]),
        abandonos=int(d.drop_duplicates(['codigo_anonimo', 'gestion']).y.sum()), variables=ASIS + NOTAS_T1 + ['promedio_T2'] + CONTEXTO,
        protocolo=f'Un corte por fin de mes (febrero a octubre), variables solo con datos hasta el corte; XGBoost por corte; '
            f'StratifiedGroupKFold 5 x {a.repeticiones} por estudiante; umbral 0,5. Regla operativa: racha actual de k faltas seguidas.',
        por_corte=por_corte, casos=casos,
        monitoreo_diario=monitoreo_diario(a.asistencia, pd.read_excel(a.excel, sheet_name='DATOS_REAL')))
    Path(a.salida, 'experimento_seguimiento_mensual.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"Matrículas {reporte['matriculas']} | abandonos {reporte['abandonos']}")
    print(f"{'corte':6s} {'AP':>6s} {'AUC':>6s} {'detecta':>8s} {'FA':>6s} | {'regla 3: det/FA':>16s} | {'regla 5: det/FA':>16s}")
    for m, v in por_corte.items():
        print(f"{m:6s} {v['average_precision']:6.3f} {v['roc_auc']:6.3f} {v['detectados']:8.2f} {v['falsas_alarmas']:6.1f} | "
            f"{v['regla'][3]['detectados']:>7d}/{v['regla'][3]['falsas_alarmas']:<8d} | {v['regla'][5]['detectados']:>7d}/{v['regla'][5]['falsas_alarmas']:<8d}")
    print('Monitoreo diario (regla de k faltas seguidas):', json.dumps(reporte['monitoreo_diario'], ensure_ascii=False))
    print('Primera detección de cada abandono:')
    for c in casos:
        print(' ', c['gestion'], c['trimestre'], 'última asistencia', c['ultima_asistencia'], '| modelo:', c['modelo'], '| regla 5:', c['regla_5_faltas'])


if __name__ == '__main__':
    main()
