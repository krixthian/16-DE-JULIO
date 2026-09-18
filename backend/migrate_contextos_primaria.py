"""Ajuste explícito de la ficha vacía a variables escolares de primaria."""
from pathlib import Path
from datetime import datetime
from sqlalchemy import inspect, text, CheckConstraint
from sqlalchemy.schema import CreateColumn, CreateTable, CreateIndex
from database import engine
from models import ContextoPermanencia

def main():
    if engine.url.database != 'alerta_temprana_v2':
        raise RuntimeError('Base inesperada; no se modifica.')
    table = ContextoPermanencia.__table__
    inspector = inspect(engine)
    actual = {c['name'] for c in inspector.get_columns(table.name)}
    expected = set(table.columns.keys())
    root = Path(__file__).resolve().parent.parent
    if actual != expected:
        with engine.connect() as conn:
            if conn.scalar(text('SELECT COUNT(*) FROM contextos_permanencia')):
                raise RuntimeError('Hay fichas existentes: se requiere preservar sus valores antes de migrar.')
            ddl = conn.execute(text('SHOW CREATE TABLE contextos_permanencia')).one()[1]
            backup = root / 'backups' / ('contexto_antes_primaria_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.sql')
            backup.parent.mkdir(exist_ok=True)
            backup.write_text(ddl + ';\n', encoding='utf-8')
            changes = ['DROP CHECK `' + c['name'] + '`' for c in inspector.get_check_constraints(table.name)]
            changes += ['DROP COLUMN `' + c + '`' for c in sorted(actual-expected)]
            changes += ['ADD COLUMN ' + str(CreateColumn(table.c[c]).compile(dialect=engine.dialect)) for c in sorted(expected-actual)]
            changes += ['ADD CONSTRAINT `' + c.name + '` CHECK (' + str(c.sqltext) + ')' for c in table.constraints if isinstance(c, CheckConstraint)]
            sql = 'ALTER TABLE contextos_permanencia\n  ' + ',\n  '.join(changes) + ';'
            (root / 'database_ajuste_primaria.sql').write_text('-- Solo para la ficha anterior VACIA; preferir el migrador Python que verifica esa condición.\nUSE alerta_temprana_v2;\n' + sql, encoding='utf-8')
            conn.execute(text(sql)); conn.commit()
    ddl = str(CreateTable(table).compile(dialect=engine.dialect)).strip() + ';\n'
    ddl += '\n'.join(str(CreateIndex(i).compile(dialect=engine.dialect)) + ';' for i in table.indexes) + '\n'
    (root / 'database_contextos_permanencia.sql').write_text('-- Para crear la tabla en una base donde aún no existe.\nUSE alerta_temprana_v2;\n' + ddl, encoding='utf-8')
    schema = root / 'database_schema.sql'
    original = schema.read_text(encoding='utf-8')
    marker = '-- Contexto adicional de permanencia escolar.'
    schema.write_text(original.split(marker)[0] + marker + '\n' + ddl, encoding='utf-8')
    print('Ficha de primaria aplicada: 27 variables, 36 columnas. Sin datos insertados.')

if __name__ == '__main__':
    main()
