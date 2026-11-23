"""Carga los registros completos de la institución (2021-2025) en la base alerta_temprana_v3.

La base v3 es una copia de alerta_temprana_v2 (respaldo previo en Desktop/RESPALDOS_BD). Este script SOLO trabaja
sobre v3 y se niega a correr contra otra base. Reemplaza los datos REALES 2021-2025 de la versión parcial por la
versión completa entregada por la institución:
- borra (en v3) las matrículas REALES 2021-2025 y lo que depende de ellas (notas, cortes y predicciones del modelo
  anterior, alertas, situaciones escolares) y los cursos de esas gestiones;
- inserta cursos, estudiantes (solo código anónimo), matrículas, asignaciones, notas trimestrales por área (T1, T2,
  T3), jornadas de clase, la asistencia día por día y el abandono confirmado. No se registra "no figura en la gestión
  siguiente": 2025 solo tiene 7 de 18 cursos y marcaría como ausentes a estudiantes que sí siguieron.
No toca usuarios, materias, gestiones, periodos, el registro del modelo ni la gestión 2026 (datos simulados).
Sin nombres, RUDE ni fechas de nacimiento.

Uso (desde backend):
    python -m predictivo.cargar_institucion_v3            # simulación: muestra qué se borraría e insertaría
    python -m predictivo.cargar_institucion_v3 --ejecutar # carga en una sola transacción
"""
import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BASE = 'alerta_temprana_v3'
DATOS = Path(__file__).resolve().parents[2] / 'data'
EXCEL = DATOS / 'DATASET_INSTITUCION_2021_2025.xlsx'
ASISTENCIA = DATOS / 'DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv'
AREAS = ['CNAT', 'LCO', 'SOC', 'APV', 'EFI', 'EMU', 'MAT', 'TTG', 'VER']
ESTADO = {'A': 'PRESENTE', 'F': 'FALTA', 'R': 'ATRASO', 'L': 'LICENCIA'}
CIERRE = {1: (4, 30), 2: (8, 31), 3: (11, 30)}
FUENTE = 'Registro pedagógico completo entregado por la institución (22/11/2026)'

# Lo que depende de las matrículas a reemplazar, en orden de borrado.
DEPENDIENTES = [
    ('intervenciones', 'alerta_id IN (SELECT a.id FROM alertas a JOIN predicciones p ON p.id=a.prediccion_id JOIN cortes_predictivos c ON c.id=p.corte_id WHERE c.matricula_id IN ({m}))'),
    ('notificaciones', 'citacion_id IN (SELECT x.id FROM citaciones x WHERE x.matricula_id IN ({m}))'),
    ('alertas', 'prediccion_id IN (SELECT p.id FROM predicciones p JOIN cortes_predictivos c ON c.id=p.corte_id WHERE c.matricula_id IN ({m}))'),
    ('predicciones', 'corte_id IN (SELECT c.id FROM cortes_predictivos c WHERE c.matricula_id IN ({m}))'),
    ('cortes_predictivos', 'matricula_id IN ({m})'),
    ('situaciones_escolares', 'matricula_id IN ({m})'),
    ('asistencias_materia', 'matricula_id IN ({m})'),
    ('asistencias', 'matricula_id IN ({m})'),
    ('calificaciones', 'matricula_id IN ({m})'),
    ('entregas_tareas', 'matricula_id IN ({m})'),
    ('citaciones', 'matricula_id IN ({m})'),
    ('contextos_permanencia', 'matricula_id IN ({m})'),
    ('registros_convivencia', 'matricula_id IN ({m})'),
    ('matriculas', 'id IN ({m})'),
]
DE_CURSOS = ['sesiones_clase', 'jornadas_clase', 'evaluaciones', 'asignaciones_docentes', 'cursos']


def conectar():
    url = make_url(Path(__file__).resolve().parents[1].joinpath('.database-url').read_text().strip()).set(database=BASE)
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar() != BASE:
            raise RuntimeError(f'Este script solo trabaja sobre {BASE}.')
    return engine


def plan(c):
    """Qué se borraría en v3: ids de matrículas REALES 2021-2025 y de sus cursos."""
    mats = [r[0] for r in c.execute(text("SELECT m.id FROM matriculas m JOIN cursos c ON c.id=m.curso_id JOIN gestiones g ON g.id=c.gestion_id "
        "WHERE m.origen='REAL' AND g.anio BETWEEN 2021 AND 2025"))]
    cursos = [r[0] for r in c.execute(text("SELECT c.id FROM cursos c JOIN gestiones g ON g.id=c.gestion_id WHERE g.anio BETWEEN 2021 AND 2025"))]
    otros = c.execute(text("SELECT COUNT(*) FROM matriculas m JOIN cursos c ON c.id=m.curso_id JOIN gestiones g ON g.id=c.gestion_id "
        "WHERE m.origen<>'REAL' AND g.anio BETWEEN 2021 AND 2025")).scalar()
    if otros:
        raise RuntimeError('Hay matrículas no reales en 2021-2025; revisar antes de cargar.')
    return mats, cursos


def lista(ids):
    return ','.join(str(int(i)) for i in ids) or 'NULL'


