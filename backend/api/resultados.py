"""Resultados del modelo: métricas validadas, comparación con baselines, importancia de variables, ajuste,
umbrales, calibración, validación temporal, experimento de balanceo (SMOTE) y experimento de etiqueta ampliada
(curva de aprendizaje y reglas frente a modelos).

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
from predictivo import dimensiones as dim
import models as m

router = APIRouter(prefix='/modelo', tags=['Resultados del modelo'], dependencies=[Depends(seguimiento)])
BACKEND = Path(__file__).resolve().parents[1]
AJUSTE = BACKEND / 'artifacts' / 'real_t1_ajuste_v1' / 'reporte_ajuste.json'
SENSIBILIDAD = BACKEND / 'artifacts' / 'real_t1_v1' / 'sensibilidad.json'
SMOTE = BACKEND.parent / 'docs' / 'experimento_smote_resumen_tabla.csv'
AMPLIADA = BACKEND.parent / 'docs' / 'experimento_etiqueta_ampliada.json'
REGISTROS = BACKEND.parent / 'docs' / 'analisis_registros_detallados.json'
ALGORITMOS = BACKEND.parent / 'docs' / 'experimento_algoritmos.json'
MENSUAL = BACKEND.parent / 'docs' / 'experimento_seguimiento_mensual.json'
TRAYECTORIA = BACKEND.parent / 'docs' / 'experimento_trayectoria.json'
DESGLOSADO = BACKEND.parent / 'docs' / 'experimento_desglosado.json'
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


def etiqueta_ampliada():
    """Resumen del experimento de etiqueta ampliada (abandono o reprobación): curvas de aprendizaje y AP por método."""
    r = leer_json(AMPLIADA)
    if not r:
        return None
    metodos = ('xgboost', 'regresion_logistica', 'regla_promedio_T1', 'regla_n_areas_bajo_51', 'siempre_continuidad')
    ap = lambda cv: {k: (cv.get(k) or {}).get('average_precision') for k in metodos}
    curva = lambda filas: [{k: f.get(k) for k in ('fraccion', 'positivos_entrenamiento', 'average_precision', 'average_precision_std',
        'sensibilidad', 'f1')} for f in filas or []]
    temporal = r.get('temporal_2025_realista') or {}
    return dict(
        etiqueta={k: (r.get('etiqueta') or {}).get(k) for k in ('descripcion', 'positivos', 'estudiantes_positivos', 'abandonos_incluidos')},
        metodos=[{'modelo': k, 'nombre': NOMBRES.get(k, k)} for k in metodos],
        ap_abandono=ap(r.get('cv_abandono') or {}), ap_ampliada=ap(r.get('cv_ampliada') or {}),
        curva_abandono=curva(r.get('curva_aprendizaje_abandono')), curva_ampliada=curva(r.get('curva_aprendizaje_ampliada')),
        sobre_los_11_abandonos=r.get('sobre_los_11_abandonos'),
        temporal_2025={'positivos': temporal.get('positivos_evaluacion'), 'evaluacion': temporal.get('evaluacion'),
            **{k: {c: ((temporal.get('modelos') or {}).get(k) or {}).get(c) for c in ('verdaderos_positivos', 'falsos_positivos', 'f1')}
               for k in ('xgboost', 'regla_promedio_T1')}})


def seguimiento_continuo():
    """Seguimiento continuo con los archivos recibidos (origen no verificado): validación de cada corte mensual del modelo en
    uso por el sistema (artifacts/seguimiento_mensual_v2/metricas.json), la regla de faltas seguidas revisada a diario y
    los cortes únicos que no anticipan (30 de abril y trayectoria previa)."""
    from predictivo import seguimiento as sg
    met, mensual, tray, desg = sg.metricas(), leer_json(MENSUAL) or {}, leer_json(TRAYECTORIA) or {}, leer_json(DESGLOSADO) or {}
    if met is None:
        return None
    cortes = [dict(mes=mes, matriculas=c['matriculas'], abandonos=c['abandonos'], azar=c['azar'],
        **{k: c['xgboost'].get(k) for k in ('average_precision', 'roc_auc', 'f1', 'sensibilidad', 'precision', 'verdaderos_positivos', 'falsos_positivos', 'ic95')},
        ic95_ap=c['xgboost'].get('ic95', {}).get('average_precision'), regla_5=c['regla_5_faltas']) for mes, c in met['cortes'].items()]
    t = (tray.get('modelos') or {}).get('trayectoria|xgboost') or {}
    g = (desg.get('modelos') or {}).get('global|xgboost') or {}
    return dict(version=met['version'], dataset=met['dataset'], protocolo=met['protocolo'], nota=met['nota'], variables=len(met['variables']),
        cortes=cortes, diario=mensual.get('monitoreo_diario'), matriculas=mensual.get('matriculas'), abandonos=mensual.get('abandonos'),
        corte_unico=dict(abril=g and dict(average_precision=g.get('average_precision'), roc_auc=g.get('roc_auc'), azar=((desg.get('modelos') or {}).get('siempre_continuidad') or {}).get('average_precision')),
            trayectoria=t and dict(average_precision=t.get('average_precision'), roc_auc=t.get('roc_auc'), azar=tray.get('prevalencia_azar'))))


def por_dimension(imp):
    """Peso del modelo actual por dimensión (suma de |SHAP| medio) y catálogo de variables: modelo actual frente a sistema."""
    from predictivo.features import DESCRIPTIONS, VERSION
    pesos = {k: 0.0 for k in dim.DIMENSIONES}
    modelo_vars = {k: [] for k in dim.DIMENSIONES}
    for v in (imp or {}).get('variables', []):
        d = dim.dimension_modelo(v['variable'])
        pesos[d] += v['porcentaje']
        modelo_vars[d].append(v['etiqueta'])
    if not imp:
        for n in FEATURE_NAMES:
            modelo_vars[dim.dimension_modelo(n)].append(ex.ETIQUETAS[n])
    sistema = {k: [] for k in dim.DIMENSIONES}
    for n, desc in DESCRIPTIONS.items():
        sistema[dim.dimension_sistema(n)].append({'variable': n, 'descripcion': desc})
    return dict(version_sistema=VERSION, variables_modelo=len(FEATURE_NAMES), variables_sistema=len(DESCRIPTIONS),
        dimensiones=[dict(clave=k, nombre=n, descripcion=d, porcentaje=round(pesos[k], 1) if imp else None,
            modelo=modelo_vars[k], sistema=sistema[k]) for k, (n, d) in dim.DIMENSIONES.items()])


@router.get('/resultados')
def resultados(db: Session = Depends(get_db)):
    # Las métricas de esta página son las del modelo de corte único (el de seguimiento tiene su propia sección).
    modelo = db.scalar(select(m.ModeloPredictivo).where(m.ModeloPredictivo.version.not_like('seguimiento%')).order_by(m.ModeloPredictivo.id.desc()))
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
        'importancia': (imp := importancia(db, modelo)),
        'dimensiones': por_dimension(imp),
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
        'etiqueta_ampliada': etiqueta_ampliada(),
        'registros': leer_json(REGISTROS),
        'algoritmos': leer_json(ALGORITMOS),
        'seguimiento': seguimiento_continuo(),
        'limitaciones': met.get('limitaciones') or [],
        'fuentes': {'registro_del_modelo': 'Base de datos (modelos_predictivos.metricas)', 'importancia': 'Base de datos (790 cortes) + modelo registrado',
            'ajuste_umbrales_calibracion': 'backend/artifacts/real_t1_ajuste_v1/reporte_ajuste.json' if ajuste else None,
            'temporal': 'backend/artifacts/real_t1_v1/sensibilidad.json' if sens else None,
            'balanceo': 'docs/experimento_smote_resumen_tabla.csv' if SMOTE.exists() else None,
            'etiqueta_ampliada': 'docs/experimento_etiqueta_ampliada.json' if AMPLIADA.exists() else None,
            'registros': 'docs/analisis_registros_detallados.json' if REGISTROS.exists() else None,
            'algoritmos': 'docs/experimento_algoritmos.json' if ALGORITMOS.exists() else None,
            'seguimiento': 'backend/artifacts/seguimiento_mensual_v2/metricas.json, docs/experimento_seguimiento_mensual.json, docs/experimento_trayectoria.json'},
    }
