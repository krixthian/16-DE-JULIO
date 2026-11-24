"""Simula la gestión 2026 (datos SIMULADOS) de febrero a octubre en alerta_temprana_v3, para demostrar el sistema.

Todo queda en la gestión 2026, cuyas 150 matrículas ya están marcadas como origen SIMULADO; no toca 2021-2025.
- Periodos 2 y 3 (T2 may-ago, T3 sep-nov) si faltan.
- Asignaciones curso x materia que falten, con el docente que tuvo ese grado en 2025 (continuidad); no cambia las
  existentes. Asesor del curso si no tiene.
- Días de clase del 9/02 al 30/10/2026 (lunes a viernes, sin feriados ni descanso pedagógico de invierno).
- Asistencia diaria: cada estudiante simulado toma las tasas de faltas, atrasos y licencias de un estudiante REAL que
  continuó (2021-2025), elegido al azar, y los días se generan con esas tasas. Escenarios explícitos para la demo:
    * 2 estudiantes dejan de asistir (uno desde el 18/05, otro desde el 07/09): todo falta desde esa fecha;
    * 1 estudiante con faltas en aumento desde agosto que no abandona;
    * 1 estudiante con licencia médica de 7 días en junio (la licencia corta la racha: no es alerta).
- Notas por área: T1 y T2 (cerrados) y una nota parcial del T3. El perfil de notas de cada estudiante se toma de un
  estudiante real (notas del T1 por área) con una variación pequeña entre trimestres. Quien dejó de asistir no tiene
  nota en los trimestres posteriores (NO_PRESENTADA).
Reproducible (semilla 2026). Sin nombres nuevos: los estudiantes simulados ya existen.

Uso (desde backend):
    python -m predictivo.simular_2026            # simulación: muestra qué se insertaría
    python -m predictivo.simular_2026 --ejecutar
"""
import argparse
from collections import Counter
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from predictivo.cargar_institucion_v3 import AREAS, DATOS, conectar

ANIO = 2026
INICIO, FIN = date(2026, 2, 9), date(2026, 10, 30)
FERIADOS = {date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3), date(2026, 5, 1), date(2026, 6, 4), date(2026, 6, 22), date(2026, 8, 6)}
INVIERNO = (date(2026, 7, 6), date(2026, 7, 17))
PERIODOS = {2: (date(2026, 5, 1), date(2026, 8, 31)), 3: (date(2026, 9, 1), date(2026, 11, 30))}
CIERRE = {1: date(2026, 4, 30), 2: date(2026, 8, 31), 3: date(2026, 10, 30)}
TITULO = {1: 'Nota del 1.er trimestre', 2: 'Nota del 2.º trimestre', 3: 'Nota parcial del 3.er trimestre'}
CODIGO = {'A': 'PRESENTE', 'F': 'FALTA', 'R': 'ATRASO', 'L': 'LICENCIA'}


def dias_de_clase():
    d, out = INICIO, []
    while d <= FIN:
        if d.weekday() < 5 and d not in FERIADOS and not (INVIERNO[0] <= d <= INVIERNO[1]):
            out.append(d)
        d += timedelta(days=1)
    return out


def perfiles_reales():
    """Tasas F/R/L y notas T1 por área de estudiantes reales que continuaron (para muestrear perfiles)."""
    ds = pd.read_excel(DATOS / 'DATASET_INSTITUCION_2021_2025.xlsx', sheet_name='DATOS_REAL')
    ds = ds[(ds.y_abandono_intra_anual == 0) & ds[[f'{a}_T1' for a in AREAS]].notna().all(axis=1)]
    asis = pd.read_csv(DATOS / 'DATASET_INSTITUCION_2021_2025_ASISTENCIA_DIARIA.csv')
    tasas = asis.groupby(['codigo_anonimo', 'gestion']).estado.value_counts(normalize=True).unstack(fill_value=0)
    ds = ds.join(tasas, on=['codigo_anonimo', 'gestion'], how='inner')
    return ds[['F', 'R', 'L'] + [f'{a}_T1' for a in AREAS]].reset_index(drop=True)


