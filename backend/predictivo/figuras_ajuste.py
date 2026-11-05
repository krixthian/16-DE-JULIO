"""Figuras del objetivo 2 (ajuste anidado) a partir de reporte_ajuste.json y oof_ajuste.npz; solo cifras agregadas.

Uso desde backend: python -m predictivo.figuras_ajuste artifacts/real_t1_ajuste_v1 ../docs/figuras
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from predictivo.ajuste_real import bootstrap_samples
from predictivo.figuras_real import SURFACE, INK, INK2, MUTED, GRID, BASE as GRAY, decimal, setup, frame

BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
NAMES = {'xgboost_base': 'XGBoost base', 'xgboost_ajustado': 'XGBoost ajustado', 'regresion_logistica': 'Regresión logística',
    'regla_promedio_T1': 'Regla promedio T1', 'xgboost_base_sigmoide': 'Base + calibración sigmoide',
    'xgboost_ajustado_sigmoide': 'Ajustado + sigmoide', 'xgboost_ajustado_isotonica': 'Ajustado + isotónica'}
COLOR = {'xgboost_base': BLUE, 'xgboost_ajustado': ORANGE, 'regresion_logistica': AQUA}
SOURCE = 'Fuente: dataset real U.E. 16 de Julio 2021-2025 (790 matrículas, 11 abandonos). Validación anidada por estudiante: externa 5 × 20, interna 4.'


def title(fig, text, subtitle):
    fig.text(.04, .94, text, fontsize=26, fontweight='bold', color=INK, va='top')
    fig.text(.04, .875, subtitle, fontsize=15, color=INK2, va='top')
    fig.text(.04, .03, SOURCE, fontsize=11, color=MUTED)


def curves(npz, out, boots=500):
    from sklearn.metrics import roc_curve, precision_recall_curve
    y, groups = npz['y'], npz['grupo']
    samples = bootstrap_samples(y, groups, boots)
    grid = np.linspace(0, 1, 101)

    def roc_at(yy, s):
        fpr, tpr, _ = roc_curve(yy, s)
        return np.interp(grid, fpr, tpr)

    def pr_at(yy, s):
        prec, rec, _ = precision_recall_curve(yy, s)
        # Precisión interpolada: máxima precisión con sensibilidad >= r.
        return np.array([prec[rec >= r].max() if (rec >= r).any() else 0 for r in grid])

    fig = setup()
    title(fig, 'Curvas ROC y precisión-sensibilidad', 'Curva media de 20 repeticiones fuera de pliegue · banda = IC 95 % bootstrap por estudiante')
    for i, (fn, label, xlabel, ylabel) in enumerate(((roc_at, 'ROC', 'Tasa de falsas alarmas', 'Sensibilidad'),
            (pr_at, 'Precisión-sensibilidad', 'Sensibilidad', 'Precisión'))):
        ax = fig.add_axes([.08 + i * .47, .15, .38, .62])
        frame(ax)
        ax.grid(axis='y', color=GRID, linewidth=1)
        for name in ('xgboost_base', 'xgboost_ajustado', 'regresion_logistica'):
            reps = npz[name]
            mean = np.mean([fn(y, s) for s in reps], axis=0)
            if name != 'regresion_logistica':
                band = np.array([fn(y[rows], reps[b % len(reps)][rows]) for b, rows in enumerate(samples)])
                ax.fill_between(grid, np.percentile(band, 2.5, axis=0), np.percentile(band, 97.5, axis=0), color=COLOR[name], alpha=.15, linewidth=0)
            ax.plot(grid, mean, color=COLOR[name], linewidth=2, label=NAMES[name])
        if fn is roc_at:
            ax.plot([0, 1], [0, 1], color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        else:
            ax.axhline(y.mean(), color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
            ax.text(.98, y.mean() + .02, 'tasa base', color=MUTED, fontsize=11.5, ha='right')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(label, loc='left', fontsize=16, color=INK, pad=10)
        ax.spines['left'].set_visible(True)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: decimal(v, 1) if v % 1 else f'{v:.0f}'))
    fig.axes[0].legend(loc='lower right', frameon=False, fontsize=13)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def comparison(report, out):
    models = report['modelos']
    keys = ['xgboost_ajustado', 'xgboost_base', 'regresion_logistica', 'regla_promedio_T1'][::-1]
    fig = setup()
    title(fig, 'Modelo ajustado frente al base y los baselines', 'Mismos pliegues externos para todos · punto = media · barra = IC 95 % bootstrap por estudiante')
    for i, (metric, label, base) in enumerate((('roc_auc', 'ROC-AUC', .5), ('average_precision', 'Average precision (AP)', models['siempre_continuidad']['average_precision']))):
        ax = fig.add_axes([.24 + i * .385, .2, .33, .55])
        frame(ax)
        for yy, k in enumerate(keys):
            m, color = models[k], COLOR.get(k, GRAY)
            lo, hi = m['ic95'][metric]
            ax.plot([lo, hi], [yy, yy], color=color, linewidth=3, solid_capstyle='round')
            ax.scatter([m[metric]], [yy], s=130, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
            ax.text(min(hi + .03, 1.06), yy, decimal(m[metric]), va='center', fontsize=13, color=INK)
        ax.axvline(base, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(base + .015, -.55, 'azar' if metric == 'roc_auc' else 'tasa base', color=MUTED, fontsize=11.5, va='bottom')
        ax.set_xlim(.3 if metric == 'roc_auc' else 0, 1.12)
        ax.set_ylim(-.7, len(keys) - .4)
        ax.set_yticks(range(len(keys)), [NAMES[k] for k in keys] if i == 0 else [''] * len(keys))
        ax.set_title(label, loc='left', fontsize=16, color=INK, pad=12)
    d = report['diferencias_pareadas']['xgboost_ajustado - xgboost_base']['average_precision']
    fig.text(.24, .1, f"Diferencia pareada de AP (ajustado − base): {d['media']:+.3f} · IC 95 % [{d['ic95'][0]:+.3f}; {d['ic95'][1]:+.3f}]".replace('.', ','),
        fontsize=14, color=INK)
    fig.text(.24, .065, report['decision']['conclusion'], fontsize=13, color=INK2)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def calibration(report, out):
    fig = setup()
    title(fig, 'Calibración de las probabilidades', 'Probabilidad media predicha frente a tasa observada de abandono por tramo (predicción media de 20 repeticiones)')
    ax = fig.add_axes([.08, .14, .5, .64])
    frame(ax)
    ax.grid(axis='y', color=GRID, linewidth=1)
    ax.spines['left'].set_visible(True)
    ax.plot([0, 1], [0, 1], color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, label='Calibración perfecta')
    shown = (('xgboost_base', BLUE, 'XGBoost base (sin calibrar)'), ('xgboost_base_sigmoide', ORANGE, 'Base + calibración sigmoide'))
    for name, color, label in shown:
        rows = report['calibracion'][name]['tabla']
        # Puntos sin unir: tramos con 1-16 casos no definen una curva continua; el tamaño refleja n.
        ax.scatter([r['prob_media'] for r in rows], [r['tasa_observada'] for r in rows], s=[40 + 4 * min(r['n'], 60) for r in rows],
            color=color, alpha=.85, edgecolor=SURFACE, linewidth=2, label=label, zorder=3)
        for r in rows[1:]:
            ax.annotate(f"n={r['n']}", (r['prob_media'], r['tasa_observada']), textcoords='offset points',
                xytext=(-34 if color == ORANGE else 8, 8 if color == ORANGE else -16), fontsize=10.5, color=INK2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: decimal(v, 1) if v % 1 else f'{v:.0f}'))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel('Probabilidad media predicha')
    ax.set_ylabel('Tasa observada de abandono')
    ax.legend(loc='upper left', frameon=False, fontsize=13)
    models, pairs = report['modelos'], report['diferencias_pareadas']
    lines = ['Brier (menor es mejor)']
    for name in ('xgboost_base', 'xgboost_base_sigmoide', 'xgboost_ajustado', 'xgboost_ajustado_sigmoide', 'xgboost_ajustado_isotonica'):
        lines.append(f"  {NAMES[name]}: {decimal(models[name]['brier'], 4)}")
    d = pairs['xgboost_base_sigmoide - xgboost_base']['brier']
    lines += ['', 'Diferencia de Brier (sigmoide − base):', f"  {d['media']:+.4f} · IC 95 % [{d['ic95'][0]:+.4f}; {d['ic95'][1]:+.4f}]".replace('.', ','),
        '', f"Tramo 0-0,05: n={report['calibracion']['xgboost_base']['tabla'][0]['n']} (base) y "
        f"{report['calibracion']['xgboost_base_sigmoide']['tabla'][0]['n']} (sigmoide),",
        f"con {report['calibracion']['xgboost_base']['tabla'][0]['positivos']} y {report['calibracion']['xgboost_base_sigmoide']['tabla'][0]['positivos']} abandonos.",
        '', f"Calibración adoptada: {report['decision']['calibracion_adoptada'] or 'ninguna'}",
        'Tramos con pocos casos: la curva es inestable', 'con solo 11 abandonos.']
    fig.text(.63, .76, '\n'.join(lines), fontsize=13.5, color=INK, va='top', linespacing=1.55)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def thresholds(report, out):
    name = report['modelo_recomendado']
    rows = report['umbrales'][name]
    t = [r['umbral'] for r in rows]
    fig = setup()
    title(fig, 'Efecto del umbral de alerta', f"{NAMES[name]} · promedio de 20 repeticiones fuera de pliegue sobre 790 matrículas (11 abandonos)")
    panels = (('verdaderos_positivos', 'Abandonos detectados (de 11)', BLUE), ('falsos_positivos', 'Falsas alarmas', ORANGE))
    for i, (k, label, color) in enumerate(panels):
        ax = fig.add_axes([.08 + i * .47, .24, .38, .52])
        frame(ax)
        ax.grid(axis='y', color=GRID, linewidth=1)
        ax.grid(axis='x', visible=False)
        ax.bar(t, [r[k] for r in rows], width=.07, color=color, edgecolor=SURFACE, linewidth=2)
        for x, r in zip(t, rows):
            ax.text(x, r[k] + .15, decimal(r[k], 1), ha='center', fontsize=12, color=INK, zorder=4,
                bbox=dict(boxstyle='square,pad=.1', facecolor=SURFACE, edgecolor='none'))
        for mark in (.5, .8):
            ax.axvline(mark, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, zorder=0)
        ax.set_xticks(t, [decimal(v, 1) for v in t])
        ax.set_xlabel('Umbral de probabilidad')
        ax.set_title(label, loc='left', fontsize=16, color=INK, pad=10)
    fig.text(.08, .1, 'Líneas punteadas: umbrales medio (0,5) y alto (0,8) registrados. La recomendación es una propuesta a validar con Dirección.',
        fontsize=13, color=INK2)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def stability(report, out):
    st = report['estabilidad']['por_parametro']
    labels = {'max_depth': 'Profundidad', 'learning_rate': 'Tasa de aprendizaje', 'n_estimators': 'N.º de árboles',
        'min_child_weight': 'min_child_weight', 'subsample': 'subsample = colsample'}
    base = report['base']
    fig = setup()
    title(fig, 'Estabilidad de los parámetros elegidos', f"Proporción de los {report['estabilidad']['pliegues_externos']} pliegues externos que eligió cada valor · en azul, el valor del modelo base")
    for i, (p, dist) in enumerate(st.items()):
        ax = fig.add_axes([.09 + i * .18, .3, .15, .45])
        frame(ax)
        ax.grid(axis='x', visible=False)
        ax.grid(axis='y', color=GRID, linewidth=1)
        values = list(dist)
        colors = [BLUE if float(v) == float(base[p]) else GRAY for v in values]
        ax.bar(range(len(values)), [dist[v] * 100 for v in values], color=colors, width=.6, edgecolor=SURFACE, linewidth=2)
        for x, v in enumerate(values):
            ax.text(x, dist[v] * 100 + 1.5, f"{dist[v] * 100:.0f} %", ha='center', fontsize=12, color=INK)
        ax.set_xticks(range(len(values)), [v.replace('.', ',') for v in values])
        ax.set_ylim(0, 105)
        ax.set_title(labels[p], loc='left', fontsize=14, color=INK, pad=8)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f} %'))
        if i:
            ax.set_yticklabels([])
    top = report['estabilidad']['mas_frecuentes'][0]
    fig.text(.06, .14, f"{report['estabilidad']['configuraciones_distintas']} configuraciones distintas en {report['estabilidad']['pliegues_externos']} pliegues; la más frecuente ({top['config']}) solo en el {top['proporcion'] * 100:.0f} %.\n"
        f"La combinación exacta del modelo base se eligió en el {report['estabilidad']['base_elegida'] * 100:.0f} %: con 11 casos ninguna configuración domina.",
        fontsize=13, color=INK2, linespacing=1.6)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main(directory, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    report = json.loads(Path(directory, 'reporte_ajuste.json').read_text(encoding='utf-8'))
    npz = np.load(Path(directory, 'oof_ajuste.npz'))
    comparison(report, out / '6_ajuste_comparacion.png')
    curves(npz, out / '7_curvas_roc_pr.png')
    calibration(report, out / '8_calibracion.png')
    thresholds(report, out / '9_umbrales.png')
    stability(report, out / '10_estabilidad_parametros.png')
    print('\n'.join(str(p) for p in sorted(out.glob('[6-9]_*.png')) + sorted(out.glob('10_*.png'))))


if __name__ == '__main__':
    main(*sys.argv[1:3])
