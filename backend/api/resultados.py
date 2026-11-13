"""Resultados del modelo: métricas validadas, comparación con baselines, importancia de variables, ajuste,
umbrales, calibración, validación temporal y experimento de balanceo (SMOTE).

Fuentes, sin cifras escritas a mano: el registro del modelo en la base (modelos_predictivos.metricas), los cortes
y predicciones de la base, y los reportes reproducibles del pipeline (artifacts/ y docs/). Si falta un reporte,
su sección se devuelve como no disponible.
"""
import csv
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.alertas import seguimiento
from database import get_db
from predictivo import explicacion as ex
from predictivo.real_t1 import FEATURE_NAMES
import models as m

router = APIRouter(prefix='/modelo', tags=['Resultados del modelo'], dependencies=[Depends(seguimiento)])
BACKEND = Path(__file__).resolve().parents[1]
AJUSTE = BACKEND / 'artifacts' / 'real_t1_ajuste_v1' / 'reporte_ajuste.json'
SENSIBILIDAD = BACKEND / 'artifacts' / 'real_t1_v1' / 'sensibilidad.json'
SMOTE = BACKEND.parent / 'docs' / 'experimento_smote_resumen_tabla.csv'
NOMBRES = {'xgboost': 'XGBoost (modelo en uso)', 'regresion_logistica': 'Regresión logística', 'regla_promedio_T1': 'Regla: promedio T1',
    'regla_n_areas_bajo_51': 'Regla: áreas bajo 51', 'regla_faltas_T1': 'Regla: faltas T1', 'siempre_continuidad': 'Siempre "continúa" (azar)'}
VARIANTES = {'a_sin_balanceo': 'Sin balanceo', 'b_scale_pos_weight': 'scale_pos_weight (en uso)', 'c_smote': 'SMOTE',
    'd_borderline_smote': 'BorderlineSMOTE', 'e_adasyn': 'ADASYN', 'f_smote_parcial_mas_pesos': 'SMOTE parcial + pesos'}


def leer_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def metrica(d):
    keys = ('roc_auc', 'average_precision', 'sensibilidad', 'precision', 'f1', 'verdaderos_positivos', 'falsos_positivos', 'tasa_marcados', 'brier')
    return {**{k: d.get(k) for k in keys}, 'ic95': d.get('ic95', {})}


def importancia(db, modelo):
    """|SHAP| medio por variable sobre todas las predicciones del modelo, y su dirección media."""
    try:
        model = ex.cargar_modelo(modelo.artefacto_uri, modelo.artefacto_sha256)
    except (OSError, ValueError):
        return None
    filas = db.scalars(select(m.CortePredictivo.variables).join(m.Prediccion, m.Prediccion.corte_id == m.CortePredictivo.id)
        .where(m.Prediccion.modelo_id == modelo.id)).all()
    import numpy as np
    import xgboost as xgb
    x = np.array([[np.nan if (v or {}).get('indicadores', {}).get(n) is None else float(v['indicadores'][n]) for n in FEATURE_NAMES] for v in filas])
    if not len(x):
        return None
    contrib = model.get_booster().predict(xgb.DMatrix(x, feature_names=FEATURE_NAMES), pred_contribs=True)[:, :-1]
    media = np.abs(contrib).mean(axis=0)
    total = media.sum() or 1
    out = [dict(variable=n, etiqueta=ex.ETIQUETAS[n], grupo=ex.GRUPOS[n], shap_medio=round(float(v), 4), porcentaje=round(float(100 * v / total), 1))
        for n, v in zip(FEATURE_NAMES, media)]
    return dict(filas=len(x), variables=sorted(out, key=lambda r: -r['shap_medio']))


