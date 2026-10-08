"""Entrenamiento base sin búsqueda de hiperparámetros ni activación en producción."""
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from predictivo.features import VERSION, FEATURE_NAMES, day
from predictivo.source import digest


def split_rows(rows, holdout_year):
    usable = [r for r in rows if r['estado'] == 'ELEGIBLE' and r.get('objetivo') in (0, 1)]
    test = [r for r in usable if r['gestion'] == holdout_year]
    if not test:
        raise ValueError('La gestión de evaluación no tiene casos elegibles etiquetados.')
    test_students = {r['estudiante_id'] for r in test}
    first_test_cut = min(day(r['fecha_corte']) for r in test)
    candidates = [r for r in usable if r['gestion'] < holdout_year]
    train = [r for r in candidates if r['estudiante_id'] not in test_students
        and day(r['horizonte']) < first_test_cut and day(r['etiqueta_disponible_en']) < first_test_cut]
    for name, group in [('entrenamiento', train), ('evaluación', test)]:
        if len(group) < 20 or set(r['objetivo'] for r in group) != {0, 1}:
            raise ValueError(f'Se requieren al menos 20 casos y ambas clases en {name}; no es un mínimo de validación científica.')
    return train, test, len(candidates) - len(train)


def train_baseline(dataset, output, holdout_year):
    import numpy as np
    import pandas as pd
    import sklearn
    import xgboost as xgb
    from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, average_precision_score, roc_auc_score

    rows = dataset['registros']
    if dataset.get('version_variables') != VERSION or not rows:
        raise ValueError('Conjunto vacío o versión de variables incompatible.')
    keys = [(r['matricula_id'], r['fecha_corte']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('Cortes duplicados en el conjunto de entrenamiento.')
    if {r['origen'] for r in rows} != {dataset['origen']} or dataset['origen'] not in ('REAL', 'SIMULADO'):
        raise ValueError('No se permite mezclar datos reales y simulados.')
    for row in rows:
        if row['version_variables'] != VERSION or set(row['variables']) != set(FEATURE_NAMES):
            raise ValueError('Contrato de variables incompatible.')
    train, test, purged = split_rows(rows, holdout_year)
    def matrix(group):
        frame = pd.DataFrame([r['variables'] for r in group], columns=FEATURE_NAMES, dtype=float)
        if np.isinf(frame.to_numpy()).any():
            raise ValueError('Los indicadores contienen valores infinitos.')
        return frame
    xtrain, xtest = matrix(train), matrix(test)
    ytrain = np.array([r['objetivo'] for r in train])
    ytest = np.array([r['objetivo'] for r in test])
    params = dict(n_estimators=80, max_depth=3, learning_rate=.05, subsample=.8, colsample_bytree=.8,
        objective='binary:logistic', eval_metric='logloss', tree_method='hist', random_state=1607, n_jobs=2,
        scale_pos_weight=float((ytrain == 0).sum() / (ytrain == 1).sum()))
    model = xgb.XGBClassifier(**params)
    # XGBoost trata NaN de forma nativa; no imputar con estadísticas del holdout.
    model.fit(xtrain, ytrain)
    probabilities = model.predict_proba(xtest)[:, 1]
    predicted = (probabilities >= .5).astype(int)
    def metrics(yhat, prob):
        return dict(precision=float(precision_score(ytest, yhat, zero_division=0)),
            sensibilidad=float(recall_score(ytest, yhat, zero_division=0)), f1=float(f1_score(ytest, yhat, zero_division=0)),
            matriz_confusion=confusion_matrix(ytest, yhat, labels=[0, 1]).tolist(),
            average_precision=float(average_precision_score(ytest, prob)), roc_auc=float(roc_auc_score(ytest, prob)))
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    model_path = out / 'modelo_xgboost.json'
    model.save_model(model_path)
    loaded = xgb.XGBClassifier()
    loaded.load_model(model_path)
    if not np.allclose(loaded.predict_proba(xtest)[:, 1], probabilities):
        raise RuntimeError('El modelo guardado no reproduce sus resultados.')
    now = datetime.now().isoformat(timespec='seconds')
    report = dict(version_modelo=f"base-{dataset['origen'].lower()}-{datetime.now():%Y%m%d%H%M%S%f}",
        version_variables=VERSION, origen=dataset['origen'], entrenado_en=now,
        objetivo='Abandono confirmado después del corte y hasta fin de gestión; traslados y seguimiento desconocido excluidos.',
        protocolo='Holdout temporal por gestión; estudiantes de evaluación excluidos del entrenamiento. No se ajustan parámetros con el holdout.',
        gestion_evaluacion=holdout_year, entrenamiento=len(train), evaluacion=len(test), registros_purgados=purged,
        estudiantes_compartidos=0, clases_entrenamiento=dict(Counter(map(int, ytrain))), clases_evaluacion=dict(Counter(map(int, ytest))),
        etiquetas_disponibles_hasta=max(r['etiqueta_disponible_en'] for r in train + test),
        parametros=params, umbral_evaluacion=.5, metricas=metrics(predicted, probabilities),
        referencia_siempre_continuidad=metrics(np.zeros_like(ytest), np.zeros_like(probabilities)),
        variables=FEATURE_NAMES, variables_sin_datos_entrenamiento=xtrain.columns[xtrain.isna().all()].tolist(),
        importancia_ganancia={k: float(v) for k, v in model.get_booster().get_score(importance_type='gain').items()},
        modelo_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(), dataset_sha256=digest(dataset),
        versiones={'xgboost': xgb.__version__, 'sklearn': sklearn.__version__, 'pandas': pd.__version__, 'numpy': np.__version__},
        limitaciones=['Modelo base experimental, sin activación de alertas ni calibración de probabilidades.',
            'El criterio de suficiencia y los umbrales requieren revisión institucional.',
            'Purga de estudiantes reduce la muestra y puede cambiar la distribución de casos.',
            'Calendario incompleto puede sobreestimar cobertura; revisar jornadas configuradas.',
            'Las correcciones sin auditoría no permiten reconstruir con certeza el pasado.'] +
            (['Datos SIMULADOS: las métricas no demuestran desempeño en estudiantes reales.'] if dataset['origen'] == 'SIMULADO' else []))
    (out / 'reporte.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    manifest = {'entrenamiento': [{'matricula_id': r['matricula_id'], 'gestion': r['gestion']} for r in train],
        'evaluacion': [{'matricula_id': r['matricula_id'], 'gestion': r['gestion']} for r in test]}
    (out / 'particiones.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return report
