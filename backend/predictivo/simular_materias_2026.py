"""Simula la asistencia por materia (por hora) y citaciones de la gestión 2026 en alerta_temprana_v3, para demostrar el sistema.

Solo AGREGA filas a la gestión 2026, cuyas 150 matrículas ya son de origen SIMULADO. No toca 2021-2025 ni la asistencia diaria.
- Agosto a octubre, 6 horas por día de clase, 30 por semana repartidas en las 9 materias.
- Coherente con la asistencia diaria que ya existe: PRESENTE todo el día, ATRASO solo en la 1.ª hora, FALTA y LICENCIA todo el día.
- Escenarios explícitos sobre estudiantes que hoy están en VERDE y faltan poco:
    * 3 faltan a UNA materia (Religión, Educación Física y Matemática) y asisten al resto;
    * 1 falta a 3 materias;
    * 2 llegan y se retiran con licencia (4 y 2 días): licencia parcial, sin efecto en la alerta;
    * 1 con 5 citaciones de una materia y 2 de Dirección; 1 con 4 citaciones repartidas en 4 materias (no alerta).
  Los citados reciben un apoderado de prueba (sin datos personales), porque la citación lo exige.
Reproducible (semilla 2026).

Uso (desde backend):
    python -m predictivo.simular_materias_2026            # muestra qué se insertaría
    python -m predictivo.simular_materias_2026 --ejecutar
"""
import argparse
import random
from collections import Counter, defaultdict
from datetime import date, datetime

from sqlalchemy import text

from predictivo.cargar_institucion_v3 import conectar

INICIO, FIN = date(2026, 8, 1), date(2026, 10, 30)
SEMANA = {'Comunicación y Lenguajes': 6, 'Matematicas': 6, 'Ciencias Naturales': 4, 'Ciencias Sociales': 4, 'Educación Física y Deportes': 2,
    'Educación Musical': 2, 'Artes Plásticas y Visuales': 2, 'Técnica Tecnológica General': 2, 'Valores, Espiritualidad y Religiones': 2}
REL, EFI, MAT = 'Valores, Espiritualidad y Religiones', 'Educación Física y Deportes', 'Matematicas'
UNA = {0: (REL, .40), 1: (EFI, .45), 2: (MAT, .30)}  # escenario: materia y proporción de faltas
VARIAS = (3, ('Educación Musical', 'Artes Plásticas y Visuales', 'Técnica Tecnológica General'), .40)
PARCIAL = {4: 4, 5: 2}