def conteos_borrado(c, mats, cursos):
    out = {}
    for tabla, cond in DEPENDIENTES:
        out[tabla] = c.execute(text(f'SELECT COUNT(*) FROM {tabla} WHERE ' + cond.format(m=lista(mats)))).scalar()
    for tabla in DE_CURSOS:
        col = 'id' if tabla == 'cursos' else 'curso_id'
        if tabla == 'sesiones_clase':
            out[tabla] = c.execute(text(f'SELECT COUNT(*) FROM sesiones_clase WHERE curso_id IN ({lista(cursos)})')).scalar()
        else:
            out[tabla] = c.execute(text(f'SELECT COUNT(*) FROM {tabla} WHERE {col} IN ({lista(cursos)})')).scalar()
    return out


def preparar():
    ds = pd.read_excel(EXCEL, sheet_name='DATOS_REAL')
    asis = pd.read_csv(ASISTENCIA)
    cursos = sorted({(int(g), int(gr), str(p)) for g, gr, p in zip(ds.gestion, ds.grado, ds.paralelo)})
    curso_de = {(c, int(g)): (int(g), int(gr), str(p)) for c, g, gr, p in zip(ds.codigo_anonimo, ds.gestion, ds.grado, ds.paralelo)}
    dias = defaultdict(set)
    for c, g, f in zip(asis.codigo_anonimo, asis.gestion, asis.fecha):
        dias[curso_de[(c, int(g))]].add(f)
    notas = sum(int(ds[f'{a}_T1'].notna().sum() + ds[f'POST_{a}_T2'].notna().sum() + ds[f'POST_{a}_T3'].notna().sum()) for a in AREAS)
    return ds, asis, cursos, dias, notas


