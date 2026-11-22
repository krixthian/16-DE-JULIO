"""Análisis de los registros pedagógicos originales (observaciones del docente revisor, 22/11/2026).

A. Calidad de los datos: ¿las notas T1 de quienes abandonaron se registraron de forma estándar ("notas planas")?
   ¿La asistencia del T1, incluso día por día, anticipa el abandono?
B. Alerta de inasistencia continua: con la asistencia diaria de todo el año, ¿una racha de k faltas seguidas detecta
   a quienes están abandonando antes del cierre del trimestre en que se registra el abandono? ¿Con cuántas falsas alarmas?

No modifica el modelo de producción ni la base. Ningún nombre sale de los registros: se empareja por curso y notas T1.
Uso (desde backend):
    python -m predictivo.analisis_registros --registros "C:/.../DATOS_HISTORICO" "C:/.../DATOS" --salida ../docs/analisis_registros_detallados.json
"""
import argparse
import json
from datetime import date
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

from predictivo import registros_pedagogicos as rp, emparejar_registros as er, variables_detalladas as vd

UMBRAL_PLANO = 4.0  # desviación entre áreas (puntos de 100) por debajo de la cual las notas se consideran "planas"
RACHAS = (3, 5, 10)


def leer_todo(carpetas, ds):
    """{(codigo, gestion): {'t1': variables detalladas, 'anual': [(fecha, código)], 'dias_curso': [fechas]}}"""
    import openpyxl
    out = {}
    for carpeta in carpetas:
        for ruta in sorted(Path(carpeta).rglob('REGISTRO_PEDAGOGICO_*.xlsx')):
            registro = rp.leer(ruta)
            pares, _ = er.emparejar(registro, ds)
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            anual = rp.asistencia_anual(wb, registro['gestion'])
            wb.close()
            dias = sorted({d for v in anual.values() for d, _ in v})
            for orden, codigo in pares.items():
                out[(codigo, registro['gestion'])] = {'t1': vd.calcular(registro['estudiantes'][orden]),
                    'anual': anual.get(orden, []), 'dias_curso': dias}
    return out


def primera_racha(registros, k, codigos=('F',)):
    """Fecha en que el estudiante completa k días seguidos con alguno de los códigos (None si nunca)."""
    racha = 0
    for d, c in registros:
        racha = racha + 1 if c in codigos else 0
        if racha >= k:
            return d
    return None


def cierre_trimestre(trimestre, dias_curso):
    """Último día de clase del trimestre en que se registra el abandono (T2: hasta agosto; T3: hasta noviembre)."""
    limite = {'T2': 8, 'T3': 11}.get(str(trimestre).strip().upper())
    candidatos = [d for d in dias_curso if limite and d.month <= limite]
    return max(candidatos) if candidatos else None


def calidad(m):
    y = m.y_abandono_intra_anual == 1
    plano = m.dispersion_areas < UMBRAL_PLANO
    return dict(
        umbral_plano=UMBRAL_PLANO,
        notas_planas={'abandonaron': int((y & plano).sum()), 'de_abandonos': int(y.sum()),
            'continuaron': int((~y & plano).sum()), 'de_continuaron': int((~y).sum())},
        dispersion_mediana={'abandonaron': float(m[y].dispersion_areas.median()), 'continuaron': float(m[~y].dispersion_areas.median()),
            'continuaron_percentil_5': float(m[~y].dispersion_areas.quantile(.05))},
        ser_exacto_3_de_5={'abandonaron': int((y & (m.ser_media.round(3) == .6)).sum()), 'continuaron': int((~y & (m.ser_media.round(3) == .6)).sum())},
        autoevaluacion_exacta_6={'abandonaron': int((y & (m.autoevaluacion_media.round(3) == 6)).sum()),
            'continuaron': int((~y & (m.autoevaluacion_media.round(3) == 6)).sum())},
        medianas={k: {'abandonaron': None if pd.isna(m[y][k].median()) else float(m[y][k].median()),
            'continuaron': None if pd.isna(m[~y][k].median()) else float(m[~y][k].median())} for k in vd.NOMBRES})


