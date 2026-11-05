"""Modelo con el dataset real consolidado: corte al cierre del 1.er trimestre (T1).

Las columnas POST_* (T2, T3 y cierre anual) nunca entran como predictores. Con tan pocos casos
positivos no hay holdout temporal posible (2025 no tiene abandonos): se usa validación cruzada
agrupada por estudiante y repetida, con intervalos bootstrap por estudiante.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

VERSION = 'real-t1-v1'
AREAS = ('CNAT', 'LCO', 'SOC', 'APV', 'EFI', 'EMU', 'MAT', 'TTG', 'VER')
FEATURE_NAMES = [f'{a}_T1' for a in AREAS] + ['promedio_T1', 'nota_minima_T1', 'n_areas_bajo_51_T1', 'faltas_T1',
    'atrasos_T1', 'licencias_T1', 'tasa_asistencia_T1', 'edad_31marzo', 'grado', 'genero_f']
DESCRIPTIONS = {**{f'{a}_T1': f'Nota del área {a} en T1 (0 a 100).' for a in AREAS},
    'promedio_T1': 'Promedio de las 9 áreas en T1, redondeado como en el cuaderno.',
    'nota_minima_T1': 'Nota más baja del estudiante en T1.',
    'n_areas_bajo_51_T1': 'Áreas con nota menor a 51 en T1.',
    'faltas_T1': 'Faltas registradas en T1.', 'atrasos_T1': 'Atrasos registrados en T1.',
    'licencias_T1': 'Licencias registradas en T1.',
    'tasa_asistencia_T1': 'Días asistidos / días lectivos de T1 (0 a 1).',
    'edad_31marzo': 'Edad cumplida al 31 de marzo.', 'grado': 'Grado de primaria (1 a 6).',
    'genero_f': '1 si el registro indica género femenino.'}
TARGETS = {'abandono': 'y_abandono_intra_anual', 'no_continua': 'y_no_continua_siguiente'}
PARAMS = dict(n_estimators=80, max_depth=3, learning_rate=.05, subsample=.8, colsample_bytree=.8,
    objective='binary:logistic', eval_metric='logloss', tree_method='hist', random_state=1607, n_jobs=2)
THRESHOLD = .5
RULES = {'regla_promedio_T1': ('promedio_T1', -1), 'regla_n_areas_bajo_51': ('n_areas_bajo_51_T1', 1),
    'regla_faltas_T1': ('faltas_T1', 1)}


def load(path):
    import pandas as pd
    raw = pd.read_excel(path, sheet_name='DATOS_REAL')
    frame = raw[['codigo_anonimo', 'gestion', 'grado', 'paralelo', *TARGETS.values()]].copy()
    for name in FEATURE_NAMES:
        if name == 'tasa_asistencia_T1':
            frame[name] = raw['dias_asistidos_T1'] / raw['dias_lectivos_T1'].where(raw['dias_lectivos_T1'] > 0)
        elif name == 'genero_f':
            frame[name] = raw['genero'].map({'F': 1, 'M': 0})
        else:
            frame[name] = raw[name]
    if any(n.startswith('POST_') for n in FEATURE_NAMES):
        raise ValueError('Las columnas POST_* no pueden ser predictores.')
    return frame


def features(frame):
    return frame[FEATURE_NAMES].astype(float)


def fit_xgb(x, y):
    import xgboost as xgb
    model = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y == 0).sum() / max((y == 1).sum(), 1)))
    # XGBoost trata NaN de forma nativa; el peso de clase sale solo del entrenamiento.
    return model.fit(x, y)


def fit_logit(x, y):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
        LogisticRegression(class_weight='balanced', max_iter=2000)).fit(x, y)


def rule_threshold(score, y):
    """Umbral de la regla elegido con F1 en el pliegue de entrenamiento, nunca con el de prueba."""
    import numpy as np
    from sklearn.metrics import f1_score
    best = max(np.unique(score), key=lambda t: (f1_score(y, score >= t, zero_division=0), t))
    return float(best)


def metrics(y, score, flagged, probability=False):
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score, precision_score, recall_score, f1_score, brier_score_loss
    out = dict(roc_auc=float(roc_auc_score(y, score)), average_precision=float(average_precision_score(y, score)),
        precision=float(precision_score(y, flagged, zero_division=0)), sensibilidad=float(recall_score(y, flagged, zero_division=0)),
        f1=float(f1_score(y, flagged, zero_division=0)), tasa_marcados=float(np.mean(flagged)),
        verdaderos_positivos=int(((y == 1) & (flagged == 1)).sum()), falsos_positivos=int(((y == 0) & (flagged == 1)).sum()))
    if probability:
        out['brier'] = float(brier_score_loss(y, score))
    return out


def cross_validate(frame, target, repetitions=20, folds=5, seed=1607):
    """Predicciones fuera de pliegue por repetición: {modelo: [(score, marcado), ...]}."""
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    data = frame[frame[target].notna()].reset_index(drop=True)
    x, y, groups = features(data), data[target].astype(int).to_numpy(), data['codigo_anonimo'].to_numpy()
    names = ['xgboost', 'regresion_logistica', *RULES]
    runs = {n: [] for n in names}
    for rep in range(repetitions):
        score = {n: np.zeros(len(y)) for n in names}
        flag = {n: np.zeros(len(y), dtype=int) for n in names}
        for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed + rep).split(x, y, groups):
            if len(set(y[tr])) < 2:
                raise ValueError('Un pliegue de entrenamiento quedó sin positivos.')
            for name, fit in (('xgboost', fit_xgb), ('regresion_logistica', fit_logit)):
                prob = fit(x.iloc[tr], y[tr]).predict_proba(x.iloc[te])[:, 1]
                score[name][te], flag[name][te] = prob, (prob >= THRESHOLD).astype(int)
            for name, (column, sign) in RULES.items():
                s = sign * x[column].to_numpy()
                cut = rule_threshold(s[tr], y[tr])
                score[name][te], flag[name][te] = s[te], (s[te] >= cut).astype(int)
        for n in names:
            runs[n].append((score[n], flag[n]))
    return data, y, groups, runs


def summarize(y, groups, runs, boots=2000, seed=1607):
    """Media entre repeticiones e IC 95 % por bootstrap de estudiantes (combina azar de partición y muestra)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    students = np.unique(groups)
    index = {s: np.flatnonzero(groups == s) for s in students}
    samples = []
    while len(samples) < boots:
        rows = np.concatenate([index[s] for s in rng.choice(students, len(students))])
        if 0 < y[rows].sum() < len(rows):
            samples.append(rows)
    summary = {}
    for name, reps in runs.items():
        probability = name in ('xgboost', 'regresion_logistica')
        per_rep = [metrics(y, s, f, probability) for s, f in reps]
        point = {k: float(np.mean([m[k] for m in per_rep])) for k in per_rep[0]}
        draws = {k: [] for k in ('roc_auc', 'average_precision', 'precision', 'sensibilidad', 'f1')}
        for b, rows in enumerate(samples):
            s, f = reps[b % len(reps)]
            m = metrics(y[rows], s[rows], f[rows])
            for k in draws:
                draws[k].append(m[k])
        point['ic95'] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}
        summary[name] = point
    summary['siempre_continuidad'] = {'average_precision': float(y.mean()), 'roc_auc': .5, 'sensibilidad': 0.0,
        'precision': 0.0, 'f1': 0.0, 'tasa_marcados': 0.0}
    return summary