def preparar(c):
    q = lambda s, **k: c.execute(text(s), k).all()
    rng = random.Random(2026)
    materia = {n: i for i, n in q('select id, nombre from materias')}
    cursos = [x[0] for x in q('select c.id from cursos c join gestiones g on g.id=c.gestion_id where g.anio=2026 order by c.grado, c.paralelo')]
    mats = q("select m.id, m.curso_id, e.codigo_anonimo from matriculas m join estudiantes e on e.id=m.estudiante_id join cursos c on c.id=m.curso_id "
        "join gestiones g on g.id=c.gestion_id where g.anio=2026 and m.origen='SIMULADO' order by m.id")
    jornadas = q("select j.id, j.curso_id, j.fecha from jornadas_clase j join cursos c on c.id=j.curso_id join gestiones g on g.id=c.gestion_id "
        "where g.anio=2026 and j.es_lectiva=1 and j.fecha between :a and :b order by j.fecha, j.curso_id", a=INICIO, b=FIN)
    if c.execute(text('select count(*) from sesiones_clase')).scalar() or c.execute(text('select count(*) from citaciones')).scalar():
        raise SystemExit('Ya hay sesiones o citaciones: no se agrega nada.')
    diario = {(m, j): e for m, j, e in q("select a.matricula_id, a.jornada_id, a.estado from asistencias a join matriculas m on m.id=a.matricula_id where m.origen='SIMULADO'")}
    horario = {}
    for cid in cursos:  # reparte sin más de 2 horas de la misma materia al día
        while True:
            bolsa = [n for n, k in SEMANA.items() for _ in range(k)]
            rng.shuffle(bolsa)
            dias = [sorted(bolsa[i * 6:i * 6 + 6]) for i in range(5)]
            if all(max(Counter(d).values()) <= 2 for d in dias):
                break
        for w, d in enumerate(dias):
            horario[cid, w] = d
    sesiones = [(j, cid, materia[n], p) for j, cid, f in jornadas for p, n in enumerate(horario[cid, f.weekday()], 1)]
    # escenarios: estudiantes hoy en VERDE y con pocas faltas, uno por curso cuando se puede
    from sqlalchemy.orm import Session
    from predictivo import seguimiento as sg
    with Session(c.engine) as db:
        alertas = {a['matricula_id']: a for a in sg.calcular(db, 2026, date(2026, 11, 22))['alertas']}
    candidatos = defaultdict(list)
    for mid, cid, cod in mats:
        a = alertas[mid]
        if a['perfil']['nivel'] == 'VERDE' and a['indicadores']['prop_faltas'] <= .02:
            candidatos[cid].append((mid, cid, cod))
    elegidos = []
    for k in range(8):
        lista = candidatos[cursos[k % len(cursos)]]
        elegidos.append(lista.pop(rng.randrange(len(lista))))
    esc = {}
    for k, (mid, _, _) in enumerate(elegidos):
        esc[mid] = k
    nombre = {v: k for k, v in materia.items()}
    por_jornada = defaultdict(list)
    for j, cid, mid, p in sesiones:
        por_jornada[j].append((p, mid))
    parciales = {}
    for mid, cid, _ in elegidos:
        if esc[mid] in PARCIAL:
            js = [j for j, x, f in jornadas if x == cid and diario.get((mid, j)) == 'PRESENTE']
            parciales[mid] = set(rng.sample(js, PARCIAL[esc[mid]]))
    filas = []
    for mid, cid, _ in mats:
        k = esc.get(mid)
        for j, x, f in jornadas:
            d = diario.get((mid, j))
            if x != cid or d is None:
                continue
            for p, mt in por_jornada[j]:
                e = 'PRESENTE' if d == 'ATRASO' and p > 1 else d
                if e in ('PRESENTE', 'ATRASO'):
                    if k in UNA and nombre[mt] == UNA[k][0] and rng.random() < UNA[k][1]:
                        e = 'FALTA'
                    elif k == VARIAS[0] and nombre[mt] in VARIAS[1] and rng.random() < VARIAS[2]:
                        e = 'FALTA'
                    elif mid in parciales and j in parciales[mid] and p > 3:
                        e = 'LICENCIA'
                filas.append((j, p, cid, mid, e))
    cit = []
    for mid, cid, cod in elegidos:
        if esc[mid] == 6:
            cit += [(mid, cod, 'DOCENTE_MATERIA', materia[MAT], date(2026, 8, 7 + 7 * i) if i < 4 else date(2026, 9, 11)) for i in range(5)]
            cit += [(mid, cod, 'DIRECCION', None, f) for f in (date(2026, 9, 18), date(2026, 10, 9))]
        if esc[mid] == 7:
            cit += [(mid, cod, 'DOCENTE_MATERIA', materia[n], date(2026, 9, 4 + 5 * i)) for i, n in enumerate(('Ciencias Naturales', 'Ciencias Sociales', REL, EFI))]
    return cursos, sesiones, filas, cit, elegidos, esc, nombre, alertas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ejecutar', action='store_true')
    args = ap.parse_args()
    engine = conectar()
    with engine.begin() as c:
        cursos, sesiones, filas, cit, elegidos, esc, nombre, alertas = preparar(c)
        print(f'sesiones_clase: {len(sesiones)} | asistencias_materia: {len(filas)} {dict(Counter(f[4] for f in filas))}')
        print(f'citaciones: {len(cit)} | apoderados de prueba: {len({x[0] for x in cit})}')
        from predictivo import asistencia_materia as am, perfil as pf
        from predictivo import seguimiento  # noqa: F401
        ids = {}
        ses = defaultdict(list)
        for i, (j, cid, mt, p) in enumerate(sesiones):
            ids[j, p] = i
            ses[cid].append(dict(id=i, materia_id=mt, dictada=True))
        reg, citas = defaultdict(list), defaultdict(list)
        for j, p, cid, mid, e in filas:
            reg[mid].append(dict(sesion_id=ids[j, p], estado=e))
        for mid, _, o, mt, f in cit:
            citas[mid].append(dict(materia_id=mt))
        curso_de = {mid: cid for mid, cid in c.execute(text('select id, curso_id from matriculas')).all()}
        antes, despues, cambian = Counter(), Counter(), []
        for mid, a in alertas.items():
            v = {**a['indicadores'], **am.senales(ses[curso_de[mid]], reg[mid], citas[mid], nombre)}
            n = pf.alerta(v, a['nivel'])
            antes[a['perfil']['nivel']] += 1
            despues[n['nivel']] += 1
            if n['nivel'] != a['perfil']['nivel'] or mid in esc:
                cambian.append((a['estudiante'].replace('SIM', 'PB'), a['curso'], a['perfil']['nivel'], n['nivel'], pf.explicacion(n, v), 'escenario' if mid in esc else 'NO previsto'))
        print('antes  ', dict(antes))
        print('después', dict(despues))
        for x in cambian:
            print('  ', *x, sep=' | ')
        if not args.ejecutar:
            print('Simulación: no se escribió nada.')
            return
        admin = c.execute(text("select min(id) from usuarios where rol='Admin'")).scalar()
        c.execute(text('insert into sesiones_clase(jornada_id, curso_id, materia_id, periodo, registrado_por) values (:j, :c, :m, :p, :u)'),
            [dict(j=j, c=cid, m=mt, p=p, u=admin) for j, cid, mt, p in sesiones])
        sid = {(j, p): i for i, j, p in c.execute(text('select id, jornada_id, periodo from sesiones_clase')).all()}
        datos = [dict(s=sid[j, p], c=cid, m=mid, e=e, u=admin) for j, p, cid, mid, e in filas]
        for i in range(0, len(datos), 10000):
            c.execute(text("insert into asistencias_materia(sesion_id, curso_id, matricula_id, estado, registrado_por, observacion) values (:s, :c, :m, :e, :u, 'SIMULADO')"), datos[i:i + 10000])
        apo = {}
        for mid, cod, o, mt, f in cit:
            if mid not in apo:
                apo[mid] = c.execute(text('insert into apoderados(nombre_completo) values (:n)'), dict(n=f"Apoderado de prueba {cod.replace('SIM', 'PB')}")).lastrowid
                c.execute(text("insert into estudiante_apoderado(estudiante_id, apoderado_id, parentesco, contacto_principal, vigente_desde) "
                    "select estudiante_id, :a, 'No registrado (prueba)', 1, '2026-02-09' from matriculas where id=:m"), dict(a=apo[mid], m=mid))
            c.execute(text("insert into citaciones(matricula_id, apoderado_id, fecha_programada, motivo, origen, materia_id, estado, registrado_por) "
                "values (:m, :a, :f, 'Citación de prueba (SIMULADO)', :o, :mt, 'ASISTIO', :u)"), dict(m=mid, a=apo[mid], f=datetime(f.year, f.month, f.day, 10), o=o, mt=mt, u=admin))
        print('Hecho.')


if __name__ == '__main__':
    main()
