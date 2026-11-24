"""Agrega a alerta_temprana_v3 la nota por dimensión del T1 y el T2 (solo INSERT; no borra ni cambia nada).

Fuente: data/DESGLOSE_INSTITUCION_2021_2025.csv (extraer_desglose.py). Origen no verificado. Los archivos no traen la
fecha de cada actividad: cada nota se registra al cierre del trimestre, igual que la nota trimestral.

Uso (desde backend):
    python -m predictivo.cargar_desglose_v3             # simulación: solo cuenta
    python -m predictivo.cargar_desglose_v3 --ejecutar  # inserta en una sola transacción (requiere OK y respaldo)
"""
import argparse

import pandas as pd
from sqlalchemy import text

from predictivo.cargar_institucion_v3 import BASE, CIERRE, conectar
from predictivo.extraer_desglose import SALIDA


def titulo(t, dim, area):
    return f"Cierre del {'1.er' if t == 1 else '2.º'} trimestre - {dim} - {area}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ejecutar', action='store_true')
    a = p.parse_args()
    df = pd.read_csv(SALIDA)
    with conectar().begin() as c:
        ya = c.execute(text("SELECT COUNT(*) FROM evaluaciones WHERE titulo LIKE 'Cierre del %'")).scalar()
        if ya:
            raise RuntimeError(f'Ya hay {ya} evaluaciones de cierre por dimensión: no se carga dos veces.')
        mats = {(cod, int(g)): (int(m), int(cu)) for cod, g, m, cu in c.execute(text(
            'SELECT e.codigo_anonimo, g.anio, m.id, m.curso_id FROM matriculas m JOIN estudiantes e ON e.id=m.estudiante_id '
            "JOIN cursos c ON c.id=m.curso_id JOIN gestiones g ON g.id=c.gestion_id WHERE m.origen='REAL' AND g.anio BETWEEN 2021 AND 2025"))}
        # La misma asignación que ya tiene la nota trimestral del área.
        asig = {}
        for cu, s, n, aid, g, pe, f in c.execute(text('SELECT ev.curso_id, ma.sigla, p.numero, ev.asignacion_id, ev.gestion_id, ev.periodo_id, ev.fecha_aplicacion '
                'FROM evaluaciones ev JOIN asignaciones_docentes ad ON ad.id=ev.asignacion_id JOIN materias ma ON ma.id=ad.materia_id '
                "JOIN periodos p ON p.id=ev.periodo_id WHERE ev.titulo LIKE 'Nota del %' AND p.numero IN (1,2)")):
            if (cu, s, n) in asig:
                raise RuntimeError(f'Dos notas trimestrales para {(cu, s, n)}.')
            asig[(cu, s, n)] = (aid, g, pe, f)
        df['matricula'] = [mats.get((x, g), (None, None))[0] for x, g in zip(df.codigo_anonimo, df.gestion)]
        df['curso'] = [mats.get((x, g), (None, None))[1] for x, g in zip(df.codigo_anonimo, df.gestion)]
        if df.matricula.isna().any():
            raise RuntimeError('Hay notas sin matrícula en la base.')
        evs = sorted(set(zip(df.curso.astype(int), df.area, df.trimestre, df.dimension, df.maximo)))
        faltan = [e for e in evs if e[:3] not in asig]
        if faltan:
            raise RuntimeError(f'Faltan asignaciones: {faltan[:3]}')
        for cu, s, t, _, _ in evs:
            f = asig[(cu, s, t)][3]
            assert (f.month, f.day) == CIERRE[t], f
        print('Base:', BASE, '| solo INSERT')
        print('evaluaciones a insertar:', len(evs), '| calificaciones a insertar:', len(df), '| matrículas:', df.matricula.nunique())
        print('por gestión:', df.groupby('gestion').size().to_dict())
        print('hoy: evaluaciones', c.execute(text('SELECT COUNT(*) FROM evaluaciones')).scalar(), '| calificaciones', c.execute(text('SELECT COUNT(*) FROM calificaciones')).scalar())
        m1 = df[(df.matricula == df.matricula.iloc[0]) & (df.area == 'MAT') & (df.trimestre == 1)]
        print('ejemplo:', [(titulo(r.trimestre, r.dimension, r.area), f'{r.puntaje:g} de {r.maximo}') for r in m1.itertuples()])
        if not a.ejecutar:
            print('Simulación: no se modificó nada.')
            return
        resp = c.execute(text("SELECT MIN(id) FROM usuarios WHERE rol='Admin'")).scalar()
        ids = {}
        for cu, s, t, dim, mx in evs:
            aid, g, pe, f = asig[(cu, s, t)]
            ids[(cu, s, t, dim)] = c.execute(text('INSERT INTO evaluaciones(asignacion_id, curso_id, gestion_id, periodo_id, titulo, tipo, dimension, fecha_aplicacion, puntaje_maximo) '
                "VALUES (:a, :c, :g, :p, :t, 'OTRA', :d, :f, :m)"), dict(a=aid, c=cu, g=g, p=pe, t=titulo(t, dim, s), d=dim, f=f, m=int(mx))).lastrowid
        filas = [dict(e=ids[(int(r.curso), r.area, r.trimestre, r.dimension)], m=int(r.matricula), c=int(r.curso), p=float(r.puntaje), u=resp) for r in df.itertuples()]
        for i in range(0, len(filas), 20000):
            c.execute(text("INSERT INTO calificaciones(evaluacion_id, matricula_id, curso_id, estado, puntaje, registrado_por) VALUES (:e, :m, :c, 'CALIFICADA', :p, :u)"), filas[i:i + 20000])
        print('Insertado.')


if __name__ == '__main__':
    main()
