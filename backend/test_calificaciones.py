import asyncio
import unittest
from datetime import date
from decimal import Decimal
import httpx
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from database import engine,get_db
from main import app
from api.auth import get_current_user
import models as m

class CalificacionesTests(unittest.TestCase):
 def test_periodos_evaluaciones_y_notas(self):
  async def run():
   with engine.connect() as conn:
    tx=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
    admin=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
    teacher=m.Usuario(nombre='Temporal',apellido='Notas',email='grades-test@example.invalid',rol='Docente',activo=True)
    stranger=m.Usuario(nombre='Otro',apellido='Docente',email='grades-test2@example.invalid',rol='Docente',activo=True)
    db.add_all([teacher,stranger]);db.flush()
    g=m.Gestion(anio=1992,fecha_inicio=date(1992,2,1),fecha_fin=date(1992,11,30));db.add(g);db.flush()
    c=m.Curso(gestion_id=g.id,grado=2,paralelo='QA');s=m.Materia(nombre='Materia notas temporal');db.add_all([c,s]);db.flush()
    a=m.AsignacionDocente(curso_id=c.id,materia_id=s.id,docente_id=teacher.id,vigente_desde=date(1992,2,1),vigente_hasta=date(1992,11,30));db.add(a);db.flush()
    enrollments=[]
    for n in range(5):
     st=m.Estudiante(nombre=f'Alumno {n}',apellido='Temporal',codigo_anonimo=f'GRADES-QA-{n}');db.add(st);db.flush()
     en=m.Matricula(estudiante_id=st.id,curso_id=c.id,fecha_ingreso=date(1992,2,1) if n<4 else date(1992,6,1),origen='SIMULADO',registrado_por=admin.id);db.add(en);db.flush();enrollments.append(en)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:admin
    try:
     async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
      async def req(method,path,body=None,status=200):
       r=await client.request(method,'/calificaciones/'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
      pb={'gestion_id':g.id,'numero':1,'fecha_inicio':'1992-02-01','fecha_fin':'1992-05-31'}
      p=await req('POST','periodos',pb,201)
      await req('POST','periodos',pb,409)
      await req('POST','periodos',{**pb,'numero':2,'fecha_inicio':'1992-05-20','fecha_fin':'1992-08-31'},409)
      await req('POST','periodos',{**pb,'numero':2,'fecha_inicio':'1992-06-01','fecha_fin':'1992-08-31'},201)
      app.dependency_overrides[get_current_user]=lambda:teacher
      await req('POST','periodos',pb,403)
      context=await req('GET','contexto');self.assertEqual([x['id'] for x in context['asignaciones']],[a.id])
      eb={'asignacion_id':a.id,'periodo_id':p['id'],'titulo':'Prueba parcial','tipo':'PRUEBA','fecha_aplicacion':'1992-03-10','puntaje_maximo':'20.00','dimension':None}
      await req('POST','evaluaciones',{**eb,'fecha_aplicacion':'1992-06-10'},422)
      e=await req('POST','evaluaciones',eb,201)
      app.dependency_overrides[get_current_user]=lambda:stranger
      await req('GET',f"evaluaciones/{e['id']}/notas",status=403)
      await req('GET',f'evaluaciones?asignacion_id={a.id}',status=403)
      app.dependency_overrides[get_current_user]=lambda:teacher
      sheet=await req('GET',f"evaluaciones/{e['id']}/notas")
      self.assertEqual(len(sheet['estudiantes']),4)
      self.assertEqual(db.scalar(select(func.count()).select_from(m.Calificacion).where(m.Calificacion.evaluacion_id==e['id'])),0)
      rows=[{'matricula_id':x['matricula_id'],'estado':state,'puntaje':score} for x,state,score in zip(sheet['estudiantes'],['CALIFICADA','PENDIENTE','NO_PRESENTADA','EXENTA'],['0.00',None,None,None])]
      async def put(sh,rs=rows,status=200,**kw):return await req('PUT',f"evaluaciones/{e['id']}/notas",{'revision':sh['revision'],'estudiantes':rs,**kw},status)
      await put(sheet,[{**rows[0],'puntaje':'20.01'},*rows[1:]],422)
      await put(sheet,[{**rows[0],'puntaje':'0.001'},*rows[1:]],422)
      await put(sheet,[rows[0],{**rows[1],'puntaje':'5'},*rows[2:]],422)
      await put(sheet,[*rows,{'matricula_id':enrollments[-1].id,'estado':'PENDIENTE','puntaje':None}],422)
      saved=await put(sheet)
      self.assertEqual(Decimal(str(saved['estudiantes'][0]['puntaje'])),Decimal('0'))
      self.assertTrue(all(x['puntaje'] is None for x in saved['estudiantes'][1:]))
      await put(sheet,status=409)
      changed=[{**rows[0],'puntaje':'18.50'},*rows[1:]]
      await put(saved,changed,422)
      updated=await put(saved,changed,motivo_correccion='Revisión del puntaje')
      self.assertEqual(Decimal(str(updated['estudiantes'][0]['puntaje'])),Decimal('18.5'))
      await req('PUT',f"evaluaciones/{e['id']}",{**eb,'puntaje_maximo':'100','revision':e['revision'],'motivo_correccion':'Cambio'},409)
      renamed=await req('PUT',f"evaluaciones/{e['id']}",{**eb,'titulo':'Prueba parcial corregida','revision':e['revision'],'motivo_correccion':'Aclaración del título'})
      self.assertEqual(renamed['titulo'],'Prueba parcial corregida')
      await put(updated,changed,409,motivo_correccion='Lista anterior')
      app.dependency_overrides[get_current_user]=lambda:admin
      await req('PUT',f"periodos/{p['id']}",{**pb,'fecha_inicio':'1992-04-01'},409)
      self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(m.AuditoriaCambio.tabla_afectada=='calificaciones')),0)
    finally:app.dependency_overrides.clear();db.close();tx.rollback()
  asyncio.run(run())
if __name__=='__main__':unittest.main()
