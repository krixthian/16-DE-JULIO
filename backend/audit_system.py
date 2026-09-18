"""Auditoría de lectura de esquema, cantidad de filas y relaciones. No muestra datos personales."""
import json
from pathlib import Path
from sqlalchemy import inspect,select,func,text
from database import engine
from models import Base
from main import app

report={'database':None,'tables':{},'foreign_keys':0,'orphan_relations':[],'schema_differences':[],'routes':[]}
inspector=inspect(engine)
with engine.connect() as conn:
 report['database']=conn.scalar(text('SELECT DATABASE()'))
 for name,table in Base.metadata.tables.items():
  actual={c['name'] for c in inspector.get_columns(name)}
  expected=set(table.columns.keys())
  if actual!=expected:report['schema_differences'].append({'table':name,'missing':sorted(expected-actual),'extra':sorted(actual-expected)})
  conn.execute(select(table).limit(0))
  report['tables'][name]=conn.scalar(select(func.count()).select_from(table))
  for fk in inspector.get_foreign_keys(name):
   report['foreign_keys']+=1
   columns=fk['constrained_columns'];targets=fk['referred_columns']
   join=' AND '.join(f'a.`{x}`=b.`{y}`' for x,y in zip(columns,targets))
   notnull=' AND '.join(f'a.`{x}` IS NOT NULL' for x in columns)
   query=f'SELECT COUNT(*) FROM `{name}` a LEFT JOIN `{fk["referred_table"]}` b ON {join} WHERE {notnull} AND b.`{targets[0]}` IS NULL'
   count=conn.scalar(text(query))
   if count:report['orphan_relations'].append({'table':name,'constraint':fk['name'],'count':count})
for route in app.routes:
 if getattr(route,'path','').startswith(('/auth','/users','/escolar','/asistencia','/calificaciones','/tareas','/health')):
  report['routes'].append({'path':route.path,'methods':sorted(route.methods)})
output=Path(__file__).resolve().parents[1]/'docs'/'auditoria_conexion.json'
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['database','foreign_keys','orphan_relations','schema_differences']},ensure_ascii=False))
print(f'Tablas: {len(report["tables"])}; rutas: {len(report["routes"])}; informe: {output}')