def insertar(c, ds, asis, cursos, dias, resp):
    q = lambda s, **k: c.execute(text(s), k)
    gest = {int(a): int(i) for i, a in q('SELECT id, anio FROM gestiones')}
    periodo = {(int(g), int(n)): int(i) for i, g, n in q('SELECT id, gestion_id, numero FROM periodos')}
    materia = {s: int(i) for i, s in q('SELECT id, sigla FROM materias')}
    faltan = [a for a in AREAS if a not in materia]
    if faltan:
        raise RuntimeError(f'Faltan materias: {faltan}')
    curso_id, asig, evalu, jornada = {}, {}, {}, {}
    for g, gr, p in cursos:
        curso_id[(g, gr, p)] = q('INSERT INTO cursos(gestion_id, grado, paralelo) VALUES (:g, :gr, :p)', g=gest[g], gr=gr, p=p).lastrowid
        for a in AREAS:
            asig[(g, gr, p, a)] = q('INSERT INTO asignaciones_docentes(curso_id, materia_id, docente_id, vigente_desde) VALUES (:c, :m, :d, :v)',
                c=curso_id[(g, gr, p)], m=materia[a], d=resp, v=date(g, 2, 1)).lastrowid
            for n, (mes, dia) in CIERRE.items():
                evalu[(g, gr, p, a, n)] = q("INSERT INTO evaluaciones(asignacion_id, curso_id, gestion_id, periodo_id, titulo, tipo, fecha_aplicacion, puntaje_maximo) "
                    "VALUES (:a, :c, :g, :pe, :t, 'OTRA', :f, 100)", a=asig[(g, gr, p, a)], c=curso_id[(g, gr, p)], g=gest[g],
                    pe=periodo[(gest[g], n)], t=f'Nota del {n}.er trimestre - {a}' if n != 2 else f'Nota del 2.º trimestre - {a}', f=date(g, mes, dia)).lastrowid
        filas = [dict(c=curso_id[(g, gr, p)], f=f) for f in sorted(dias[(g, gr, p)])]
        c.execute(text('INSERT INTO jornadas_clase(curso_id, fecha, es_lectiva) VALUES (:c, :f, TRUE)'), filas)
        for i, f in q('SELECT id, fecha FROM jornadas_clase WHERE curso_id=:c', c=curso_id[(g, gr, p)]):
            jornada[(curso_id[(g, gr, p)], f.isoformat())] = int(i)
    estudiante = {cod: int(i) for i, cod in q('SELECT id, codigo_anonimo FROM estudiantes')}
    nuevos = [cod for cod in sorted(set(ds.codigo_anonimo)) if cod not in estudiante]
    if nuevos:
        c.execute(text("INSERT INTO estudiantes(codigo_anonimo, nombre, apellido) VALUES (:cod, 'ANONIMO', :cod)"), [dict(cod=x) for x in nuevos])
        estudiante = {cod: int(i) for i, cod in q('SELECT id, codigo_anonimo FROM estudiantes')}
    matricula = {}
    for r in ds.itertuples(index=False):
        k = (int(r.gestion), int(r.grado), str(r.paralelo))
        matricula[(r.codigo_anonimo, int(r.gestion))] = (q("INSERT INTO matriculas(estudiante_id, curso_id, fecha_ingreso, origen, registrado_por) "
            "VALUES (:e, :c, :f, 'REAL', :u)", e=estudiante[r.codigo_anonimo], c=curso_id[k], f=date(int(r.gestion), 2, 1), u=resp).lastrowid, curso_id[k], k)
    cal = []
    for r in ds.itertuples(index=False):
        mid, cid, k = matricula[(r.codigo_anonimo, int(r.gestion))]
        for a in AREAS:
            for n, col in ((1, f'{a}_T1'), (2, f'POST_{a}_T2'), (3, f'POST_{a}_T3')):
                v = getattr(r, col)
                if pd.notna(v):
                    cal.append(dict(e=evalu[(*k, a, n)], m=mid, c=cid, p=float(v), u=resp))
    c.execute(text("INSERT INTO calificaciones(evaluacion_id, matricula_id, curso_id, estado, puntaje, registrado_por) VALUES (:e, :m, :c, 'CALIFICADA', :p, :u)"), cal)
    filas = []
    for cod, g, f, e in asis.itertuples(index=False):
        mid, cid, _ = matricula[(cod, int(g))]
        filas.append(dict(m=mid, j=jornada[(cid, f)], c=cid, e=ESTADO[e], u=resp))
    for i in range(0, len(filas), 20000):
        c.execute(text('INSERT INTO asistencias(matricula_id, jornada_id, curso_id, estado, registrado_por) VALUES (:m, :j, :c, :e, :u)'), filas[i:i + 20000])
    ultima = asis[asis.estado.isin(['A', 'R'])].groupby(['codigo_anonimo', 'gestion']).fecha.max()
    sit = []
    for r in ds.itertuples(index=False):
        mid = matricula[(r.codigo_anonimo, int(r.gestion))][0]
        if r.y_abandono_intra_anual == 1:
            u = ultima.get((r.codigo_anonimo, r.gestion))
            sit.append(dict(m=mid, t='ABANDONO_CONFIRMADO', f=u or f'{int(r.gestion)}-02-01', h=f'{int(r.gestion)}-11-30', fu=FUENTE,
                o=f'Dejó de asistir después del {u} (sin asistencia en el 3.er trimestre o notas del T3 en 18). Caída en el {r.trimestre_caida}.', u=resp))
    c.execute(text('INSERT INTO situaciones_escolares(matricula_id, tipo, fecha_efectiva, observado_hasta, fuente_verificacion, observacion, registrado_por) '
        'VALUES (:m, :t, :f, :h, :fu, :o, :u)'), sit)
    return dict(cursos=len(cursos), asignaciones=len(asig), evaluaciones=len(evalu), jornadas=len(jornada), estudiantes_nuevos=len(nuevos),
        matriculas=len(matricula), calificaciones=len(cal), asistencias=len(filas), situaciones=len(sit))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ejecutar', action='store_true')
    a = p.parse_args()
    engine = conectar()
    ds, asis, cursos, dias, notas = preparar()
    with engine.begin() as c:
        mats, cursos_v3 = plan(c)
        borrar = conteos_borrado(c, mats, cursos_v3)
        resp = c.execute(text("SELECT MIN(id) FROM usuarios WHERE rol='Admin'")).scalar()
        print(f'Base: {BASE}')
        print('BORRAR en v3 (versión parcial 2021-2025):', {k: v for k, v in borrar.items() if v})
        print('INSERTAR en v3 (versión completa):', dict(cursos=len(cursos), estudiantes_en_total=ds.codigo_anonimo.nunique(), matriculas=len(ds),
            asignaciones=len(cursos) * len(AREAS), evaluaciones=len(cursos) * len(AREAS) * 3, calificaciones=notas,
            jornadas=sum(len(v) for v in dias.values()), asistencias=len(asis),
            abandonos_confirmados=int(ds.y_abandono_intra_anual.sum())))
        print('Por gestión:', ds.groupby('gestion').agg(matriculas=('codigo_anonimo', 'size'), abandonos=('y_abandono_intra_anual', 'sum')).to_dict('index'))
        print('Muestra (anónima):', ds[['codigo_anonimo', 'gestion', 'grado', 'paralelo', 'promedio_T1', 'POST_promedio_T2']].head(3).to_dict('records'))
        if not a.ejecutar:
            print('Simulación: no se modificó nada. Para cargar: --ejecutar')
            return
        for tabla, cond in DEPENDIENTES:
            c.execute(text(f'DELETE FROM {tabla} WHERE ' + cond.format(m=lista(mats))))
        for tabla in DE_CURSOS:
            c.execute(text(f"DELETE FROM {tabla} WHERE {'id' if tabla == 'cursos' else 'curso_id'} IN ({lista(cursos_v3)})"))
        hecho = insertar(c, ds, asis, cursos, dias, resp)
        huerfanos = c.execute(text('DELETE FROM estudiantes WHERE NOT EXISTS (SELECT 1 FROM matriculas m WHERE m.estudiante_id=estudiantes.id) '
            'AND NOT EXISTS (SELECT 1 FROM estudiante_apoderado x WHERE x.estudiante_id=estudiantes.id)')).rowcount
        print('Insertado:', hecho, '| estudiantes sin matrícula eliminados:', huerfanos)


if __name__ == '__main__':
    main()
