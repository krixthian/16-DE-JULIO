"""Carga en alerta_temprana_v3 los docentes que figuran en los registros pedagógicos y los asigna a sus cursos.

Fuente: celda "MAESTRA/O:" de cada hoja de área y de FILIACION (coincide con el nombre del archivo en los 79 registros).
- Crea un usuario con rol Docente por cada docente, SIN contraseña (no puede entrar hasta que el administrador le
  asigne una en Gestión de usuarios) y con correo provisional nombre.apellido@16dejulio.edu.bo.
- Pasa las asignaciones curso x materia 2021-2025 (cargadas a nombre del administrador) a su docente.
- Marca al docente como asesor de cada curso.
Solo trabaja sobre alerta_temprana_v3. No toca estudiantes, notas, asistencia ni la gestión 2026.

Uso (desde backend):
    python -m predictivo.cargar_docentes_v3            # simulación
    python -m predictivo.cargar_docentes_v3 --ejecutar
"""
import argparse
import unicodedata
from collections import Counter
from pathlib import Path

import openpyxl
from sqlalchemy import text

from predictivo import registros_pedagogicos as rp
from predictivo.cargar_institucion_v3 import conectar

CARPETAS = [r'C:/Users/Cristhian/Documents/DATOS_COMPLETOS', r'C:/Users/Cristhian/Documents/DATOS']
DOMINIO = '16dejulio.edu.bo'


def vecino(ws, fila, col):
    for row in ws.iter_rows(min_row=fila, max_row=fila, min_col=col + 1, max_col=col + 15):
        for c in row:
            if isinstance(c.value, str) and c.value.strip() and ':' not in c.value:
                return ' '.join(c.value.split())
    return None


def leer_docentes(carpetas=CARPETAS):
    """{(gestión, grado, paralelo): nombre} desde los registros; exige un solo docente por curso."""
    out = {}
    for carpeta in carpetas:
        for ruta in sorted(Path(carpeta).rglob('REGISTRO_PEDAGOGICO_*.xlsx')):
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            g, gr, par = rp.curso(wb)
            nombres = {vecino(wb['FILIACION'], 5, 3)} | {vecino(wb[f'{a} 1'], 5, 21) for a in rp.AREAS if f'{a} 1' in wb.sheetnames}
            wb.close()
            nombres.discard(None)
            if len(nombres) != 1:
                raise ValueError(f'{ruta.name}: se esperaba un docente y hay {len(nombres)}.')
            out[(int(g), int(gr), str(par))] = nombres.pop()
    return out


def partes(nombre):
    p = nombre.title().split()
    corte = 1 if len(p) <= 3 else len(p) - 2
    return ' '.join(p[:corte]), ' '.join(p[corte:])


def correo(nombre, apellido):
    base = f'{nombre.split()[0]}.{apellido.split()[0]}'.lower()
    return unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode() + '@' + DOMINIO


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--ejecutar', action='store_true')
    args = a.parse_args()
    docentes = leer_docentes()
    personas = sorted(set(docentes.values()))
    usuarios = {n: (*partes(n), correo(*partes(n))) for n in personas}
    if len({u[2] for u in usuarios.values()}) != len(usuarios):
        raise ValueError('Correos provisionales repetidos.')
    engine = conectar()
    with engine.begin() as c:
        q = lambda s, **k: c.execute(text(s), k)
        admin = q("SELECT MIN(id) FROM usuarios WHERE rol='Admin'").scalar()
        cursos = {(int(g), int(gr), str(p)): int(i) for i, g, gr, p in q(
            'SELECT c.id, g.anio, c.grado, c.paralelo FROM cursos c JOIN gestiones g ON g.id=c.gestion_id WHERE g.anio BETWEEN 2021 AND 2025')}
        faltan = set(docentes) - set(cursos)
        if faltan:
            raise ValueError(f'Cursos de los registros que no están en la base: {sorted(faltan)}')
        existentes = {e for (e,) in q('SELECT email FROM usuarios')}
        choques = [u[2] for u in usuarios.values() if u[2] in existentes]
        asign = q(f"SELECT COUNT(*) FROM asignaciones_docentes WHERE curso_id IN ({','.join(map(str, cursos.values()))}) AND docente_id=:a", a=admin).scalar()
        print('Docentes a crear (sin contraseña):')
        for n, (nom, ape, mail) in usuarios.items():
            print(f'  {nom} | {ape} | {mail} | {sum(v == n for v in docentes.values())} cursos')
        print('Cursos con docente:', len(docentes), '| asignaciones a reasignar desde el admin:', asign, '| correos que ya existen:', choques)
        if not args.ejecutar:
            print('Simulación: no se modificó nada. Para cargar: --ejecutar')
            return
        if choques:
            raise RuntimeError('Hay correos que ya existen; no se carga nada.')
        ids = {}
        for n, (nom, ape, mail) in usuarios.items():
            ids[n] = q("INSERT INTO usuarios(nombre, apellido, email, password_hash, rol, activo) VALUES (:n, :a, :e, NULL, 'Docente', TRUE)",
                n=nom, a=ape, e=mail).lastrowid
        cambios = Counter()
        for k, n in docentes.items():
            cid = cursos[k]
            cambios['asignaciones'] += q('UPDATE asignaciones_docentes SET docente_id=:d WHERE curso_id=:c AND docente_id=:a', d=ids[n], c=cid, a=admin).rowcount
            cambios['cursos'] += q('UPDATE cursos SET docente_asesor_id=:d WHERE id=:c', d=ids[n], c=cid).rowcount
        print('Hecho:', dict(usuarios=len(ids), **cambios))


if __name__ == '__main__':
    main()
