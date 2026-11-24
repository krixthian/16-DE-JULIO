"""Actividades de cada dimensión (T1 y T2) en alerta_temprana_v3. Solo INSERT; dos fuentes separadas:

- `archivos` (2021-2025): las de los archivos recibidos (origen no verificado). No traen fecha: se registran al cierre del
  trimestre con el título "Actividad del ..." y no cuentan como actividades fechadas. Sin título -> "Actividad N de <dimensión>".
- `simuladas` (2026, matrículas SIMULADO): mismos títulos, con fecha en un día de clase del trimestre (semilla fija). Su
  promedio redondeado da la nota simulada de la dimensión; si ese día el estudiante faltó, queda "no presentada".

Uso (desde backend):
    python -m predictivo.cargar_actividades_v3 archivos|simuladas              # cuenta y verifica, no escribe
    python -m predictivo.cargar_actividades_v3 archivos|simuladas --ejecutar   # una transacción (requiere OK y respaldo)
"""
import argparse
import math
import random
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from predictivo import dataset_institucion as di, registros_pedagogicos as rp
from predictivo.cargar_institucion_v3 import BASE, conectar
from predictivo.desglose import DIMENSIONES
from predictivo.extraer_desglose import DATOS

DOCS = [Path('C:/Users/Cristhian/Documents/DATOS_COMPLETOS'), Path('C:/Users/Cristhian/Documents/DATOS')]
SEED = 1607
TRIM = {1: '1.er', 2: '2.º'}


def leer(ruta):
    """Curso, órdenes y columnas [(área, trimestre, dimensión, n, título, {orden: nota})]. Comprueba el promedio."""
    import openpyxl
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    g, gr, p = rp.curso(wb)
    ordenes, centra, cols = sorted(di.nombres(wb)), di.centralizador(wb), []
    for a in rp.AREAS:
        for t in (1, 2):
            f = list(wb[f'{a} {t}'].iter_rows(values_only=True))
            fd = next(i for i, x in enumerate(f) if any(rp._txt(v).upper().startswith('SABER') for v in x))
            dim = lambda v: rp._txt(v).upper().split('/')[0].strip()
            ini = sorted((j, dim(v)) for j, v in enumerate(f[fd]) if dim(v) in rp.DIMENSIONES)
            tot = next(j for j, v in enumerate(f[fd]) if rp._txt(v).upper() == 'TOTAL')
            est = dict(rp._filas_estudiantes(f, rp._encabezado(f, 'N°')))
            for (i, d), fin in zip(ini, [j for j, _ in ini[1:]] + [tot]):
                pr = next(j for j in range(i, fin) if rp._txt(f[fd + 1][j]).upper() == 'PROMEDIO')
                cs = [j for j in range(i, pr) if any(rp._num(e[j]) is not None for e in est.values())]
                for o in ordenes:
                    v = [x for x in (rp._num(est[o][j]) for j in cs) if x is not None]
                    assert all(0 <= x <= DIMENSIONES[d.capitalize()] for x in v)
                    assert abs(sum(v) / len(v) - rp._num(est[o][pr])) <= .5001, (ruta.name[:24], a, t, d)
                for n, j in enumerate(cs, 1):
                    titulo = ' '.join(rp._txt(f[fd + 1][j]).split()).capitalize() or f'Actividad {n} de {d.capitalize()}'
                    cols.append((a, t, d.capitalize(), n, titulo[:110], {o: rp._num(est[o][j]) for o in ordenes if rp._num(est[o][j]) is not None}))
    wb.close()
    return dict(curso=(g, gr, str(p)), ordenes=ordenes, cols=cols, t1={o: [centra.get(o, {}).get(a, (None,))[0] for a in rp.AREAS] for o in ordenes})


def registros():
    rutas = [r for c in DOCS for r in sorted(c.rglob('REGISTRO_PEDAGOGICO_*.xlsx'))]
    with ProcessPoolExecutor(8) as ex:
        return sorted(ex.map(leer, rutas), key=lambda r: r['curso'])


def destinos(c, desde, hasta):
    """{(gestión, grado, paralelo, área, trimestre): (asignación, curso, gestión_id, periodo, cierre)}"""
    return {(g, gr, p, s, n): (a, cu, gi, pe, f) for g, gr, p, s, n, a, cu, gi, pe, f in c.execute(text(
        'SELECT g.anio, cu.grado, cu.paralelo, ma.sigla, p.numero, ev.asignacion_id, ev.curso_id, ev.gestion_id, ev.periodo_id, ev.fecha_aplicacion '
        'FROM evaluaciones ev JOIN cursos cu ON cu.id=ev.curso_id JOIN gestiones g ON g.id=ev.gestion_id JOIN asignaciones_docentes ad ON ad.id=ev.asignacion_id '
        "JOIN materias ma ON ma.id=ad.materia_id JOIN periodos p ON p.id=ev.periodo_id WHERE ev.titulo LIKE 'Nota del %' AND p.numero IN (1,2) AND g.anio BETWEEN :a AND :b"),
        dict(a=desde, b=hasta))}


