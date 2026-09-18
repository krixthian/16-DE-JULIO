"""Revisión integral: autenticación real, usuarios, conexión y calendario. Sin datos persistentes."""
import asyncio
import unittest
from unittest.mock import Mock
from datetime import date, datetime
import httpx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import engine,get_db
from main import app
from core.security import get_password_hash
import models as m

class SystemTests(unittest.TestCase):
 def test_auth_users_and_module_reads(self):
  async def run():
   with engine.connect() as conn:
    tx=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
    password=' QA-valid-pass-27 '
    admin=m.Usuario(nombre='Temporal',apellido='Revisión',email='audit-admin@example.org',rol='Admin',activo=True,password_hash=get_password_hash(password))
    db.add(admin);db.flush()
    app.dependency_overrides[get_db]=lambda:db
    try:
     async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
      async def request(method,path,body=None,code=200):
       r=await client.request(method,path,json=body);self.assertEqual(r.status_code,code,r.text);return r.json()
      for path in ['/users/','/escolar/estudiantes','/asistencia/cursos','/calificaciones/contexto','/tareas/contexto']:
       await request('GET',path,code=401)
      r=await client.post('/auth/login',data={'username':admin.email,'password':'wrong'})
      self.assertEqual(r.status_code,401)
      r=await client.post('/auth/login',data={'username':admin.email,'password':password})
      self.assertEqual(r.status_code,200,r.text)
      client.headers['Authorization']='Bearer '+r.json()['access_token']
      self.assertEqual((await request('GET','/auth/me'))['id'],admin.id)
      for path in ['/users/','/escolar/gestiones','/escolar/cursos','/escolar/estudiantes','/escolar/matriculas','/escolar/materias','/escolar/asignaciones','/escolar/docentes','/asistencia/cursos','/calificaciones/contexto','/tareas/contexto']:
       await request('GET',path)
      body={'nombre':'Usuario','apellido':'Temporal','email':'audit-user@example.org','rol':'Docente','password':password}
      u=await request('POST','/users/',body)
      db.expire_all()
      self.assertEqual(db.get(m.Usuario,u['id']).email,body['email'])
      self.assertNotIn('password_hash',u)
      await request('POST','/users/',body,400)
      for invalid in [{'nombre':None},{'nombre':' '},{'nombre':'x'*101},{'rol':None},{'password':None},{'password':'é'*37}]:
       await request('PUT',f"/users/{u['id']}",invalid,422)
      await request('PUT',f"/users/{u['id']}",{'email':admin.email},409)
      await request('DELETE',f'/users/{admin.id}',code=409)
      await request('PUT',f'/users/{admin.id}',{'rol':'Docente'},409)
      teacher_login=await client.post('/auth/login',data={'username':body['email'],'password':password})
      self.assertEqual(teacher_login.status_code,200)
      teacher_token=teacher_login.json()['access_token']
      await request('PUT',f"/users/{u['id']}",{'rol':'Orientador','apellido':'Corregido'})
      db.expire_all();self.assertEqual(db.get(m.Usuario,u['id']).apellido,'Corregido')
      await request('DELETE',f"/users/{u['id']}")
      db.expire_all();self.assertFalse(db.get(m.Usuario,u['id']).activo)
      r=await client.get('/auth/me',headers={'Authorization':'Bearer '+teacher_token});self.assertEqual(r.status_code,400)
      await request('PUT',f"/users/{u['id']}",{'activo':True})
      r=await client.get('/users/',headers={'Authorization':'Bearer '+teacher_token});self.assertEqual(r.status_code,403)
      r=await client.get('/tareas/contexto',headers={'Authorization':'Bearer '+teacher_token});self.assertEqual(r.status_code,403)
      self.assertEqual((await request('GET','/health'))['database'],'connected')
      cors=await client.options('/auth/login',headers={'Origin':'http://127.0.0.1:5173','Access-Control-Request-Method':'POST'})
      self.assertEqual(cors.headers['access-control-allow-origin'],'http://127.0.0.1:5173')
    finally:app.dependency_overrides.clear();db.close();tx.rollback()
  asyncio.run(run())

 def test_database_failure_health(self):
  async def run():
   db=Mock();db.execute.side_effect=OperationalError('SELECT 1',{},Exception('private connection details'))
   app.dependency_overrides[get_db]=lambda:db
   try:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
     r=await c.get('/health');self.assertEqual(r.status_code,503)
     self.assertEqual(r.json(),{'status':'error','database':'unavailable'})
   finally:app.dependency_overrides.clear()
  asyncio.run(run())

 def test_calendar_preserves_task_deadline(self):
  from api.escolar import editar_gestion,GestionEntrada
  from fastapi import HTTPException
  with engine.connect() as conn:
   tx=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
   try:
    admin=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
    g=m.Gestion(anio=1994,fecha_inicio=date(1994,2,1),fecha_fin=date(1994,11,30));db.add(g);db.flush()
    c=m.Curso(gestion_id=g.id,grado=1,paralelo='AUDIT');s=m.Materia(nombre='Calendario temporal');db.add_all([c,s]);db.flush()
    a=m.AsignacionDocente(curso_id=c.id,materia_id=s.id,docente_id=admin.id,vigente_desde=date(1994,2,1));db.add(a);db.flush()
    t=m.Tarea(asignacion_id=a.id,curso_id=c.id,titulo='Prueba calendario',fecha_asignacion=datetime(1994,3,1,8),fecha_limite=datetime(1994,3,15,12));db.add(t);db.flush()
    with self.assertRaises(HTTPException) as e:
     editar_gestion(g.id,GestionEntrada(anio=1994,fecha_inicio=date(1994,2,1),fecha_fin=date(1994,3,10)),db,admin)
    self.assertEqual(e.exception.status_code,409)
   finally:db.close();tx.rollback()
if __name__=='__main__':unittest.main()