def smote():
    try:
        with SMOTE.open(encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None
    pick = ('roc_auc_media', 'average_precision_media', 'average_precision_de', 'sensibilidad_media', 'precision_media', 'f1_media',
        'verdaderos_positivos_media', 'falsos_positivos_media', 'delta_ap_vs_base_media', 'repeticiones_ap_mayor_que_base', 'repeticiones')
    out = {}
    for r in rows:
        out.setdefault(r['esquema'], []).append({'variante': r['variante'], 'nombre': VARIANTES.get(r['variante'], r['variante']),
            **{k: float(r[k]) for k in pick}})
    return out


@router.get('/resultados')
def resultados(db: Session = Depends(get_db)):
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    if modelo is None:
        raise HTTPException(404, 'No hay un modelo registrado.')
    met = modelo.metricas or {}
    ev = (met.get('evaluacion') or {}).get('abandono') or {}
    modelos = ev.get('modelos') or {}
    xgb_m = modelos.get('xgboost') or {}
    filas, positivos = ev.get('filas'), ev.get('positivos')
    tp, fp = xgb_m.get('verdaderos_positivos'), xgb_m.get('falsos_positivos')
    matriz = None
    if None not in (filas, positivos, tp, fp):
        matriz = dict(verdaderos_positivos=tp, falsos_negativos=round(positivos - tp, 2), falsos_positivos=fp,
            verdaderos_negativos=round(filas - positivos - fp, 2), positivos=positivos, negativos=filas - positivos)
    ajuste = leer_json(AJUSTE)
    sens = leer_json(SENSIBILIDAD)
    predicciones = db.scalar(select(func.count()).select_from(m.Prediccion).where(m.Prediccion.modelo_id == modelo.id))
    return {
        'modelo': dict(version=modelo.version, algoritmo=modelo.algoritmo, entrenado_en=modelo.entrenado_en, protocolo=modelo.protocolo_validacion,
            parametros=met.get('parametros'), variables=len(met.get('variables') or []), excluidas=met.get('variables_excluidas'),
            umbral_medio=float(modelo.umbral_medio), umbral_alto=float(modelo.umbral_alto), predicciones=predicciones,
            filas=filas, positivos=positivos, estudiantes=ev.get('estudiantes'), estudiantes_positivos=ev.get('estudiantes_positivos'),
            gestiones=ev.get('gestiones')),
        'comparacion': [{'modelo': k, 'nombre': NOMBRES.get(k, k), **metrica(v)} for k, v in modelos.items()],
        'matriz_confusion': matriz,
        'importancia': importancia(db, modelo),
        'ajuste': ajuste and dict(protocolo=ajuste.get('protocolo'), configuraciones=(ajuste.get('espacio') or {}).get('configuraciones'),
            decision=ajuste.get('decision'), diferencia=(ajuste.get('diferencias_pareadas') or {}).get('xgboost_ajustado - xgboost_base'),
            ajustado=metrica((ajuste.get('modelos') or {}).get('xgboost_ajustado') or {}),
            estabilidad={k: (ajuste.get('estabilidad') or {}).get(k) for k in ('pliegues_externos', 'configuraciones_distintas', 'mas_frecuentes')},
            umbrales=(ajuste.get('umbrales') or {}).get('xgboost_base'),
            calibracion={k: ((ajuste.get('modelos') or {}).get(k) or {}).get('brier') for k in ('xgboost_base', 'xgboost_base_sigmoide', 'xgboost_ajustado_isotonica')},
            diferencia_calibracion=(ajuste.get('diferencias_pareadas') or {}).get('xgboost_base_sigmoide - xgboost_base')),
        'temporal': sens and sens.get('temporal_2021_2023_a_2024'),
        'separacion_promedio_le_66': sens and sens.get('separacion_promedio_le_66'),
        'balanceo': smote(),
        'limitaciones': met.get('limitaciones') or [],
        'fuentes': {'registro_del_modelo': 'Base de datos (modelos_predictivos.metricas)', 'importancia': 'Base de datos (790 cortes) + modelo registrado',
            'ajuste_umbrales_calibracion': 'backend/artifacts/real_t1_ajuste_v1/reporte_ajuste.json' if ajuste else None,
            'temporal': 'backend/artifacts/real_t1_v1/sensibilidad.json' if sens else None,
            'balanceo': 'docs/experimento_smote_resumen_tabla.csv' if SMOTE.exists() else None},
    }
