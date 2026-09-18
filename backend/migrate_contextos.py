"""Ampliación aditiva. No altera tablas existentes ni inserta datos de alumnos."""
from sqlalchemy import inspect
from database import engine
from models import ContextoPermanencia

def main():
    if engine.url.database != 'alerta_temprana_v2':
        raise RuntimeError('Se esperaba alerta_temprana_v2; no se realizaron cambios.')
    table = ContextoPermanencia.__table__
    table.create(engine, checkfirst=True)
    actual = {c['name'] for c in inspect(engine).get_columns(table.name)}
    if actual != set(table.columns.keys()):
        raise RuntimeError('La tabla existente difiere del modelo; revisar manualmente.')
    print(f'Base: {engine.url.database}. Tabla {table.name} verificada ({len(actual)} columnas).')

if __name__ == '__main__':
    main()