def de_archivos(c):
    ds = pd.read_excel(DATOS / 'DATASET_INSTITUCION_2021_2025.xlsx', sheet_name='DATOS_REAL')
    mats = {(cod, int(g)): int(m) for cod, g, m in c.execute(text('SELECT e.codigo_anonimo, g.anio, m.id FROM matriculas m JOIN estudiantes e ON e.id=m.estudiante_id '
        "JOIN cursos cu ON cu.id=m.curso_id JOIN gestiones g ON g.id=cu.gestion_id WHERE m.origen='REAL' AND g.anio BETWEEN 2021 AND 2025"))}
    dest, evs, i = destinos(c, 2021, 2025), [], 0
    for r in registros():
        mat = {}
        for o in r['ordenes']:
            f = ds.iloc[i]
            i += 1
            assert (int(f.gestion), int(f.grado), str(f.paralelo)) == r['curso']
            assert all(v is None or float(f[f'{a}_T1']) == v for a, v in zip(rp.AREAS, r['t1'][o]))
            mat[o] = mats[(f.codigo_anonimo, int(f.gestion))]
        for a, t, d, n, titulo, notas in r['cols']:
            asig, cu, gi, pe, cierre = dest[(*r['curso'], a, t)]
            evs.append(dict(a=asig, c=cu, g=gi, p=pe, t=f'Actividad del {TRIM[t]} trimestre - {d} - {titulo}', tipo='OTRA', d=d, f=cierre, m=DIMENSIONES[d],
                notas=[(mat[o], 'CALIFICADA', v) for o, v in notas.items()]))
    assert i == len(ds)
    return evs


def tipo_de(d, titulo):
    if d == 'Saber' and any(k in titulo.upper() for k in ('EVALUACION', 'PRUEBA')):
        return 'PRUEBA'
    return 'TRABAJO' if d in ('Saber', 'Hacer') else 'OTRA'


def repartir(nota, n, maximo, rng):
    """n enteros entre 0 y el máximo cuyo promedio, redondeado (mitad hacia arriba), es `nota`."""
    v = [min(maximo, max(0, round(rng.gauss(nota, maximo * .09)))) for _ in range(n)]
    while (dif := round(nota * n) - sum(v)) != 0:
        j = rng.randrange(n)
        if 0 <= v[j] + (1 if dif > 0 else -1) <= maximo:
            v[j] += 1 if dif > 0 else -1
    assert math.floor(sum(v) / n + .5) == nota
    return v


def simuladas(c):
    rng = random.Random(SEED)
    plantilla = defaultdict(list)  # títulos de un curso de los archivos, los mismos para cada grado
    for a, t, d, n, titulo, _ in next(r for r in registros() if r['curso'] == (2023, 3, 'A'))['cols']:
        plantilla[(a, t, d)].append(titulo)
    dias = defaultdict(list)
    for cu, f in c.execute(text('SELECT j.curso_id, j.fecha FROM jornadas_clase j JOIN cursos cu ON cu.id=j.curso_id JOIN gestiones g ON g.id=cu.gestion_id '
            'WHERE g.anio=2026 AND j.es_lectiva ORDER BY j.fecha')):
        dias[cu].append(f)
    falta = {(m, f) for m, f in c.execute(text("SELECT a.matricula_id, j.fecha FROM asistencias a JOIN jornadas_clase j ON j.id=a.jornada_id JOIN cursos cu ON cu.id=j.curso_id "
        "JOIN gestiones g ON g.id=cu.gestion_id WHERE g.anio=2026 AND a.estado IN ('FALTA','LICENCIA')"))}
    vig = {a: (x, y) for a, x, y in c.execute(text('SELECT id, vigente_desde, vigente_hasta FROM asignaciones_docentes'))}
    per = {p: (x, y) for p, x, y in c.execute(text('SELECT id, fecha_inicio, fecha_fin FROM periodos'))}
    cierres = defaultdict(dict)
    for a, p, d, m, v, o in c.execute(text('SELECT ev.asignacion_id, ev.periodo_id, ev.dimension, k.matricula_id, k.puntaje, mt.origen FROM calificaciones k '
            'JOIN evaluaciones ev ON ev.id=k.evaluacion_id JOIN gestiones g ON g.id=ev.gestion_id JOIN matriculas mt ON mt.id=k.matricula_id '
            "WHERE g.anio=2026 AND ev.titulo LIKE 'Cierre del %' AND k.estado='CALIFICADA' ORDER BY k.matricula_id")):
        assert o == 'SIMULADO'
        cierres[(a, p, d)][m] = int(v)
    ingreso = dict(c.execute(text('SELECT id, fecha_ingreso FROM matriculas')).all())
    evs = []
    for (g, gr, par, area, t), (asig, cu, gi, pe, cierre) in sorted(destinos(c, 2026, 2026).items()):
        ini, fin = per[pe][0] or cierre.replace(month=2 if t == 1 else 5, day=1), per[pe][1] or cierre
        posibles = [f for f in dias[cu] if max(ini, vig[asig][0]) <= f <= min(fin, cierre, vig[asig][1] or fin)]
        for d in ('Ser', 'Saber', 'Hacer', 'Decidir'):
            tit = plantilla[(area, t, d)]
            fechas = sorted(rng.sample(posibles, len(tit)))
            # La evaluación trimestral cierra el trimestre; el resto, en el orden del registro.
            hoja = [dict(a=asig, c=cu, g=gi, p=pe, t=x, tipo=tipo_de(d, x), d=d, f=f, m=DIMENSIONES[d], notas=[]) for x, f in zip(tit, fechas)]
            for mat, nota in cierres[(asig, pe, d)].items():
                vino = [e for e in hoja if e['f'] >= ingreso[mat] and (mat, e['f']) not in falta]
                for e in hoja:
                    if e['f'] >= ingreso[mat] and (mat, e['f']) in falta:
                        e['notas'].append((mat, 'NO_PRESENTADA', None))
                if vino:
                    for e, v in zip(vino, repartir(nota, len(vino), DIMENSIONES[d], rng)):
                        e['notas'].append((mat, 'CALIFICADA', v))
            evs += hoja
    return evs


