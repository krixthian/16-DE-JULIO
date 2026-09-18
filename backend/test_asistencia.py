import asyncio
import unittest
from datetime import date,timedelta
from sqlalchemy import select,func
from sqlalchemy.orm import Session
import httpx
from database import engine,get_db
from main import app
from api.auth import get_current_user
import models as m

class AsistenciaTests(unittest.TestCase):
 def test_daily_register(self):
  async def run():
   with engine.connect() as conn:
    tx=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
    admin=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
    teacher=m.Usuario(nombre='Temporal',apellido='Asistencia',email='attendance-test@example.invalid',rol='Docente',activo=True)
    db.add(teacher);db.flush()
    year=m.Gestion(anio=1991,fecha_inicio=date(1991,2,1),fecha_fin=date(1991,11,30));db.add(year);db.flush()
    course=m.Curso(gestion_id=year.id,grado=1,paralelo='QA');other=m.Curso(gestion_id=year.id,grado=2,paralelo='QA');db.add_all([course,other]);db.flush()
    subject=m.Materia(nombre='Asistencia temporal QA');db.add(subject);db.flush()
    db.add(m.AsignacionDocente(curso_id=course.id,materia_id=subject.id,docente_id=teacher.id,vigente_desde=date(1991,2,1),vigente_hasta=date(1991,6,30)))
    enrollments=[]
    for n in range(3):
     s=m.Estudiante(nombre=f'Prueba {n}',apellido='Temporal',codigo_anonimo=f'ATTENDANCE-TEST-{n}');db.add(s);db.flush()
     e=m.Matricula(estudiante_id=s.id,curso_id=course.id,fecha_ingreso=date(1991,2,1) if n<2 else date(1991,3,1),origen='SIMULADO',registrado_por=admin.id);db.add(e);db.flush();enrollments.append(e)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:teacher
    try:
     async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
      async def get(day='1991-02-04',cid=None,status=200):
       r=await c.get(f'/asistencia/{cid or course.id}/{day}');self.assertEqual(r.status_code,status,r.text);return r.json()
      async def put(sheet,rows=None,status=200,**kw):
       body={'revision':sheet['revision'],'es_lectiva':sheet['es_lectiva'],'estudiantes':rows if rows is not None else [{k:x[k] for k in ('matricula_id','estado','justificada','observacion')} for x in sheet['estudiantes']],**kw}
       r=await c.put(f"/asistencia/{course.id}/{sheet['fecha']}",json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
      self.assertEqual(len((await c.get('/asistencia/cursos')).json()),1)
      sheet=await get();self.assertEqual(len(sheet['estudiantes']),2)
      self.assertFalse(sheet['jornada_registrada'])
      self.assertIsNone(db.scalar(select(m.JornadaClase.id).where(m.JornadaClase.curso_id==course.id)))
      await get(cid=other.id,status=403);await get('1991-07-01',status=403)
      await put(sheet,status=422)
      payload=[{'matricula_id':x['matricula_id'],'estado':None} for x in sheet['estudiantes']]
      payload[0]['estado']='PRESENTE'
      await put(sheet,payload+[{'matricula_id':enrollments[2].id,'estado':'FALTA'}],422)
      saved=await put(sheet,payload)
      self.assertEqual(sum(x['estado'] is None for x in saved['estudiantes']),1)
      await put(sheet,payload,409)
      payload[0]['estado']='ATRASO'
      await put(saved,payload,422)
      updated=await put(saved,payload,motivo_correccion='Corrección comprobada')
      self.assertEqual(updated['estudiantes'][0]['estado'],'ATRASO')
      await put(updated,[{'matricula_id':x['matricula_id'],'estado':None} for x in updated['estudiantes']],422)
      self.assertEqual(db.scalar(select(func.count()).select_from(m.Asistencia).where(m.Asistencia.curso_id==course.id)),1)
      day=await get('1991-02-05')
      await put(day,es_lectiva=False,motivo_no_lectiva='Suspensión',status=403)
      app.dependency_overrides[get_current_user]=lambda:admin
      off=await put(day,es_lectiva=False,motivo_no_lectiva='Suspensión')
      self.assertFalse(off['es_lectiva'])
      app.dependency_overrides[get_current_user]=lambda:teacher
      await put(off,status=403,motivo_no_lectiva='Suspensión')
      r=await c.put(f'/asistencia/{course.id}/{date.today()+timedelta(days=1)}',json={'revision':'0'*64,'estudiantes':[]});self.assertEqual(r.status_code,422)
      app.dependency_overrides[get_current_user]=lambda:m.Usuario(id=admin.id,rol='Orientador')
      self.assertEqual((await c.get('/asistencia/cursos')).status_code,403)
      self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(m.AuditoriaCambio.tabla_afectada=='asistencias')),0)
    finally:app.dependency_overrides.clear();db.close();tx.rollback()
  asyncio.run(run())
if __name__=='__main__':unittest.main()
