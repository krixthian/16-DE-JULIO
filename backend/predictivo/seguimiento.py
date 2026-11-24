"""Seguimiento continuo del riesgo de abandono: XGBoost recalculado cada mes con lo registrado hasta la fecha.

Origen: con los archivos recibidos, de origen no verificado (2021-2025, 1889 matrículas, 11 abandonos) ningún modelo con un
único corte al 30 de abril anticipa el abandono (docs/experimento_desglosado.json, docs/experimento_trayectoria.json).
Lo que sí funciona es el seguimiento continuo (docs/experimento_seguimiento_mensual.json): un modelo por fin de mes,
con variables calculadas SOLO con lo conocido hasta esa fecha, y la alerta inmediata de 5 faltas seguidas.

Variables (23, todas calculables desde la base del sistema):
- asistencia acumulada hasta la fecha (10): proporción de faltas, retrasos y licencias; faltas en los últimos 10 y 20
  días registrados; racha actual y máxima de faltas; días de clase desde la última asistencia; tendencia semanal de
  las faltas; días registrados;
- notas del 1.er trimestre (promedio, mínima, áreas < 51) solo después de su cierre; promedio del 2.º trimestre solo
  después de su cierre;
- notas por dimensión (8, predictivo/desglose.py), al cierre de cada trimestre;
- grado. La edad no se usa porque la base no guarda fechas de nacimiento de los registros históricos (se omitieron
  por privacidad) y el modelo debe usar lo mismo que la base; el género tampoco (no es accionable).

Para mostrar gestiones pasadas sin optimismo, además del modelo final se guarda uno por gestión entrenado SIN esa
gestión (modelo_<mes>_sin_<año>.json): las alertas de 2022 salen de un modelo que nunca vio 2022.

Entrenamiento (desde backend):
    python -m predictivo.seguimiento entrenar --excel ../data/DATASET_INSTITUCION_2021_2025.xlsx \
        --directorio artifacts/seguimiento_mensual_v2
Guarda un modelo por mes (modelo_<mes>.json) y metricas.json con la validación por estudiante 5 x 20 de CADA corte,
IC 95 % por bootstrap de estudiantes y comparación con el azar. Las probabilidades no están calibradas: ranking.
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from predictivo import desglose as dg, perfil as pf
from predictivo.experimento_seguimiento_mensual import ASIS, MESES, NOMBRE_MES, armar, variables_asistencia
from predictivo.real_t1 import PARAMS, THRESHOLD, summarize

VERSION = 'seguimiento-mensual-v2'  # v2 = v1 + notas por dimensión (decisión de diseño del 23/11/2026)
VERSION_V1 = 'seguimiento-mensual-v1'
NOTAS = ['promedio_T1', 'nota_minima_T1', 'n_areas_bajo_51_T1']
VARIABLES_V1 = ASIS + NOTAS + ['promedio_T2', 'grado']
VARIABLES = VARIABLES_V1 + list(dg.VARIABLES)
_ARTEFACTOS = Path(__file__).resolve().parent.parent / 'artifacts'
DIRECTORIO, DIRECTORIO_V1 = _ARTEFACTOS / 'seguimiento_mensual_v2', _ARTEFACTOS / 'seguimiento_mensual_v1'
ADOPCION = ('Incluye 8 variables de notas por dimensión (Ser, Saber, Hacer, Decidir, autoevaluación) por decisión de diseño, para no mirar las notas '
    'solo en general. No mejoraron la detección: en junio la AP baja 0,010 (docs/experimento_desglose_resumen.md).')
RACHA_ALERTA = 5  # regla propuesta; en los archivos recibidos (origen no verificado): 11 de 11 abandonos, 0 de 1878 matrículas que continuaron
UMBRAL_MEDIO, UMBRAL_ALTO = .5, .8
CODIGO = {'PRESENTE': 'A', 'ATRASO': 'R', 'FALTA': 'F', 'LICENCIA': 'L'}
DESCRIPCION = {
    'prop_faltas': 'Proporción de faltas en el año', 'prop_retrasos': 'Proporción de atrasos', 'prop_licencias': 'Proporción de licencias',
    'faltas_ult10': 'Faltas en los últimos 10 días de clase', 'faltas_ult20': 'Faltas en los últimos 20 días de clase',
    'racha_actual': 'Faltas seguidas hasta hoy', 'racha_max': 'Racha más larga de faltas', 'dias_desde_asistencia': 'Días de clase desde que asistió por última vez',
    'tendencia_faltas': 'Tendencia semanal de las faltas', 'dias_registrados': 'Días de clase registrados',
    'promedio_T1': 'Promedio del 1.er trimestre', 'nota_minima_T1': 'Nota más baja del 1.er trimestre', 'n_areas_bajo_51_T1': 'Áreas con nota menor a 51 (1.er trimestre)',
    'promedio_T2': 'Promedio del 2.º trimestre', 'grado': 'Grado', **dg.VARIABLES}


def mes_modelo(fecha):
    """Modelo que corresponde a una fecha: el del mes en curso (febrero a octubre); noviembre usa el de octubre."""
    if fecha.month < 2:
        return None
    return min(fecha.month, 10)


# ---------------------------------------------------------------- entrenamiento

def entrenar(excel, asistencia_csv, desglose_csv, directorio, repeticiones=20, folds=5, seed=1607):
    import sklearn
    import xgboost as xgb
    from sklearn.model_selection import StratifiedGroupKFold
    if any(v.startswith('POST_') for v in VARIABLES):
        raise ValueError('Las columnas POST_* no pueden ser predictores.')
    d = dg.con_desglose(armar(excel, asistencia_csv), desglose_csv)
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
            'parámetros del modelo en uso, sin ajuste; variables solo con datos hasta el corte. ' + ADOPCION,
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


def calcular(db, anio, fecha=None, directorio=DIRECTORIO, solo_cursos=None):
    """Riesgo a la fecha de todas las matrículas vigentes de la gestión `anio`, solo con lo registrado hasta `fecha`.
    `solo_cursos`: limita el cálculo a esos cursos (vista del docente); el puntaje de cada estudiante no cambia.
    Solo lectura: no escribe en la base."""
    from sqlalchemy import select
    import models as m
    gestion = db.scalar(select(m.Gestion).where(m.Gestion.anio == anio))
    if gestion is None:
        raise LookupError(f'No existe la gestión {anio}.')
    cursos = {c.id: c for c in db.scalars(select(m.Curso).where(m.Curso.gestion_id == gestion.id))}
    if solo_cursos is not None:
        cursos = {k: v for k, v in cursos.items() if k in set(solo_cursos)}
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
    diario = {(mid, jid): estado for mid, jid, estado in db.execute(select(m.Asistencia.matricula_id, m.Asistencia.jornada_id, m.Asistencia.estado)
        .where(m.Asistencia.jornada_id.in_(list(jornadas)))) if jid in jornadas} if ids and jornadas else {}
    por_curso = defaultdict(list)
    for j in jornadas.values():
        por_curso[j.curso_id].append(j)
    sesiones = {s.id: s.jornada_id for s in db.scalars(select(m.SesionClase).where(m.SesionClase.curso_id.in_(cursos), m.SesionClase.dictada == True))
        if s.jornada_id in jornadas} if cursos else {}
    horas = defaultdict(list)
    if sesiones:
        for r in db.scalars(select(m.AsistenciaMateria).where(m.AsistenciaMateria.sesion_id.in_(sesiones))):
            horas[(r.matricula_id, sesiones[r.sesion_id])].append(r.estado)
    notas, dimensiones = defaultdict(list), defaultdict(list)
    if ids:
        evaluaciones = {e.id: e for e in db.scalars(select(m.Evaluacion).where(m.Evaluacion.curso_id.in_(cursos), m.Evaluacion.fecha_aplicacion <= fecha))}
        sobran = dg.redundantes(evaluaciones.values())
        evaluaciones = {k: e for k, e in evaluaciones.items() if k not in sobran}
        asignaciones = {a.id: a.materia_id for a in db.scalars(select(m.AsignacionDocente).where(m.AsignacionDocente.curso_id.in_(cursos)))}
        numero_periodo = {p.id: p.numero for p in periodos.values()}
        for eid, mid, puntaje in db.execute(select(m.Calificacion.evaluacion_id, m.Calificacion.matricula_id, m.Calificacion.puntaje)
                .where(m.Calificacion.evaluacion_id.in_(list(evaluaciones)), m.Calificacion.estado == 'CALIFICADA')):
            e = evaluaciones[eid]
            notas[(mid, numero_periodo.get(e.periodo_id))].append((asignaciones.get(e.asignacion_id), e.titulo, float(puntaje) / float(e.puntaje_maximo) * 100))
            if e.dimension:
                dimensiones[(mid, numero_periodo.get(e.periodo_id))].append((asignaciones.get(e.asignacion_id), e.dimension, float(puntaje) / float(e.puntaje_maximo) * 100))
    estudiantes = {e.id: e for e in db.scalars(select(m.Estudiante).where(m.Estudiante.id.in_([x.estudiante_id for x in matriculas])))} if matriculas else {}
    filas, info = [], []
    for mat in matriculas:
        curso = cursos[mat.curso_id]
        dias = sorted((j.fecha, codigo_dia(diario.get((mat.id, j.id)), horas.get((mat.id, j.id), []))) for j in por_curso[curso.id]
            if j.fecha >= mat.fecha_ingreso)
        regs = [(f, c) for f, c in dias if c is not None]
        if not regs:
            continue  # sin asistencia registrada no hay seguimiento posible
        v = variables_asistencia(regs)
        p1 = notas_trimestre(dg.notas_de_area(notas.get((mat.id, 1), []))) if t1_cerrado else (None, None, None)
        p2 = notas_trimestre(dg.notas_de_area(notas.get((mat.id, 2), []))) if t2_cerrado else (None, None, None)
        est = estudiantes[mat.estudiante_id]
        v.update(promedio_T1=p1[0], nota_minima_T1=p1[1], n_areas_bajo_51_T1=p1[2], promedio_T2=p2[0], grado=curso.grado)
        v.update(dg.variables(dimensiones.get((mat.id, 1)) if t1_cerrado else None, dimensiones.get((mat.id, 2)) if t2_cerrado else None))
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
            notas_t1_disponibles=fila['promedio_T1'] is not None, indicadores={k: fila.get(k) for k in VARIABLES},
            perfil=pf.alerta(fila, nivel(prob), RACHA_ALERTA)))
    orden = sorted(alertas, key=lambda a: (pf.NIVELES.index(a['perfil']['nivel']), not a['perfil']['notas_y_asistencia'], -a['probabilidad']))
    for i, a in enumerate(orden, 1):
        a['puesto'] = i
    met = metricas(directorio)
    return {**base, 'total': len(orden), 'alertas': orden, 'nota_perfil': pf.NOTA, 'notas_t1_incluidas': t1_cerrado, 'promedio_t2_incluido': t2_cerrado,
        'validacion_del_corte': met and met['cortes'].get(NOMBRE_MES[mes]),
        'modelo_usado': f'entrenado sin la gestión {anio} (la gestión no se usó para aprender)' if fuera_de_muestra else 'modelo final (todas las gestiones 2021-2025)'}


# ---------------------------------------------------------------- casos (gestión de alertas)

def _sha256(ruta):
    import hashlib
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def registrar_modelo(db, directorio=DIRECTORIO):
    """Registro del modelo de seguimiento en modelos_predictivos (una sola vez); lo usan los casos abiertos."""
    from datetime import datetime
    from sqlalchemy import select
    import models as m
    modelo = db.scalar(select(m.ModeloPredictivo).where(m.ModeloPredictivo.version == VERSION))
    if modelo is not None:
        return modelo
    met = metricas(directorio)
    if met is None:
        raise LookupError('Falta artifacts/seguimiento_mensual_v2: ejecutar el entrenamiento.')
    ruta = Path(directorio) / 'metricas.json'
    modelo = m.ModeloPredictivo(version=VERSION, algoritmo='XGBoost', version_variables=VERSION, origen_datos='REAL',
        objetivo='Abandono dentro de la gestión: un modelo por fin de mes con lo registrado hasta la fecha, más la alerta inmediata de '
            f'{RACHA_ALERTA} faltas seguidas.',
        entrenado_en=datetime.fromtimestamp(ruta.stat().st_mtime).replace(microsecond=0), datos_hasta=date(2025, 11, 30),
        artefacto_uri=str(ruta), artefacto_sha256=_sha256(ruta), umbral_medio=UMBRAL_MEDIO, umbral_alto=UMBRAL_ALTO,
        protocolo_validacion=met['protocolo'], metricas=met)
    db.add(modelo)
    db.flush()
    return modelo


def casos_abiertos(db, matriculas):
    """{matrícula: (alerta_id, estado)} de casos no cerrados (de cualquier modelo)."""
    from sqlalchemy import select
    import models as m
    if not matriculas:
        return {}
    rows = db.execute(select(m.CortePredictivo.matricula_id, m.Alerta.id, m.Alerta.estado)
        .join(m.Prediccion, m.Prediccion.corte_id == m.CortePredictivo.id).join(m.Alerta, m.Alerta.prediccion_id == m.Prediccion.id)
        .where(m.CortePredictivo.matricula_id.in_(list(matriculas)), m.Alerta.estado != 'CERRADA').order_by(m.Alerta.id)).all()
    return {mid: (aid, est) for mid, aid, est in rows}


def responsable_por_defecto(db):
    from sqlalchemy import select
    import models as m
    for rol in ('Director', 'Orientador', 'Admin'):
        u = db.scalar(select(m.Usuario).where(m.Usuario.rol == rol, m.Usuario.activo.is_(True)).order_by(m.Usuario.id))
        if u is not None:
            return u
    raise LookupError('No hay un usuario activo de Dirección, Orientación o administración para responsabilizar el caso.')


def abrir_caso(db, calculo, alerta, responsable, usuario=None, automatico=False):
    """Guarda una alerta del seguimiento como caso (corte + predicción + alerta) para gestionarlo. No duplica: si la
    matrícula ya tiene un caso sin cerrar, devuelve ese. `calculo` es el resultado de calcular() y `alerta` una de sus filas."""
    from datetime import datetime, time
    from fastapi.encoders import jsonable_encoder
    import models as m
    existente = casos_abiertos(db, [alerta['matricula_id']]).get(alerta['matricula_id'])
    if existente:
        return existente[0], False
    modelo = registrar_modelo(db)
    fecha = date.fromisoformat(calculo['fecha'])
    inmediata = alerta['alerta_inmediata']
    perfil = alerta['perfil']
    por_perfil = not inmediata and alerta['nivel'] == 'BAJO'
    nivel_caso = 'ALTO' if inmediata or perfil['nivel'] == 'ROJO' else alerta['nivel'] if alerta['nivel'] != 'BAJO' else 'MEDIO'
    corte = m.CortePredictivo(matricula_id=alerta['matricula_id'], fecha_corte=fecha, disponible_hasta=datetime.combine(fecha, time(23, 59, 59)),
        version_variables=VERSION, estado='ELEGIBLE', motivo='Alerta inmediata (faltas seguidas)' if inmediata else 'Perfil por dimensiones' if por_perfil else 'Prioridad del modelo mensual',
        variables=jsonable_encoder(dict(indicadores=alerta['indicadores'], perfil=perfil, mes=calculo['mes'], gestion=calculo['gestion'],
            modelo_usado=calculo.get('modelo_usado'), racha_actual=alerta['racha_actual'], ultima_asistencia=alerta['ultima_asistencia'])))
    db.add(corte)
    db.flush()
    principales = [dict(variable='racha_actual', descripcion=DESCRIPCION['racha_actual'], valor=alerta['racha_actual'])] if inmediata else []
    principales += [f for f in alerta['factores'] if f['variable'] != 'racha_actual' or not inmediata]
    pred = m.Prediccion(corte_id=corte.id, modelo_id=modelo.id, probabilidad=round(min(max(alerta['probabilidad'], 0), 1), 6),
        nivel=nivel_caso,
        factores=jsonable_encoder(dict(principales=principales, uso='SEGUIMIENTO_A_LA_FECHA',
            origen='ALERTA_INMEDIATA' if inmediata else 'PERFIL' if por_perfil else 'MODELO_MENSUAL', apertura='AUTOMATICA' if automatico else 'MANUAL')))
    db.add(pred)
    db.flush()
    caso = m.Alerta(prediccion_id=pred.id, responsable_id=responsable.id)
    db.add(caso)
    db.flush()
    motivo = ('Caso abierto automáticamente: ' if automatico else 'Caso abierto desde el seguimiento: ') + (
        f"{alerta['racha_actual']} faltas seguidas" if inmediata else f"{perfil['nivel'].lower()}: {pf.texto(perfil)}")
    db.add(m.AuditoriaCambio(usuario_id=(usuario or responsable).id, tabla_afectada='alertas', registro_id=caso.id, operacion='ALTA',
        motivo=motivo, antes=None, despues=jsonable_encoder(dict(estado='NUEVA', responsable_id=responsable.id))))
    return caso.id, True


def dia_de_la_regla(db, matricula, fecha):
    """Día en que la racha de faltas vigente a `fecha` llegó a RACHA_ALERTA (None si no llegó), por asistencia diaria."""
    from sqlalchemy import select
    import models as m
    dias = list(db.execute(select(m.JornadaClase.fecha, m.Asistencia.estado).join(m.Asistencia, m.Asistencia.jornada_id == m.JornadaClase.id)
        .where(m.Asistencia.matricula_id == matricula.id, m.JornadaClase.es_lectiva == True, m.JornadaClase.fecha <= fecha).order_by(m.JornadaClase.fecha)))
    racha = []
    for f, estado in dias:
        racha = racha + [f] if estado == 'FALTA' else []
    return racha[RACHA_ALERTA - 1] if len(racha) >= RACHA_ALERTA else None


def abrir_inmediatas(db, calculo):
    """Apertura automática: cada alerta inmediata sin caso abierto pasa a ser un caso. Devuelve cuántos abrió."""
    pendientes = [a for a in calculo['alertas'] if a['alerta_inmediata']]
    if not pendientes:
        return 0
    responsable = responsable_por_defecto(db)
    return sum(abrir_caso(db, calculo, a, responsable, automatico=True)[1] for a in pendientes)


def _texto(variable, valor):
    if valor is None:
        return 'sin dato'
    if variable.startswith('prop'):
        return f'{valor * 100:.1f} %'.replace('.', ',')
    if variable == 'tendencia_faltas':
        return 'en aumento' if valor > 0 else 'en descenso' if valor < 0 else 'estable'
    return f'{round(valor, 1) + 0:.1f}'.removesuffix('.0').replace('.', ',') if isinstance(valor, (int, float)) else str(valor)


def explicar(corte, pred, umbral_medio, umbral_alto, curso_txt, anio, companeros=(), dia_regla=None, vigente=None):
    """Explicación de un caso del seguimiento con la misma forma que la del modelo anterior (para la misma pantalla)."""
    import xgboost as xgb
    v = corte.variables or {}
    ind = v.get('indicadores') or {}
    mes = next((k for k, n in NOMBRE_MES.items() if n == v.get('mes')), None)
    # Un caso abierto con la v1 se explica con el modelo vigente si se pasan sus indicadores recalculados a la misma
    # fecha (`vigente`); el puntaje guardado no cambia. Sin ellos, con la versión con la que se abrió.
    anterior = corte.version_variables == VERSION_V1
    v1 = anterior and vigente is None
    if anterior and vigente is not None:
        ind = vigente
    VARIABLES = VARIABLES_V1 if v1 else globals()['VARIABLES']
    booster = cargar_modelo(mes, DIRECTORIO_V1 if v1 else DIRECTORIO, sin_anio=anio) if mes else None
    if booster is None:
        raise LookupError('No se encontró el modelo del mes de este caso.')
    x = np.array([[np.nan if ind.get(k) is None else float(ind[k]) for k in VARIABLES]], dtype=float)
    contrib = booster.predict(xgb.DMatrix(x, feature_names=VARIABLES, missing=np.nan), pred_contribs=True)[0]
    base = float(contrib[-1])
    puntaje = float(1 / (1 + np.exp(-(base + float(contrib[:-1].sum())))))
    perfil = pf.alerta(ind, pred.nivel if (pred.factores or {}).get('origen') == 'MODELO_MENSUAL' else 'BAJO', RACHA_ALERTA)
    medias = {}
    for k in VARIABLES:
        vals = [c[k] for c in companeros if c.get(k) is not None]
        medias[k] = float(np.mean(vals)) if vals else None
    grupo = lambda k: 'Notas por dimensión' if k in dg.VARIABLES else 'Notas' if k in NOTAS + ['promedio_T2'] else 'Curso' if k == 'grado' else 'Asistencia'
    variables = [dict(variable=k, etiqueta=DESCRIPCION[k], grupo=grupo(k), valor=ind.get(k), valor_texto=_texto(k, ind.get(k)),
        media_curso=medias[k], media_gestion=None, comparacion='' if medias[k] is None or k == 'grado' else f'curso: {_texto(k, medias[k])}', aporte=round(float(c), 4),
        efecto='sube' if c > 0.005 else 'baja' if c < -0.005 else 'neutro') for k, c in zip(VARIABLES, contrib[:-1])]
    variables.sort(key=lambda r: -abs(r['aporte']))
    suben = [r for r in variables if r['efecto'] == 'sube']
    total = sum(r['aporte'] for r in suben) or 1
    for r in suben:
        r['peso_relativo'] = round(100 * r['aporte'] / total, 1)
    inmediata = (pred.factores or {}).get('origen') == 'ALERTA_INMEDIATA'
    racha = v.get('racha_actual')
    p = float(pred.probabilidad)
    p_txt = f'{p:.2f}'.replace('.', ',')
    if inmediata:
        motivo = (f'Alerta inmediata: al {corte.fecha_corte:%d/%m/%Y} acumulaba {racha} faltas seguidas' + (f'; llegó a {RACHA_ALERTA} el {dia_regla:%d/%m/%Y}' if dia_regla else '')
            + f' (regla de {RACHA_ALERTA}). '
            f'Puntaje del modelo de {v.get("mes")}: {p_txt}.')
    elif (pred.factores or {}).get('origen') == 'PERFIL':
        motivo = f'Alerta por perfil: {pf.texto(perfil)}. Puntaje del modelo de {v.get("mes")}: {p_txt}.'
    else:
        motivo = f'Puntaje del modelo de {v.get("mes")} ({p_txt}) por encima del umbral de prioridad {pred.nivel.lower()}.'
    principales = ', '.join(f"{r['etiqueta'].lower()} ({r['valor_texto']})" for r in suben[:3])
    resumen = (f'Dejó de asistir: {racha} faltas seguidas, última asistencia {v.get("ultima_asistencia") or "sin registro"}. ' if inmediata else '')
    resumen += f'Lo que más eleva la prioridad en el modelo: {principales}.' if suben else 'Ninguna variable eleva el puntaje del modelo.'
    caso = dict(tipo='actual', titulo=f'Caso abierto el {corte.fecha_corte:%d/%m/%Y} (gestión {anio}).',
        texto='Contactar a la familia lo antes posible: llamada o visita, y acordar el retorno del estudiante.' if inmediata else
            'Revisar con el docente si hay señales recientes (faltas, cambio de domicilio, situación familiar) antes de decidir una acción.')
    como_leer = [f'La alerta inmediata se activa con {RACHA_ALERTA} o más faltas seguidas; en los archivos recibidos de 2021-2025 (origen '
        'no verificado) se cumplió en 11 de 11 abandonos. Es retrospectivo y el abandono se definió con la asistencia.', 'El puntaje del modelo ordena la prioridad; no es la probabilidad real de abandono.']
    return dict(nivel=dict(nivel=pred.nivel, puntaje=round(p, 6), umbral_medio=umbral_medio, umbral_alto=umbral_alto, puesto=1, de=1, motivo=motivo,
            nota='El puntaje no está calibrado: ordena la prioridad de revisión, no es la probabilidad real de abandono.'),
        resumen=resumen, curso=curso_txt, gestion=anio, estudiantes_en_curso=len(companeros) + 1, areas_en_desarrollo=[],
        punto_partida=round(float(1 / (1 + np.exp(-base))), 6), puntaje_recalculado=round(puntaje, 6),
        coincide_con_guardado=abs(puntaje - p) < 1e-3, variables=variables, perfil=dict(**perfil, nota=pf.NOTA),
        metodo=f'Aportes SHAP del modelo de seguimiento de {v.get("mes")} ({v.get("modelo_usado") or "modelo final"}).'
            + (f' El caso se abrió con la versión anterior (15 variables, puntaje guardado {p_txt}); esta explicación usa la vigente, con las notas '
               'por dimensión registradas hasta la misma fecha.' if anterior and not v1 else ''),
        advertencia='Los aportes muestran lo que el modelo aprendió con 11 abandonos; úselos como orientación junto con el criterio docente.',
        caso=caso, como_leer=como_leer, abandono_confirmado=False)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='accion', required=True)
    e = sub.add_parser('entrenar')
    e.add_argument('--excel', default='../data/DATASET_INSTITUCION_2021_2025.xlsx')
    e.add_argument('--asistencia', default='../data/DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv')
    e.add_argument('--desglose', default='../data/DESGLOSE_INSTITUCION_2021_2025.csv')
    e.add_argument('--directorio', default=str(DIRECTORIO))
    e.add_argument('--repeticiones', type=int, default=20)
    c = sub.add_parser('abrir-casos', help='Abre como caso las alertas inmediatas de la gestión más reciente (para una tarea diaria).')
    c.add_argument('--gestion', type=int)
    a = p.parse_args()
    if a.accion == 'entrenar':
        entrenar(a.excel, a.asistencia, a.desglose, a.directorio, a.repeticiones)
    else:
        from sqlalchemy import select, func
        from database import SessionLocal
        import models as m
        with SessionLocal() as db:
            anio = a.gestion or db.scalar(select(func.max(m.Gestion.anio)))
            n = abrir_inmediatas(db, calcular(db, anio))
            db.commit()
            print(f'Gestión {anio}: {n} caso(s) nuevo(s).')


if __name__ == '__main__':
    main()