def senal_asistencia_t1(m, repeticiones=20):
    """Validación por estudiante (5 x repeticiones) de modelos SOLO con asistencia T1 (sin notas)."""
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold
    from predictivo.real_t1 import PARAMS
    y, g = m.y_abandono_intra_anual.astype(int).to_numpy(), m.codigo_anonimo.to_numpy()
    base = ['faltas_T1', 'atrasos_T1', 'licencias_T1', 'tasa_asistencia_T1', 'edad_31marzo', 'grado']
    detalle = ['faltas_feb', 'faltas_abr', 'tendencia_faltas', 'faltas_ultimas_4_semanas', 'cambio_faltas_final_inicio', 'racha_max_faltas',
        'racha_final_faltas', 'faltas_lunes_viernes', 'retrasos_ultimas_4_semanas']
    out = {}
    for nombre, cols in (('asistencia_total_t1', base), ('asistencia_dia_a_dia_t1', base + detalle)):
        aps, aucs, det, fa = [], [], [], []
        for rep in range(repeticiones):
            s = np.zeros(len(y))
            for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=1607 + rep).split(m, y, g):
                mod = xgb.XGBClassifier(**PARAMS, scale_pos_weight=float((y[tr] == 0).sum() / y[tr].sum())).fit(m[cols].iloc[tr], y[tr])
                s[te] = mod.predict_proba(m[cols].iloc[te])[:, 1]
            aps.append(average_precision_score(y, s))
            aucs.append(roc_auc_score(y, s))
            det.append(int(((s >= .5) & (y == 1)).sum()))
            fa.append(int(((s >= .5) & (y == 0)).sum()))
        out[nombre] = dict(variables=cols, roc_auc=float(np.mean(aucs)), average_precision=float(np.mean(aps)),
            average_precision_de=float(np.std(aps)), detectados=float(np.mean(det)), falsas_alarmas=float(np.mean(fa)))
    out['azar'] = dict(average_precision=float(y.mean()))
    return out


def alerta_inasistencia(m, datos):
    """Racha de k faltas seguidas en el año: detección de abandonos, anticipación frente al cierre del trimestre
    en que se registra el abandono y falsas alarmas (estudiantes que continuaron)."""
    res = {}
    for codigos, etiqueta in ((('F',), 'faltas'), (('F', 'L'), 'faltas_o_licencias')):
        for k in RACHAS:
            detectados, anticipacion, demora, falsas = 0, [], [], 0
            for _, r in m.iterrows():
                d = datos[(r.codigo_anonimo, r.gestion)]
                alerta = primera_racha(d['anual'], k, codigos)
                if r.y_abandono_intra_anual == 1:
                    if alerta is None:
                        continue
                    detectados += 1
                    cierre = cierre_trimestre(r.trimestre_caida, d['dias_curso'])
                    if cierre:
                        anticipacion.append((cierre - alerta).days)
                    asiste = [f for f, c in d['anual'] if c in ('A', 'R') and f <= alerta]
                    if asiste:
                        demora.append((alerta - max(asiste)).days)
                elif alerta is not None:
                    falsas += 1
            n_ab = int((m.y_abandono_intra_anual == 1).sum())
            res[f'{etiqueta}_{k}_dias'] = dict(codigos=list(codigos), racha=k, detectados=detectados, abandonos=n_ab,
                falsas_alarmas=falsas, continuaron=int((m.y_abandono_intra_anual == 0).sum()),
                precision=detectados / (detectados + falsas) if detectados + falsas else None,
                anticipacion_dias_mediana=median(anticipacion) if anticipacion else None,
                anticipacion_dias_min=min(anticipacion) if anticipacion else None,
                demora_desde_ultima_asistencia_mediana=median(demora) if demora else None)
    return res


