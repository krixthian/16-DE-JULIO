"""Seguimiento continuo del riesgo de abandono: XGBoost recalculado cada mes con lo registrado hasta la fecha.

Origen: con los registros completos de la institución (2021-2025, 1889 matrículas, 11 abandonos) ningún modelo con un
único corte al 30 de abril anticipa el abandono (docs/experimento_desglosado.json, docs/experimento_trayectoria.json).
Lo que sí funciona es el seguimiento continuo (docs/experimento_seguimiento_mensual.json): un modelo por fin de mes,
con variables calculadas SOLO con lo conocido hasta esa fecha, y la alerta inmediata de 5 faltas seguidas.

Variables (16, todas calculables desde la base del sistema):
- asistencia acumulada hasta la fecha (10): proporción de faltas, retrasos y licencias; faltas en los últimos 10 y 20
  días registrados; racha actual y máxima de faltas; días de clase desde la última asistencia; tendencia semanal de
  las faltas; días registrados;
- notas del 1.er trimestre (promedio, mínima, áreas < 51) solo después de su cierre; promedio del 2.º trimestre solo
  después de su cierre;
- grado. La edad no se usa porque la base no guarda fechas de nacimiento de los registros históricos (se omitieron
  por privacidad) y el modelo debe usar lo mismo que la base; el género tampoco (no es accionable).

Para mostrar gestiones pasadas sin optimismo, además del modelo final se guarda uno por gestión entrenado SIN esa
gestión (modelo_<mes>_sin_<año>.json): las alertas de 2022 salen de un modelo que nunca vio 2022.

Entrenamiento (desde backend):
    python -m predictivo.seguimiento entrenar --excel ../data/DATASET_INSTITUCION_2021_2025.xlsx \
        --directorio artifacts/seguimiento_mensual_v1
Guarda un modelo por mes (modelo_<mes>.json) y metricas.json con la validación por estudiante 5 x 20 de CADA corte,
IC 95 % por bootstrap de estudiantes y comparación con el azar. Las probabilidades no están calibradas: ranking.
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from predictivo.experimento_seguimiento_mensual import ASIS, MESES, NOMBRE_MES, armar, variables_asistencia
from predictivo.real_t1 import PARAMS, THRESHOLD, summarize

VERSION = 'seguimiento-mensual-v1'
NOTAS = ['promedio_T1', 'nota_minima_T1', 'n_areas_bajo_51_T1']
VARIABLES = ASIS + NOTAS + ['promedio_T2', 'grado']
DIRECTORIO = Path(__file__).resolve().parent.parent / 'artifacts' / 'seguimiento_mensual_v1'
RACHA_ALERTA = 5  # validada en los registros 2021-2025: 11 de 11 abandonos, 0 falsas alarmas entre 1878 que continuaron
UMBRAL_MEDIO, UMBRAL_ALTO = .5, .8
CODIGO = {'PRESENTE': 'A', 'ATRASO': 'R', 'FALTA': 'F', 'LICENCIA': 'L'}
DESCRIPCION = {
    'prop_faltas': 'Proporción de faltas en el año', 'prop_retrasos': 'Proporción de atrasos', 'prop_licencias': 'Proporción de licencias',
    'faltas_ult10': 'Faltas en los últimos 10 días de clase', 'faltas_ult20': 'Faltas en los últimos 20 días de clase',
    'racha_actual': 'Faltas seguidas hasta hoy', 'racha_max': 'Racha más larga de faltas', 'dias_desde_asistencia': 'Días de clase desde que asistió por última vez',
    'tendencia_faltas': 'Tendencia semanal de las faltas', 'dias_registrados': 'Días de clase registrados',
    'promedio_T1': 'Promedio del 1.er trimestre', 'nota_minima_T1': 'Nota más baja del 1.er trimestre', 'n_areas_bajo_51_T1': 'Áreas con nota menor a 51 (1.er trimestre)',
    'promedio_T2': 'Promedio del 2.º trimestre', 'grado': 'Grado'}


def mes_modelo(fecha):
    """Modelo que corresponde a una fecha: el del mes en curso (febrero a octubre); noviembre usa el de octubre."""
    if fecha.month < 2:
        return None
    return min(fecha.month, 10)


# ---------------------------------------------------------------- entrenamiento

def entrenar(excel, asistencia_csv, directorio, repeticiones=20, folds=5, seed=1607):
    import sklearn
    import xgboost as xgb
    from sklearn.model_selection import StratifiedGroupKFold
    if any(v.startswith('POST_') for v in VARIABLES):
        raise ValueError('Las columnas POST_* no pueden ser predictores.')
    d = armar(excel, asistencia_csv)
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    cortes = {}
    for mes in MESES:
        dm = d[d.mes == mes].reset_index(drop=True)
        x, y, groups = dm[VARIABLES].astype(float), dm.y.to_numpy(), dm.codigo_anonimo.to_numpy()
        runs = {'xgboost': []}
        for rep in range(repeticiones):
            s = np.zeros(len(y))
            for tr, te in StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed + rep).split(x, y, groups):
                assert not set(groups[tr]) & set(groups[te])
                mod = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y[tr] == 0).sum() / max(y[tr].sum(), 1))).fit(x.iloc[tr], y[tr])
                s[te] = mod.predict_proba(x.iloc[te])[:, 1]
            runs['xgboost'].append((s, (s >= THRESHOLD).astype(int)))
        resumen = summarize(y, groups, runs)
        regla = dict(detectados=int(((dm.racha_actual >= RACHA_ALERTA) & (dm.y == 1)).sum()),
            falsas_alarmas=int(((dm.racha_actual >= RACHA_ALERTA) & (dm.y == 0)).sum()))
        final = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y == 0).sum() / max(y.sum(), 1))).fit(x, y)
        final.get_booster().save_model(str(directorio / f'modelo_{NOMBRE_MES[mes]}.json'))
        for anio in sorted(dm.gestion.unique()):
            fuera = (dm.gestion != anio).to_numpy()
            if y[fuera].sum() == 0:
                continue
            m_sin = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y[fuera] == 0).sum() / max(y[fuera].sum(), 1))).fit(x[fuera], y[fuera])
            m_sin.get_booster().save_model(str(directorio / f'modelo_{NOMBRE_MES[mes]}_sin_{anio}.json'))
        cortes[NOMBRE_MES[mes]] = dict(matriculas=int(len(y)), abandonos=int(y.sum()), xgboost=resumen['xgboost'],
            azar=resumen['siempre_continuidad']['average_precision'], regla_5_faltas=regla)
        print(f"{NOMBRE_MES[mes]}: AP {resumen['xgboost']['average_precision']:.3f} {resumen['xgboost']['ic95']['average_precision']}"
            f"  AUC {resumen['xgboost']['roc_auc']:.3f}  VP {resumen['xgboost']['verdaderos_positivos']:.1f}"
            f"  FP {resumen['xgboost']['falsos_positivos']:.1f}  | regla 5: {regla}")
    reporte = dict(version=VERSION, dataset=Path(excel).name, variables=VARIABLES, parametros=PARAMS, umbral=THRESHOLD,
        protocolo=f'Un modelo por fin de mes; StratifiedGroupKFold {folds} x {repeticiones} por estudiante; IC 95 % bootstrap por estudiante; '
            'parámetros del modelo en uso, sin ajuste; variables solo con datos hasta el corte.',
        nota='Probabilidades no calibradas: se usan como ranking de prioridad. Umbrales MEDIO 0,5 y ALTO 0,8: propuesta pendiente de validar con Dirección.',
        cortes=cortes, versiones=dict(sklearn=sklearn.__version__, xgboost=xgb.__version__))
    (directorio / 'metricas.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
    return reporte


# ---------------------------------------------------------------- uso en el sistema

def metricas(directorio=DIRECTORIO):
    ruta = Path(directorio) / 'metricas.json'
    return json.loads(ruta.read_text(encoding='utf-8')) if ruta.exists() else None


def cargar_modelo(mes, directorio=DIRECTORIO, sin_anio=None):
    """Modelo del mes; con `sin_anio`, el entrenado sin esa gestión (si esa gestión estuvo en el entrenamiento)."""
    import xgboost as xgb
    ruta = Path(directorio) / f'modelo_{NOMBRE_MES[mes]}.json'
    if sin_anio is not None and (Path(directorio) / f'modelo_{NOMBRE_MES[mes]}_sin_{sin_anio}.json').exists():
        ruta = Path(directorio) / f'modelo_{NOMBRE_MES[mes]}_sin_{sin_anio}.json'
    if not ruta.exists():
        return None
    booster = xgb.Booster()
    booster.load_model(str(ruta))
    return booster


def codigo_dia(diario, horas):
    """Estado del día en códigos del registro pedagógico (A, R, F, L). La asistencia diaria manda; si no existe, se
    deduce de las horas (asistencia por materia): asistió a alguna hora -> A (o R si solo llegó tarde), faltó a todas -> F."""
    if diario is not None:
        return CODIGO[diario]
    if not horas:
        return None
    if 'PRESENTE' in horas:
        return 'A'
    if 'ATRASO' in horas:
        return 'R'
    return 'F' if all(e == 'FALTA' for e in horas) else 'L'


def notas_trimestre(registros):
    """registros: [(materia_id, puntaje_sobre_100)] -> promedio, nota mínima y áreas < 51 (promedio por área)."""
    por_area = defaultdict(list)
    for materia, nota in registros:
        por_area[materia].append(nota)
    if not por_area:
        return None, None, None
    areas = [float(np.mean(v)) for v in por_area.values()]
    return float(np.mean(areas)), float(min(areas)), int(sum(a < 51 for a in areas))


def puntuar(filas, mes, directorio=DIRECTORIO, top=3, sin_anio=None):
    """filas: [dict con VARIABLES]. Devuelve [(probabilidad, factores)] con los aportes SHAP que más suben el riesgo."""
    import xgboost as xgb
    booster = cargar_modelo(mes, directorio, sin_anio)
    if booster is None or not filas:
        return None
    x = np.array([[np.nan if f.get(v) is None else float(f[v]) for v in VARIABLES] for f in filas], dtype=float)
    dm = xgb.DMatrix(x, feature_names=VARIABLES, missing=np.nan)
    prob = booster.predict(dm)
    contrib = booster.predict(dm, pred_contribs=True)[:, :-1]
    out = []
    for p, aportes, fila in zip(prob, contrib, filas):
        orden = sorted(range(len(VARIABLES)), key=lambda i: -aportes[i])[:top]
        factores = [dict(variable=VARIABLES[i], descripcion=DESCRIPCION[VARIABLES[i]], valor=fila.get(VARIABLES[i]),
            aporte=round(float(aportes[i]), 4)) for i in orden if aportes[i] > 0]
        out.append((float(p), factores))
    return out


def nivel(probabilidad):
    return 'ALTO' if probabilidad >= UMBRAL_ALTO else 'MEDIO' if probabilidad >= UMBRAL_MEDIO else 'BAJO'


def cierre_periodo(periodos, numero, anio, por_defecto):
    p = periodos.get(numero)
    return p.fecha_fin if p is not None and p.fecha_fin is not None else date(anio, *por_defecto)


def calcular(db, anio, fecha=None, directorio=DIRECTORIO):
    """Riesgo a la fecha de todas las matrículas vigentes de la gestión `anio`, solo con lo registrado hasta `fecha`.
    Solo lectura: no escribe en la base."""
    from sqlalchemy import select
    import models as m
    gestion = db.scalar(select(m.Gestion).where(m.Gestion.anio == anio))
    if gestion is None:
        raise LookupError(f'No existe la gestión {anio}.')
    cursos = {c.id: c for c in db.scalars(select(m.Curso).where(m.Curso.gestion_id == gestion.id))}
    jornadas = {j.id: j for j in db.scalars(select(m.JornadaClase).where(m.JornadaClase.curso_id.in_(cursos), m.JornadaClase.es_lectiva == True))} if cursos else {}
    if fecha is None:
        fechas = [j.fecha for j in jornadas.values() if j.fecha <= date.today()]
        fecha = max(fechas) if fechas else min(date.today(), gestion.fecha_fin or date.today())
    mes = mes_modelo(fecha)
    base = dict(gestion=anio, fecha=fecha.isoformat(), mes=None if mes is None else NOMBRE_MES[mes], version=VERSION, racha_alerta=RACHA_ALERTA)
    if mes is None:
        return {**base, 'total': 0, 'alertas': [], 'motivo': 'El seguimiento empieza en febrero, con el inicio de clases.'}
    jornadas = {k: j for k, j in jornadas.items() if j.fecha <= fecha}
    periodos = {p.numero: p for p in db.scalars(select(m.Periodo).where(m.Periodo.gestion_id == gestion.id))}
    t1_cerrado = fecha >= cierre_periodo(periodos, 1, anio, (4, 30))
    t2_cerrado = fecha >= cierre_periodo(periodos, 2, anio, (8, 31))
    matriculas = [x for x in db.scalars(select(m.Matricula).where(m.Matricula.curso_id.in_(cursos)))
        if x.fecha_ingreso <= fecha and (x.fecha_fin is None or x.fecha_fin >= fecha)] if cursos else []
    ids = [x.id for x in matriculas]
    diario = {(a.matricula_id, a.jornada_id): a.estado for a in db.scalars(select(m.Asistencia).where(m.Asistencia.matricula_id.in_(ids)))
        if a.jornada_id in jornadas} if ids else {}
    sesiones = {s.id: s.jornada_id for s in db.scalars(select(m.SesionClase).where(m.SesionClase.curso_id.in_(cursos), m.SesionClase.dictada == True))
        if s.jornada_id in jornadas} if cursos else {}
    horas = defaultdict(list)
    if sesiones:
        for r in db.scalars(select(m.AsistenciaMateria).where(m.AsistenciaMateria.sesion_id.in_(sesiones))):
            horas[(r.matricula_id, sesiones[r.sesion_id])].append(r.estado)
    notas = defaultdict(list)
    if ids:
        evaluaciones = {e.id: e for e in db.scalars(select(m.Evaluacion).where(m.Evaluacion.gestion_id == gestion.id, m.Evaluacion.fecha_aplicacion <= fecha))}
        asignaciones = {a.id: a.materia_id for a in db.scalars(select(m.AsignacionDocente).where(m.AsignacionDocente.curso_id.in_(cursos)))}
        numero_periodo = {p.id: p.numero for p in periodos.values()}
        for c in db.scalars(select(m.Calificacion).where(m.Calificacion.matricula_id.in_(ids), m.Calificacion.estado == 'CALIFICADA')):
            e = evaluaciones.get(c.evaluacion_id)
            if e is None:
                continue
            notas[(c.matricula_id, numero_periodo.get(e.periodo_id))].append(
                (asignaciones.get(e.asignacion_id), float(c.puntaje) / float(e.puntaje_maximo) * 100))
    estudiantes = {e.id: e for e in db.scalars(select(m.Estudiante).where(m.Estudiante.id.in_([x.estudiante_id for x in matriculas])))} if matriculas else {}
    filas, info = [], []
    for mat in matriculas:
        curso = cursos[mat.curso_id]
        dias = sorted((j.fecha, codigo_dia(diario.get((mat.id, j.id)), horas.get((mat.id, j.id), []))) for j in jornadas.values()
            if j.curso_id == curso.id and j.fecha >= mat.fecha_ingreso)
        regs = [(f, c) for f, c in dias if c is not None]
        if not regs:
            continue  # sin asistencia registrada no hay seguimiento posible
        v = variables_asistencia(regs)
        p1 = notas_trimestre(notas.get((mat.id, 1), [])) if t1_cerrado else (None, None, None)
        p2 = notas_trimestre(notas.get((mat.id, 2), [])) if t2_cerrado else (None, None, None)
        est = estudiantes[mat.estudiante_id]
        v.update(promedio_T1=p1[0], nota_minima_T1=p1[1], n_areas_bajo_51_T1=p1[2], promedio_T2=p2[0], grado=curso.grado)
        filas.append(v)
        ultima = max((f for f, c in regs if c in ('A', 'R')), default=None)
        info.append(dict(matricula_id=mat.id, estudiante=est.codigo_anonimo, origen=mat.origen, curso_id=curso.id, curso=f'{curso.grado}° {curso.paralelo}',
            ultima_asistencia=None if ultima is None else ultima.isoformat(), racha_actual=int(v['racha_actual'])))
    puntajes = puntuar(filas, mes, directorio, sin_anio=anio)
    fuera_de_muestra = (Path(directorio) / f'modelo_{NOMBRE_MES[mes]}_sin_{anio}.json').exists()
    if puntajes is None:
        return {**base, 'total': 0, 'alertas': [], 'motivo': 'No hay asistencia registrada en la gestión hasta esta fecha.'
            if not filas else 'No se encontró el modelo de seguimiento; ejecute el entrenamiento.'}
    alertas = []
    for (prob, factores), extra, fila in zip(puntajes, info, filas):
        alertas.append(dict(**extra, probabilidad=round(prob, 4), nivel=nivel(prob), factores=factores,
            alerta_inmediata=extra['racha_actual'] >= RACHA_ALERTA,
            notas_t1_disponibles=fila['promedio_T1'] is not None))
    orden = sorted(alertas, key=lambda a: (-a['alerta_inmediata'], -a['probabilidad']))
    for i, a in enumerate(orden, 1):
        a['puesto'] = i
    met = metricas(directorio)
    return {**base, 'total': len(orden), 'alertas': orden, 'notas_t1_incluidas': t1_cerrado, 'promedio_t2_incluido': t2_cerrado,
        'validacion_del_corte': met and met['cortes'].get(NOMBRE_MES[mes]),
        'modelo_usado': f'entrenado sin la gestión {anio} (la gestión no se usó para aprender)' if fuera_de_muestra else 'modelo final (todas las gestiones 2021-2025)'}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='accion', required=True)
    e = sub.add_parser('entrenar')
    e.add_argument('--excel', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    e.add_argument('--asistencia', default='../data/DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv')
    e.add_argument('--directorio', default=str(DIRECTORIO))
    e.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    entrenar(a.excel, a.asistencia, a.directorio, a.repeticiones)


if __name__ == '__main__':
    main()
