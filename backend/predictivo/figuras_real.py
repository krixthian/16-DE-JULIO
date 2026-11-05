"""Figuras para diapositivas a partir de reporte.json y sensibilidad.json (solo cifras agregadas).

Uso desde backend: python -m predictivo.figuras_real artifacts/real_t1_v1 ../docs/figuras
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

SURFACE, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
XGB, LOGIT, BASE = '#2a78d6', '#eb6834', '#b8b6ae'
NAMES = {'xgboost': 'XGBoost', 'regresion_logistica': 'Regresión logística', 'regla_promedio_T1': 'Regla promedio T1',
    'regla_faltas_T1': 'Regla faltas T1', 'regla_n_areas_bajo_51': 'Regla n.º áreas < 51', 'siempre_continuidad': 'Siempre continuidad'}
ORDER = ['xgboost', 'regresion_logistica', 'regla_promedio_T1', 'regla_faltas_T1', 'regla_n_areas_bajo_51']
COLOR = {'xgboost': XGB, 'regresion_logistica': LOGIT}
SOURCE = 'Fuente: dataset real U.E. 16 de Julio 2021-2025 (790 matrículas, 11 abandonos). Validación 5 pliegues por estudiante × 20 repeticiones.'


def decimal(v, n=2):
    return f'{v:.{n}f}'.replace('.', ',')


def setup(figsize=(13.33, 7.5)):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 15, 'text.color': INK, 'axes.labelcolor': INK2,
        'xtick.color': INK2, 'ytick.color': INK, 'axes.edgecolor': AXIS})
    fig = plt.figure(figsize=figsize, facecolor=SURFACE)
    return fig


def frame(ax):
    ax.set_facecolor(SURFACE)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.grid(axis='x', color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: decimal(v, 1) if v % 1 else f'{v:.0f}'))


def title(fig, text, subtitle):
    fig.text(.04, .94, text, fontsize=26, fontweight='bold', color=INK, va='top')
    fig.text(.04, .875, subtitle, fontsize=15, color=INK2, va='top')
    fig.text(.04, .03, SOURCE, fontsize=11, color=MUTED)


def table(models, out):
    fig = setup()
    title(fig, 'Métricas del modelo frente a los baselines', 'Abandono dentro de la gestión, predicho al cierre del 1.er trimestre (umbral 0,5)')
    ax = fig.add_axes([.04, .1, .92, .72])
    ax.axis('off')
    head = ['Modelo', 'ROC-AUC [IC 95 %]', 'AP [IC 95 %]', 'Sensibilidad', 'Precisión', 'F1', '% marcados']
    rows = []
    for key in ORDER + ['siempre_continuidad']:
        m = models[key]
        ic = m.get('ic95', {})
        ci = lambda k: f" [{decimal(ic[k][0])}-{decimal(ic[k][1])}]" if k in ic else ''
        rows.append([NAMES[key], decimal(m['roc_auc'], 3) + ci('roc_auc'), decimal(m['average_precision'], 3) + ci('average_precision'),
            decimal(m['sensibilidad']), decimal(m['precision']), decimal(m['f1']), decimal(m['tasa_marcados'] * 100, 1) + ' %'])
    t = ax.table(cellText=rows, colLabels=head, loc='upper center', cellLoc='center', colLoc='center',
        colWidths=[.2, .19, .19, .11, .1, .08, .11])
    t.auto_set_font_size(False)
    t.set_fontsize(14)
    t.scale(1, 2.6)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_facecolor(SURFACE)
        if r == 0:
            cell.set_text_props(color=INK2, fontweight='bold')
            cell.set_facecolor('#f1f0ec')
        elif r == 1:
            cell.set_facecolor('#e9f1fb')
            cell.set_text_props(fontweight='bold')
        if c == 0 and r > 0:
            cell.set_text_props(ha='left')
            cell.PAD = .04
    fig.text(.05, .33, 'AP = average precision (área bajo la curva precisión-sensibilidad). Tasa base de abandono: 1,4 %.\n'
        'XGBoost y la regresión logística no difieren de forma significativa: sus intervalos se solapan.', fontsize=13.5, color=INK2, linespacing=1.6)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def intervals(models, out):
    fig = setup()
    title(fig, 'Discriminación con intervalos de confianza al 95 %', 'Punto = media de 20 repeticiones · barra = IC bootstrap por estudiante')
    keys = ORDER[::-1]
    for i, (metric, label, base) in enumerate((('roc_auc', 'ROC-AUC', .5), ('average_precision', 'Average precision (AP)', models['siempre_continuidad']['average_precision']))):
        ax = fig.add_axes([.24 + i * .385, .14, .33, .6])
        frame(ax)
        for y, key in enumerate(keys):
            m, color = models[key], COLOR.get(key, BASE)
            lo, hi = m['ic95'][metric]
            ax.plot([lo, hi], [y, y], color=color, linewidth=3, solid_capstyle='round')
            ax.scatter([m[metric]], [y], s=130, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
            ax.text(min(hi + .03, 1.06), y, decimal(m[metric], 2), va='center', fontsize=13, color=INK)
        ax.axvline(base, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(base + .015, -.55, 'azar' if metric == 'roc_auc' else 'tasa base', color=MUTED, fontsize=11.5, ha='left', va='bottom')
        ax.set_xlim(0 if metric != 'roc_auc' else .3, 1.12)
        ax.set_ylim(-.7, len(keys) - .4)
        ax.set_yticks(range(len(keys)), [NAMES[k] for k in keys] if i == 0 else [''] * len(keys))
        ax.set_title(label, loc='left', fontsize=16, color=INK, pad=12)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def temporal(models, sens, out):
    fig = setup()
    title(fig, 'Validación cruzada frente a una gestión nueva', 'XGBoost · entrenado con 2021-2023 y evaluado en 2024 (320 matrículas, 2 abandonos, sin estudiantes compartidos)')
    ax = fig.add_axes([.24, .2, .68, .56])
    frame(ax)
    cv, tmp = models['xgboost'], sens['temporal_2021_2023_a_2024']['xgboost']
    metrics = [('roc_auc', 'ROC-AUC'), ('average_precision', 'Average precision'), ('sensibilidad', 'Sensibilidad'), ('precision', 'Precisión')]
    for y, (key, label) in enumerate(metrics[::-1]):
        a, b = cv[key], tmp[key]
        ax.plot([a, b], [y, y], color=GRID, linewidth=4, solid_capstyle='round', zorder=1)
        ax.scatter([a], [y], s=150, color=XGB, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter([b], [y], s=150, color=LOGIT, edgecolor=SURFACE, linewidth=2, zorder=3)
        for v, dy in ((a, .22), (b, -.3)):
            ax.text(v, y + dy, decimal(v), ha='center', fontsize=13, color=INK)
    ax.set_yticks(range(len(metrics)), [l for _, l in metrics[::-1]])
    ax.set_xlim(-.02, 1.05)
    ax.set_ylim(-.7, len(metrics) - .3)
    ax.scatter([], [], s=120, color=XGB, label='Validación cruzada agrupada (2021-2025)')
    ax.scatter([], [], s=120, color=LOGIT, label='Temporal 2021-2023 → 2024')
    ax.legend(loc='lower left', bbox_to_anchor=(-.02, 1.02), ncol=2, frameon=False, fontsize=13.5)
    fig.text(.24, .085, f"En 2024 detecta los 2 abandonos con {tmp['falsos_positivos']} falsas alarmas: el ranking se mantiene, la precisión cae.",
        fontsize=13, color=INK2)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def importance(report, out, top=10):
    fig = setup()
    title(fig, 'Variables con mayor peso en el modelo', 'Ganancia relativa de XGBoost (modelo final, 790 matrículas) · solo información disponible al cierre de T1')
    gain = sorted(report['importancia_ganancia'].items(), key=lambda kv: kv[1], reverse=True)[:top]
    total = sum(report['importancia_ganancia'].values())
    ax = fig.add_axes([.24, .17, .68, .65])
    frame(ax)
    names = [k for k, _ in gain][::-1]
    values = [v / total * 100 for _, v in gain][::-1]
    ax.barh(names, values, height=.62, color=XGB, edgecolor=SURFACE, linewidth=2)
    for y, v in enumerate(values):
        ax.text(v + .6, y, decimal(v, 1) + ' %', va='center', fontsize=13, color=INK)
    ax.set_xlim(0, max(values) * 1.15)
    ax.set_xlabel('% de la ganancia total', color=INK2)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def confusion(models, rows, out):
    fig = setup()
    m = models['xgboost']
    tp, fp = m['verdaderos_positivos'], m['falsos_positivos']
    pos = 11
    fn, tn = pos - tp, rows - pos - fp
    title(fig, 'Matriz de confusión de XGBoost', 'Promedio de 20 repeticiones de validación cruzada · umbral 0,5 · 790 matrículas')
    ax = fig.add_axes([.3, .1, .42, .64])
    cells = [[(tn, 'Verdaderos negativos', '#f1f0ec', INK), (fp, 'Falsas alarmas', '#fde5dc', INK)],
             [(fn, 'Abandonos no detectados', '#fde5dc', INK), (tp, 'Abandonos detectados', XGB, '#ffffff')]]
    for r in range(2):
        for c in range(2):
            v, label, bg, ink = cells[r][c]
            ax.add_patch(plt.Rectangle((c, 1 - r), .98, .98, color=bg))
            ax.text(c + .49, 1 - r + .56, decimal(v, 1), ha='center', va='center', fontsize=30, fontweight='bold', color=ink)
            ax.text(c + .49, 1 - r + .3, label, ha='center', va='center', fontsize=13, color=ink)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.axis('off')
    for c, label in enumerate(('Predicho: continúa', 'Predicho: abandono')):
        fig.text(.3 + .42 * (c * .5 + .245), .765, label, ha='center', fontsize=14, color=INK2)
    for r, label in enumerate(('Real: continúa', 'Real: abandono')):
        fig.text(.285, .1 + .64 * (.75 - r * .5), label, ha='right', va='center', fontsize=14, color=INK2)
    fig.text(.74, .42, f"Sensibilidad {decimal(m['sensibilidad'])}\nPrecisión {decimal(m['precision'])}\nMarca el {decimal(m['tasa_marcados'] * 100, 1)} %\nde las matrículas",
        fontsize=15, color=INK, va='center', linespacing=1.6)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main(directory, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    report = json.loads(Path(directory, 'reporte.json').read_text(encoding='utf-8'))
    sens = json.loads(Path(directory, 'sensibilidad.json').read_text(encoding='utf-8'))
    ev = report['evaluacion']['abandono']
    models = ev['modelos']
    table(models, out / '1_tabla_metricas.png')
    intervals(models, out / '2_auc_ap_intervalos.png')
    temporal(models, sens, out / '3_validacion_temporal.png')
    importance(report, out / '4_importancia_variables.png')
    confusion(models, ev['filas'], out / '5_matriz_confusion.png')
    print('\n'.join(str(p) for p in sorted(out.glob('*.png'))))


if __name__ == '__main__':
    main(*sys.argv[1:3])