def main():
    p = argparse.ArgumentParser()
    p.add_argument('fuente', choices=['archivos', 'simuladas'])
    p.add_argument('--ejecutar', action='store_true')
    a = p.parse_args()
    with conectar().begin() as c:
        rango = dict(x=2026, y=2026) if a.fuente == 'simuladas' else dict(x=2021, y=2025)
        if c.execute(text("SELECT COUNT(*) FROM evaluaciones e JOIN gestiones g ON g.id=e.gestion_id WHERE g.anio BETWEEN :x AND :y AND e.dimension IS NOT NULL "
                "AND e.titulo NOT LIKE 'Cierre del %'"), rango).scalar():
            raise RuntimeError('Ya hay actividades por dimensión en esas gestiones: no se carga dos veces.')
        evs = de_archivos(c) if a.fuente == 'archivos' else simuladas(c)
        n = sum(len(e['notas']) for e in evs)
        print('Base:', BASE, '|', a.fuente, '| solo INSERT')
        print('actividades a insertar:', len(evs), '| notas a insertar:', n, '| estados:', dict(Counter(s for e in evs for _, s, _ in e['notas'])))
        print('por dimensión:', dict(Counter(e['d'] for e in evs)), '| tipos:', dict(Counter(e['tipo'] for e in evs)))
        print('sin título en el archivo:', sum(' - Actividad ' in e['t'] for e in evs), '| fechas:', len({e['f'] for e in evs}), 'de', min(e['f'] for e in evs), 'a', max(e['f'] for e in evs))
        mat = evs[0]['notas'][0][0]
        for e in [e for e in evs if e['a'] == evs[0]['a'] and e['p'] == evs[0]['p']][:6]:
            print('  ', e['f'], e['d'], '|', e['t'][:75], '|', next(((s, v) for m, s, v in e['notas'] if m == mat), None), 'de', e['m'])
        if not a.ejecutar:
            print('Simulación: no se modificó nada.')
            return
        resp = c.execute(text("SELECT MIN(id) FROM usuarios WHERE rol='Admin'")).scalar()
        filas = []
        for e in evs:
            i = c.execute(text('INSERT INTO evaluaciones(asignacion_id, curso_id, gestion_id, periodo_id, titulo, tipo, dimension, fecha_aplicacion, puntaje_maximo) '
                'VALUES (:a, :c, :g, :p, :t, :tipo, :d, :f, :m)'), {k: v for k, v in e.items() if k != 'notas'}).lastrowid
            filas += [dict(e=i, m=m, c=e['c'], s=s, p=v, u=resp) for m, s, v in e['notas']]
        for i in range(0, len(filas), 20000):
            c.execute(text('INSERT INTO calificaciones(evaluacion_id, matricula_id, curso_id, estado, puntaje, registrado_por) VALUES (:e, :m, :c, :s, :p, :u)'), filas[i:i + 20000])
        print('Insertado.')


if __name__ == '__main__':
    main()