def generar(matriculas, dias, rng):
    """matriculas: [(id, curso_id)]. Devuelve asistencia {(mid, fecha): código}, notas {(mid, area, n): nota|None} y escenarios."""
    perf = perfiles_reales()
    asis, notas, esc = {}, {}, {}
    orden = list(matriculas)
    rng.shuffle(orden)
    escenarios = ['abandona_mayo', 'abandona_septiembre', 'faltas_en_aumento', 'licencia_medica']
    for i, (mid, _) in enumerate(orden):
        esc[mid] = escenarios[i] if i < len(escenarios) else 'normal'
    for mid, _ in matriculas:
        p = perf.iloc[rng.integers(len(perf))]
        f, r, l = float(p.F), float(p.R), float(p.L)
        base = [rng.choice(['F', 'R', 'L', 'A'], p=[f, r, l, max(0.0, 1 - f - r - l)]) for _ in dias]
        e = esc[mid]
        for k, d in enumerate(dias):
            c = base[k]
            if e == 'abandona_mayo' and d >= date(2026, 5, 18):
                c = 'F'
            elif e == 'abandona_septiembre' and d >= date(2026, 9, 7):
                c = 'F'
            elif e == 'faltas_en_aumento' and d >= date(2026, 8, 3):
                c = 'F' if (rng.random() < 0.08 + 0.25 * (d - date(2026, 8, 3)).days / 90 and k % 3) else ('A' if c == 'F' else c)
            elif e == 'licencia_medica' and date(2026, 6, 8) <= d <= date(2026, 6, 16):
                c = 'L'
            asis[(mid, d)] = c
        for a in AREAS:
            t1 = float(p[f'{a}_T1'])
            for n in (1, 2, 3):
                v = int(np.clip(round(t1 + rng.normal(0, 3) * (n - 1)), 1, 100))
                if e == 'faltas_en_aumento' and n == 3:
                    v = max(1, v - 8)
                sin_nota = (e == 'abandona_mayo' and n >= 2) or (e == 'abandona_septiembre' and n == 3)
                notas[(mid, a, n)] = None if sin_nota else v
    return asis, notas, esc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ejecutar', action='store_true')
    args = ap.parse_args()
    rng = np.random.default_rng(2026)
    engine = conectar()
    with engine.begin() as c:
        q = lambda s, **k: c.execute(text(s), k)
        g = q('SELECT id FROM gestiones WHERE anio=:a', a=ANIO).scalar()
        cursos = {int(i): (int(gr), p, ase) for i, gr, p, ase in q('SELECT id, grado, paralelo, docente_asesor_id FROM cursos WHERE gestion_id=:g ORDER BY grado', g=g)}
        mats = [(int(i), int(cid)) for i, cid, o in q('SELECT m.id, m.curso_id, m.origen FROM matriculas m WHERE m.curso_id IN :c', c=tuple(cursos)) if o == 'SIMULADO']
        otras = q("SELECT COUNT(*) FROM matriculas WHERE curso_id IN :c AND origen<>'SIMULADO'", c=tuple(cursos)).scalar()
        if otras:
            raise RuntimeError('Hay matrículas reales en 2026; no se simula.')
        periodos = {int(n): int(i) for i, n in q('SELECT id, numero FROM periodos WHERE gestion_id=:g', g=g)}
        materia = {s: int(i) for i, s in q('SELECT id, sigla FROM materias')}
        prof_2025 = {int(gr): int(u) for gr, u in q('SELECT c.grado, MIN(c.docente_asesor_id) FROM cursos c JOIN gestiones x ON x.id=c.gestion_id WHERE x.anio=2025 GROUP BY c.grado')}
        asign = {(int(cid), int(mid)): (int(i), int(d)) for i, cid, mid, d in q('SELECT id, curso_id, materia_id, docente_id FROM asignaciones_docentes WHERE curso_id IN :c', c=tuple(cursos))}
        jornadas_exist = {(int(cid), f) for cid, f in q('SELECT curso_id, fecha FROM jornadas_clase WHERE curso_id IN :c', c=tuple(cursos))}
        dias = dias_de_clase()
        asis, notas, esc = generar(mats, dias, rng)
        nuevas_asig = [(cid, a) for cid in cursos for a in AREAS if (cid, materia[a]) not in asign]
        nuevas_jornadas = [(cid, d) for cid in cursos for d in dias if (cid, d) not in jornadas_exist]
        conteo = Counter(asis.values())
        resumen = dict(periodos_nuevos=[n for n in PERIODOS if n not in periodos], asignaciones_nuevas=len(nuevas_asig),
            asesores_nuevos=sum(1 for v in cursos.values() if v[2] is None), dias_de_clase=len(dias), jornadas_nuevas=len(nuevas_jornadas),
            asistencias=len(asis), estados={CODIGO[k]: v for k, v in conteo.items()}, evaluaciones=len(cursos) * len(AREAS) * 3,
            calificaciones=len(notas), sin_nota=sum(v is None for v in notas.values()))
        print('Gestión 2026 (SIMULADA), 9/02 a 30/10/2026:', resumen)
        cod = dict(q('SELECT m.id, e.codigo_anonimo FROM matriculas m JOIN estudiantes e ON e.id=m.estudiante_id WHERE m.curso_id IN :c', c=tuple(cursos)).all())
        print('Escenarios de demostración:', {k: f'{cursos[dict(mats)[m]][0]}° {cursos[dict(mats)[m]][1]} (matrícula {m}, {cod[m]})' for m, k in
            ((m, e) for m, e in esc.items() if e != 'normal')})
        if not args.ejecutar:
            print('Simulación: no se modificó nada. Para cargar: --ejecutar')
            return
        for n, (a, b) in PERIODOS.items():
            if n not in periodos:
                periodos[n] = q('INSERT INTO periodos(gestion_id, numero, fecha_inicio, fecha_fin) VALUES (:g, :n, :a, :b)', g=g, n=n, a=a, b=b).lastrowid
        for cid, (gr, p, ase) in cursos.items():
            if ase is None:
                q('UPDATE cursos SET docente_asesor_id=:d WHERE id=:c', d=prof_2025[gr], c=cid)
        for cid, a in nuevas_asig:
            i = q('INSERT INTO asignaciones_docentes(curso_id, materia_id, docente_id, vigente_desde) VALUES (:c, :m, :d, :v)',
                c=cid, m=materia[a], d=prof_2025[cursos[cid][0]], v=INICIO).lastrowid
            asign[(cid, materia[a])] = (i, prof_2025[cursos[cid][0]])
        c.execute(text('INSERT INTO jornadas_clase(curso_id, fecha, es_lectiva) VALUES (:c, :f, TRUE)'), [dict(c=cid, f=d) for cid, d in nuevas_jornadas])
        jornada = {(int(cid), f): int(i) for i, cid, f in q('SELECT id, curso_id, fecha FROM jornadas_clase WHERE curso_id IN :c', c=tuple(cursos))}
        resp = {cid: (ase or prof_2025[gr]) for cid, (gr, p, ase) in cursos.items()}
        filas = [dict(m=mid, j=jornada[(cid, d)], c=cid, e=CODIGO[asis[(mid, d)]], u=resp[cid]) for mid, cid in mats for d in dias]
        for i in range(0, len(filas), 10000):
            c.execute(text('INSERT INTO asistencias(matricula_id, jornada_id, curso_id, estado, registrado_por) VALUES (:m, :j, :c, :e, :u)'), filas[i:i + 10000])
        evalu = {}
        for cid in cursos:
            for a in AREAS:
                aid, doc = asign[(cid, materia[a])]
                for n in (1, 2, 3):
                    evalu[(cid, a, n)] = (q("INSERT INTO evaluaciones(asignacion_id, curso_id, gestion_id, periodo_id, titulo, tipo, fecha_aplicacion, puntaje_maximo) "
                        "VALUES (:a, :c, :g, :p, :t, 'OTRA', :f, 100)", a=aid, c=cid, g=g, p=periodos[n], t=f'{TITULO[n]} - {a}', f=CIERRE[n]).lastrowid, doc)
        cal = []
        for mid, cid in mats:
            for a in AREAS:
                for n in (1, 2, 3):
                    v = notas[(mid, a, n)]
                    eid, doc = evalu[(cid, a, n)]
                    cal.append(dict(e=eid, m=mid, c=cid, s='CALIFICADA' if v is not None else 'NO_PRESENTADA', p=v, u=doc))
        c.execute(text('INSERT INTO calificaciones(evaluacion_id, matricula_id, curso_id, estado, puntaje, registrado_por) VALUES (:e, :m, :c, :s, :p, :u)'), cal)
        print('Hecho:', dict(asistencias=len(filas), evaluaciones=len(evalu), calificaciones=len(cal), jornadas=len(nuevas_jornadas), asignaciones=len(nuevas_asig)))


if __name__ == '__main__':
    main()
