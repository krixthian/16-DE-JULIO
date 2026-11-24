"""Desglose SIMULADO por dimensión (T1 y T2) de la gestión 2026, para demostración. Solo INSERT.

Parte de la nota trimestral simulada que ya existe y la reparte con semilla fija, de modo que
Ser + Saber + Hacer + Decidir + Autoevaluación/2 = nota trimestral. Solo matrículas con origen SIMULADO.

Uso (desde backend):
    python -m predictivo.simular_desglose_2026             # cuenta y verifica, no escribe
    python -m predictivo.simular_desglose_2026 --ejecutar  # inserta en una transacción (requiere OK y respaldo)
"""
import argparse
import random
from collections import Counter

from sqlalchemy import text

from predictivo.cargar_desglose_v3 import titulo
from predictivo.cargar_institucion_v3 import BASE, conectar
from predictivo.desglose import DIMENSIONES

ANIO, SEED = 2026, 1607


def repartir(nota, rng):
    """Puntajes enteros por dimensión cuya suma (con media autoevaluación) da la nota trimestral entera."""
    f = nota / 100
    for _ in range(500):
        ser, dec = (min(5, max(0, round(5 * f + rng.gauss(0, .5)))) for _ in range(2))
        auto = 2 * min(5, max(0, round(5 * f + rng.gauss(0, .5))))
        hacer = min(40, max(0, round(40 * f + rng.gauss(0, 1.5))))
        saber = round(nota) - ser - dec - hacer - auto // 2
        if 0 <= saber <= 45 and abs(saber / 45 - f) < .15:
            return {'Ser': ser, 'Saber': saber, 'Hacer': hacer, 'Decidir': dec, 'Autoevaluación': auto}
    raise ValueError(f'No se pudo repartir la nota {nota}.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ejecutar', action='store_true')
    a = p.parse_args()
    rng = random.Random(SEED)
    with conectar().begin() as c:
        if c.execute(text("SELECT COUNT(*) FROM evaluaciones e JOIN gestiones g ON g.id=e.gestion_id WHERE g.anio=:a AND e.titulo LIKE 'Cierre del %'"), dict(a=ANIO)).scalar():
            raise RuntimeError('2026 ya tiene desglose: no se carga dos veces.')
        filas = c.execute(text('SELECT k.matricula_id, m.origen, k.estado, k.puntaje, ev.asignacion_id, ev.curso_id, ev.gestion_id, ev.periodo_id, ev.fecha_aplicacion, '
            'ev.puntaje_maximo, p.numero, ma.sigla, m.fecha_ingreso FROM calificaciones k JOIN evaluaciones ev ON ev.id=k.evaluacion_id JOIN periodos p ON p.id=ev.periodo_id '
            'JOIN gestiones g ON g.id=ev.gestion_id JOIN matriculas m ON m.id=k.matricula_id JOIN asignaciones_docentes ad ON ad.id=ev.asignacion_id '
            "JOIN materias ma ON ma.id=ad.materia_id WHERE g.anio=:a AND p.numero IN (1,2) AND ev.titulo LIKE 'Nota del %' ORDER BY k.matricula_id, p.numero, ma.sigla"), dict(a=ANIO)).mappings().all()
        assert filas and all(r['origen'] == 'SIMULADO' and float(r['puntaje_maximo']) == 100 for r in filas)
        evs, notas, omitidas = {}, [], Counter()
        for r in filas:
            if r['estado'] != 'CALIFICADA':
                omitidas[r['estado']] += 1
                continue
            partes = repartir(float(r['puntaje']), rng)
            assert sum(partes.values()) - partes['Autoevaluación'] / 2 == round(float(r['puntaje']))
            for dim, v in partes.items():
                k = (r['asignacion_id'], r['periodo_id'], dim)
                assert 0 <= v <= DIMENSIONES[dim]
                evs[k] = (r, dim)
                notas.append((k, r['matricula_id'], r['curso_id'], v))
        print('Base:', BASE, '| gestión', ANIO, '| SIMULADO | solo INSERT')
        print('evaluaciones a insertar:', len(evs), '| calificaciones a insertar:', len(notas), '| matrículas:', len({n[1] for n in notas}), '| sin nota de origen (omitidas):', dict(omitidas))
        print('fechas:', sorted({str(r['fecha_aplicacion']) for r, _ in evs.values()}))
        x = next(r for r in filas if r['sigla'] == 'MAT' and r['estado'] == 'CALIFICADA')
        print('ejemplo MAT T1, nota', float(x['puntaje']), [(k[2], v) for k, m, _, v in notas if m == x['matricula_id'] and k[:2] == (x['asignacion_id'], x['periodo_id'])])
        for d, mx in DIMENSIONES.items():
            v = [n[3] for n in notas if n[0][2] == d]
            print(f'  {d}: min {min(v)} media {sum(v) / len(v):.1f} max {max(v)} de {mx}')
        if not a.ejecutar:
            print('Simulación: no se modificó nada.')
            return
        resp = c.execute(text("SELECT MIN(id) FROM usuarios WHERE rol='Admin'")).scalar()
        ids = {k: c.execute(text('INSERT INTO evaluaciones(asignacion_id, curso_id, gestion_id, periodo_id, titulo, tipo, dimension, fecha_aplicacion, puntaje_maximo) '
            "VALUES (:a, :c, :g, :p, :t, 'OTRA', :d, :f, :m)"), dict(a=r['asignacion_id'], c=r['curso_id'], g=r['gestion_id'], p=r['periodo_id'],
                t=titulo(r['numero'], d, r['sigla']), d=d, f=r['fecha_aplicacion'], m=DIMENSIONES[d])).lastrowid for k, (r, d) in evs.items()}
        c.execute(text("INSERT INTO calificaciones(evaluacion_id, matricula_id, curso_id, estado, puntaje, registrado_por) VALUES (:e, :m, :c, 'CALIFICADA', :p, :u)"),
            [dict(e=ids[k], m=m, c=cu, p=v, u=resp) for k, m, cu, v in notas])
        print('Insertado.')


if __name__ == '__main__':
    main()