def patrones_asistencia(m, datos):
    """Patrones atípicos de la asistencia anual: ¿el abandono empieza justo después del último día de clases de un mes?
    ¿Cuál es la racha más larga de faltas de quienes continuaron?"""
    fin_de_mes = sin_asistencia = 0
    rachas = {}
    for _, r in m.iterrows():
        d = datos[(r.codigo_anonimo, r.gestion)]
        if r.y_abandono_intra_anual == 1:
            asistio = [f for f, c in d['anual'] if c in ('A', 'R')]
            if not asistio:
                sin_asistencia += 1
                continue
            ultima = max(asistio)
            ultimo_del_mes = max(f for f in d['dias_curso'] if (f.year, f.month) == (ultima.year, ultima.month))
            fin_de_mes += ultima == ultimo_del_mes
        else:
            racha = maximo = 0
            for _, c in d['anual']:
                racha = racha + 1 if c == 'F' else 0
                maximo = max(maximo, racha)
            rachas[maximo] = rachas.get(maximo, 0) + 1
    return dict(abandono_desde_fin_de_mes=fin_de_mes, abandonos_sin_ninguna_asistencia=sin_asistencia,
        abandonos=int((m.y_abandono_intra_anual == 1).sum()),
        continuaron_racha_maxima_de_faltas={str(k): v for k, v in sorted(rachas.items())})


def main():
    from predictivo.real_t1 import load
    p = argparse.ArgumentParser()
    p.add_argument('--registros', nargs='+', required=True)
    p.add_argument('--excel', default='../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx')
    p.add_argument('--salida', default='../docs/analisis_registros_detallados.json')
    p.add_argument('--repeticiones', type=int, default=20)
    a = p.parse_args()
    ds = pd.read_excel(a.excel, sheet_name='DATOS_REAL')
    datos = leer_todo(a.registros, ds)
    t1 = pd.DataFrame([{'codigo_anonimo': c, 'gestion': g, **v['t1']} for (c, g), v in datos.items()])
    base = load(a.excel).merge(ds[['codigo_anonimo', 'gestion', 'trimestre_caida']], on=['codigo_anonimo', 'gestion'])
    m = base.merge(t1, on=['codigo_anonimo', 'gestion'])
    if len(m) != len(base):
        raise ValueError(f'Se emparejaron {len(m)} de {len(base)} matrículas.')
    reporte = dict(
        version='analisis-registros-v1', matriculas=len(m), abandonos=int(m.y_abandono_intra_anual.sum()),
        fuente='Registros pedagógicos originales 2021-2025 (asistencia diaria A/F/R/L y notas por actividad), emparejados sin nombres.',
        calidad_datos=calidad(m), senal_asistencia_t1=senal_asistencia_t1(m, a.repeticiones),
        alerta_inasistencia=alerta_inasistencia(m, datos), patrones_asistencia=patrones_asistencia(m, datos))
    Path(a.salida).write_text(json.dumps(reporte, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    c = reporte['calidad_datos']
    print('Notas planas:', c['notas_planas'], '| dispersion mediana:', {k: round(v, 2) for k, v in c['dispersion_mediana'].items()})
    print('SER 3/5:', c['ser_exacto_3_de_5'], '| Autoevaluacion 6:', c['autoevaluacion_exacta_6'])
    for k, v in reporte['senal_asistencia_t1'].items():
        print('Asistencia T1', k, {x: (round(y, 3) if isinstance(y, float) else y) for x, y in v.items() if x != 'variables'})
    print('Patrones de asistencia:', reporte['patrones_asistencia'])
    for k, v in reporte['alerta_inasistencia'].items():
        print('Alerta', k, {x: (round(y, 3) if isinstance(y, float) else y) for x, y in v.items() if x != 'codigos'})


if __name__ == '__main__':
    main()