def contributions(model, x, top=3):
    """Aportes SHAP de XGBoost por fila: los factores que más suben el riesgo."""
    import xgboost as xgb
    contrib = model.get_booster().predict(xgb.DMatrix(x, feature_names=FEATURE_NAMES), pred_contribs=True)[:, :-1]
    rows = []
    for values, raw in zip(contrib, x.to_dict('records')):
        order = sorted(range(len(FEATURE_NAMES)), key=lambda i: -values[i])[:top]
        rows.append([{'variable': FEATURE_NAMES[i], 'valor': raw[FEATURE_NAMES[i]], 'aporte': round(float(values[i]), 4)}
            for i in order if values[i] > 0])
    return rows


def train(excel, output, repetitions=20):
    import numpy as np
    import pandas as pd
    import sklearn
    import xgboost as xgb
    frame = load(excel)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    evaluation = {}
    for key, target in TARGETS.items():
        data, y, groups, runs = cross_validate(frame, target, repetitions)
        evaluation[key] = dict(columna=target, filas=int(len(y)), positivos=int(y.sum()),
            estudiantes=int(len(set(groups))), estudiantes_positivos=int(len(set(groups[y == 1]))),
            gestiones=sorted(int(g) for g in data['gestion'].unique()), modelos=summarize(y, groups, runs))
        if key == 'abandono':
            oof = np.mean([s for s, _ in runs['xgboost']], axis=0)
            pd.DataFrame({'gestion': data['gestion'], 'grado': data['grado'], 'y': y, 'prob_oof_media': oof}).to_csv(
                out / 'predicciones_oof_abandono.csv', index=False)
    target = TARGETS['abandono']
    x, y = features(frame), frame[target].astype(int).to_numpy()
    model = fit_xgb(x, y)
    model_path = out / 'modelo_xgboost.json'
    model.save_model(model_path)
    loaded = xgb.XGBClassifier()
    loaded.load_model(model_path)
    if not np.allclose(loaded.predict_proba(x)[:, 1], model.predict_proba(x)[:, 1]):
        raise RuntimeError('El modelo guardado no reproduce sus resultados.')
    now = datetime.now()
    report = dict(version_modelo=f'xgb-{VERSION}-{now:%Y%m%d%H%M%S}', version_variables=VERSION, origen='REAL',
        entrenado_en=now.isoformat(timespec='seconds'), etiquetas_disponibles_hasta='2025-11-30',
        objetivo='Abandono dentro de la gestión (deja de asistir en T2/T3), predicho al cierre de T1.',
        protocolo=f'StratifiedGroupKFold 5 pliegues por estudiante x {repetitions} repeticiones; IC 95 % bootstrap por '
            'estudiante (2000). Umbral 0,5 fijo. Sin búsqueda de hiperparámetros ni calibración. Modelo final con las 790 filas.',
        filas_entrenamiento_final=int(len(y)), positivos_entrenamiento_final=int(y.sum()), parametros={**PARAMS,
            'scale_pos_weight': float((y == 0).sum() / y.sum())}, umbral_evaluacion=THRESHOLD, variables=FEATURE_NAMES,
        variables_excluidas='POST_* (T2, T3, anual), gestión, paralelo, fuente y códigos.', evaluacion=evaluation,
        importancia_ganancia={k: float(v) for k, v in model.get_booster().get_score(importance_type='gain').items()},
        modelo_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        dataset_sha256=hashlib.sha256(Path(excel).read_bytes()).hexdigest(),
        versiones={'xgboost': xgb.__version__, 'sklearn': sklearn.__version__, 'pandas': pd.__version__, 'numpy': np.__version__},
        limitaciones=['11 abandonos (9 estudiantes): los intervalos son amplios y las métricas inestables.',
            '2025 no tiene abandonos y solo 7 de 18 cursos: no es posible un holdout temporal.',
            '2021-2023 provienen de pocos cursos históricos con mayor tasa de abandono que 2024-2025; posible sesgo de selección.',
            'La etiqueta de abandono se infiere del cuaderno (asistencia en cero / notas fijas) y falta confirmar con Dirección.',
            'no_continua solo existe para 2024 y está sobrestimado por los cursos de 2025 no cargados; es exploratorio.',
            'Probabilidades sin calibrar: con scale_pos_weight el umbral 0,5 no equivale a 50 % de riesgo real.'])
    (out / 'reporte.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (out / 'diccionario.json').write_text(json.dumps(DESCRIPTIONS, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def generate(db, excel, model_id):
    """Cortes T1, predicciones y alertas para matrículas REAL. Idempotente; no hace commit."""
    from datetime import date, time
    from sqlalchemy import select
    import xgboost as xgb
    import models as m
    record = db.get(m.ModeloPredictivo, model_id)
    if record is None or record.origen_datos != 'REAL' or record.version_variables != VERSION:
        raise ValueError('El modelo no existe o no corresponde a la versión real-t1.')
    path = Path(record.artefacto_uri)
    if hashlib.sha256(path.read_bytes()).hexdigest() != record.artefacto_sha256:
        raise ValueError('El artefacto del modelo no coincide con su huella registrada.')
    medium, high = float(record.umbral_medio), float(record.umbral_alto)
    model = xgb.XGBClassifier()
    model.load_model(path)
    frame = load(excel)
    keys = db.execute(select(m.Matricula.id, m.Estudiante.codigo_anonimo, m.Gestion.anio, m.Curso.grado, m.Curso.paralelo)
        .join(m.Estudiante, m.Estudiante.id == m.Matricula.estudiante_id).join(m.Curso, m.Curso.id == m.Matricula.curso_id)
        .join(m.Gestion, m.Gestion.id == m.Curso.gestion_id).where(m.Matricula.origen == 'REAL')).all()
    index = {(c, a, g, p): i for i, c, a, g, p in keys}
    frame['matricula_id'] = [index.get((r.codigo_anonimo, r.gestion, r.grado, r.paralelo)) for r in frame.itertuples()]
    if frame['matricula_id'].isna().any() or frame['matricula_id'].duplicated().any():
        raise ValueError('Hay filas del dataset sin matrícula REAL única en la base.')
    x = features(frame)
    probabilities = model.predict_proba(x)[:, 1]
    factors = contributions(model, x)
    responsible = db.scalar(select(m.Usuario.id).where(m.Usuario.rol == 'Admin').order_by(m.Usuario.id))
    current = int(frame['gestion'].max())
    counts = {'cortes': 0, 'predicciones': 0, 'alertas': 0}
    for row, prob, top, values in zip(frame.itertuples(), probabilities, factors, x.to_dict('records')):
        cutoff = date(row.gestion, 4, 30)
        cut = db.scalar(select(m.CortePredictivo).where(m.CortePredictivo.matricula_id == row.matricula_id,
            m.CortePredictivo.fecha_corte == cutoff, m.CortePredictivo.version_variables == VERSION))
        if cut is None:
            cut = m.CortePredictivo(matricula_id=int(row.matricula_id), fecha_corte=cutoff,
                disponible_hasta=datetime.combine(cutoff, time(23, 59, 59)), version_variables=VERSION,
                variables={'indicadores': values, 'origen': 'REAL', 'gestion': row.gestion, 'horizonte': f'{row.gestion}-11-30'},
                estado='ELEGIBLE', motivo='Dataset real consolidado: totales del cuaderno pedagógico al cierre de T1.')
            db.add(cut)
            db.flush()
            counts['cortes'] += 1
        prediction = db.scalar(select(m.Prediccion).where(m.Prediccion.corte_id == cut.id, m.Prediccion.modelo_id == model_id))
        if prediction is None:
            prob = round(float(prob), 6)
            level = 'ALTO' if prob >= high else 'MEDIO' if prob >= medium else 'BAJO'
            # Las gestiones anteriores formaron parte del entrenamiento: no son una evaluación del modelo.
            use = 'COHORTE_ACTUAL' if row.gestion == current else 'RETROSPECTIVO_EN_ENTRENAMIENTO'
            prediction = m.Prediccion(corte_id=cut.id, modelo_id=model_id, probabilidad=prob, nivel=level,
                factores={'principales': top, 'uso': use})
            db.add(prediction)
            db.flush()
            counts['predicciones'] += 1
        if prediction.nivel != 'BAJO' and db.scalar(select(m.Alerta.id).where(m.Alerta.prediccion_id == prediction.id)) is None:
            db.add(m.Alerta(prediccion_id=prediction.id, responsable_id=responsible))
            counts['alertas'] += 1
    db.flush()
    return counts


def print_report(directory, excel=None, repetitions=20):
    """Imprime las métricas guardadas; con excel las recalcula y compara (evidencia reproducible)."""
    import xgboost as xgb
    directory = Path(directory)
    report = json.loads((directory / 'reporte.json').read_text(encoding='utf-8'))
    model_path = directory / 'modelo_xgboost.json'
    model_ok = hashlib.sha256(model_path.read_bytes()).hexdigest() == report['modelo_sha256']
    print(f"Modelo {report['version_modelo']} · entrenado {report['entrenado_en']} · origen {report['origen']}")
    print(f"SHA-256 modelo:  {report['modelo_sha256'][:16]}…  {'OK, coincide con el archivo' if model_ok else 'NO COINCIDE'}")
    if excel:
        data_ok = hashlib.sha256(Path(excel).read_bytes()).hexdigest() == report['dataset_sha256']
        print(f"SHA-256 dataset: {report['dataset_sha256'][:16]}…  {'OK, mismo Excel' if data_ok else 'NO COINCIDE: el Excel cambió'}")
    print(f"Protocolo: {report['protocolo']}\nVariables ({len(report['variables'])}): {', '.join(report['variables'])}")
    print(f"Excluidas: {report['variables_excluidas']}  · xgboost {xgb.__version__}")
    keys = ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'tasa_marcados')
    for target, ev in report['evaluacion'].items():
        print(f"\n== {target}: {ev['filas']} filas, {ev['positivos']} positivos ({ev['estudiantes_positivos']} estudiantes), gestiones {ev['gestiones']}")
        print(f"{'Modelo':24}{'ROC-AUC':>8} {'IC 95 %':>13}{'AP':>8} {'IC 95 %':>13}{'Sens.':>7}{'Prec.':>7}{'F1':>7}{'%marc.':>8}")
        for name, m in ev['modelos'].items():
            ic = m.get('ic95', {})
            ci = lambda k: f"[{ic[k][0]:.2f}-{ic[k][1]:.2f}]" if k in ic else ''
            print(f"{name:24}{m['roc_auc']:8.3f} {ci('roc_auc'):>13}{m['average_precision']:8.3f} {ci('average_precision'):>13}"
                f"{m['sensibilidad']:7.2f}{m['precision']:7.2f}{m['f1']:7.2f}{m['tasa_marcados'] * 100:7.1f}%")
    sens = directory / 'sensibilidad.json'
    if sens.exists():
        t = json.loads(sens.read_text(encoding='utf-8'))['temporal_2021_2023_a_2024']
        x = t['xgboost']
        print(f"\n== Temporal 2021-2023 -> 2024: {t['evaluacion']} matrículas, {t['positivos_evaluacion']} abandonos")
        print(f"XGBoost ROC-AUC {x['roc_auc']:.3f} · AP {x['average_precision']:.3f} · sensibilidad {x['sensibilidad']:.2f} · "
            f"precisión {x['precision']:.2f} · {x['verdaderos_positivos']} detectados, {x['falsos_positivos']} falsas alarmas")
    if not excel:
        return model_ok
    print(f'\nRecalculando la validación cruzada desde el Excel ({repetitions} repeticiones)…')
    frame = load(excel)
    same = True
    for target, ev in report['evaluacion'].items():
        _, y, groups, runs = cross_validate(frame, TARGETS[target], repetitions)
        fresh = summarize(y, groups, runs)
        for name, m in ev['modelos'].items():
            diff = max(abs(fresh[name][k] - m[k]) for k in keys)
            same &= diff < 1e-9
            print(f"  {target:12}{name:24}{'idéntico' if diff < 1e-9 else f'difiere ({diff:.2e})'}")
    print('RESULTADO: métricas reproducidas exactamente.' if same else 'RESULTADO: hay diferencias, revisar versiones o datos.')
    return model_ok and same
