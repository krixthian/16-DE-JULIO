import asyncio
import unittest
from datetime import date, datetime
from unittest.mock import patch
import httpx
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from database import engine,get_db
from main import app
from api.auth import get_current_user
import models as m

class Frozen(datetime):
 @classmethod
 def now(cls,tz=None):return cls(1993,3,10,12)

class TareasTests(unittest.TestCase):
 def test_tareas_entregas_permisos_e_historial(self):
  async def run():
   with engine.connect() as conn:
    tx=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
    admin=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
    teacher=m.Usuario(nombre='Temporal',apellido='Notas',email='tasks-test@example.invalid',rol='Docente',activo=True)
    stranger=m.Usuario(nombre='Otro',apellido='Docente',email='tasks-test2@example.invalid',rol='Docente',activo=True)
    db.add_all([teacher,stranger]);db.flush()
    g=m.Gestion(anio=1993,fecha_inicio=date(1993,2,1),fecha_fin=date(1993,11,30));db.add(g);db.flush()
    c=m.Curso(gestion_id=g.id,grado=2,paralelo='QA');s=m.Materia(nombre='Materia notas temporal');db.add_all([c,s]);db.flush()
    a=m.AsignacionDocente(curso_id=c.id,materia_id=s.id,docente_id=teacher.id,vigente_desde=date(1993,2,1),vigente_hasta=date(1993,11,30));db.add(a);db.flush()
    enrollments=[]
    for n in range(5):
     st=m.Estudiante(nombre=f'Alumno {n}',apellido='Temporal',codigo_anonimo=f'TASKS-QA-{n}');db.add(st);db.flush()
     en=m.Matricula(estudiante_id=st.id,curso_id=c.id,fecha_ingreso=date(1993,2,1) if n<4 else date(1993,6,1),origen='SIMULADO',registrado_por=admin.id);db.add(en);db.flush();enrollments.append(en)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:teacher
    try:
     with patch('api.tareas.datetime',Frozen):
      async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
       async def req(method,path='',body=None,status=200):
        r=await client.request(method,'/tareas'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
       context=await req('GET','/contexto');self.assertEqual([x['id'] for x in context['asignaciones']],[a.id])
       payload={'asignacion_id':a.id,'titulo':'Lectura semanal','fecha_asignacion':'1993-03-01T08:00:00','fecha_limite':'1993-03-08T12:00:00'}
       await req('POST',body={**payload,'fecha_limite':'1993-02-28T12:00:00'},status=422)
       await req('POST',body={**payload,'fecha_limite':'1993-12-01T12:00:00'},status=422)
       t=await req('POST',body=payload,status=201)
       self.assertEqual(len(await req('GET',f'?asignacion_id={a.id}')),1)
       path=f"/{t['id']}/entregas"
       app.dependency_overrides[get_current_user]=lambda:stranger
       await req('GET',path,status=403)
       await req('POST',body=payload,status=403)
       app.dependency_overrides[get_current_user]=lambda:teacher
       sh=await req('GET',path)
       self.assertEqual(len(sh['estudiantes']),4)
       self.assertTrue(all(x['estado'] is None for x in sh['estudiantes']))
       self.assertEqual(db.scalar(select(func.count()).select_from(m.EntregaTarea).where(m.EntregaTarea.tarea_id==t['id'])),0)
       rows=[{'matricula_id':x['matricula_id'],'estado':s,'fecha_entrega':d} for x,s,d in zip(sh['estudiantes'],['ENTREGADA','ENTREGADA','NO_ENTREGADA','EXENTA'],['1993-03-08T12:00:00','1993-03-09T12:00:00',None,None])]
       async def put(sheet,rs=rows,status=200,**kw):return await req('PUT',path,{'revision':sheet['revision'],'estudiantes':rs,**kw},status)
       await put(sh,[{**rows[0],'fecha_entrega':None},*rows[1:]],422)
       await put(sh,[{**rows[0],'fecha_entrega':'1993-03-11T12:00:00'},*rows[1:]],422)
       await put(sh,[{**rows[0],'fecha_entrega':'1993-02-28T12:00:00'},*rows[1:]],422)
       await put(sh,[*rows,rows[0]],422)
       await put(sh,[*rows,{'matricula_id':enrollments[-1].id,'estado':'PENDIENTE'}],422)
       saved=await put(sh)
       self.assertFalse(saved['estudiantes'][0]['fuera_plazo']);self.assertTrue(saved['estudiantes'][1]['fuera_plazo'])
       await put(sh,status=409)
       changed=[rows[0],rows[1],{**rows[2],'estado':'EXENTA'},rows[3]]
       await put(saved,changed,422)
       updated=await put(saved,changed,motivo_correccion='Justificación revisada')
       await put(updated,[{**rows[0],'estado':None,'fecha_entrega':None},*changed[1:]],422)
       await req('PUT',f"/{t['id']}",{**payload,'fecha_limite':'1993-03-09T12:00:00','revision':t['revision'],'motivo_correccion':'Cambio'},409)
       await req('PUT',f"/{t['id']}",{**payload,'titulo':'Lectura corregida','revision':t['revision'],'motivo_correccion':'Título aclarado'})
       await put(updated,changed,409,motivo_correccion='Lista vieja')
       future=await req('POST',body={**payload,'fecha_limite':'1993-03-15T12:00:00'},status=201)
       path=f"/{future['id']}/entregas";sh=await req('GET',path)
       await put(sh,status=422)
       pending=[{**x,'estado':'PENDIENTE','fecha_entrega':None} for x in rows]
       await put(sh,pending)
       planned=await req('POST',body={**payload,'fecha_asignacion':'1993-03-12T08:00:00','fecha_limite':'1993-03-15T12:00:00'},status=201)
       path=f"/{planned['id']}/entregas";sh=await req('GET',path)
       await put(sh,pending,422)
       self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(m.AuditoriaCambio.tabla_afectada=='entregas_tareas')),0)
    finally:app.dependency_overrides.clear();db.close();tx.rollback()
  asyncio.run(run())
if __name__=='__main__':unittest.main()
