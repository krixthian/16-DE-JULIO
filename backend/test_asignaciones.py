import asyncio
import unittest
from datetime import date
import httpx
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from main import app
from database import engine,get_db
from api.auth import get_current_user
import models as m

class AsignacionesTests(unittest.TestCase):
    def test_flujo(self):
        async def run():
            with engine.connect() as conn:
                outer=conn.begin();db=Session(bind=conn,join_transaction_mode='create_savepoint')
                admin=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
                app.dependency_overrides[get_db]=lambda:db
                app.dependency_overrides[get_current_user]=lambda:admin
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                        async def req(method,path,body=None,status=201):
                            r=await client.request(method,'/escolar/'+path,json=body)
                            self.assertEqual(r.status_code,status,r.text)
                            return r.json()
                        year=m.Gestion(anio=2094,fecha_inicio=date(2094,2,1),fecha_fin=date(2094,11,30));db.add(year);db.flush()
                        course=m.Curso(gestion_id=year.id,grado=1,paralelo='TEST');db.add(course)
                        teacher=m.Usuario(nombre='Temporal',apellido='Docente',email='asignacion-test@example.invalid',rol='Docente',activo=True)
                        other=m.Usuario(nombre='Reemplazo',apellido='Docente',email='asignacion-test2@example.invalid',rol='Docente',activo=True)
                        db.add_all([teacher,other]);db.flush()
                        subject=await req('POST','materias',{'nombre':'Materia temporal 2094','sigla':'TMP'})
                        await req('POST','materias',{'nombre':'Materia temporal 2094'},status=409)
                        await req('POST','materias',{'nombre':' '},status=422)
                        await req('PUT',f"materias/{subject['id']}",{'nombre':'Materia temporal 2094','sigla':'TMP2'},200)
                        body={'curso_id':course.id,'materia_id':subject['id'],'docente_id':teacher.id,'vigente_desde':'2094-02-01'}
                        await req('POST','asignaciones',{**body,'vigente_desde':'2094-01-01'},422)
                        await req('POST','asignaciones',{**body,'docente_id':admin.id},422)
                        first=await req('POST','asignaciones',body)
                        await req('POST','asignaciones',{**body,'docente_id':other.id},409)
                        await req('PUT',f"asignaciones/{first['id']}",{**body,'vigente_hasta':'2094-05-31'},200)
                        await req('POST','asignaciones',{**body,'docente_id':other.id,'vigente_desde':'2094-05-31'},409)
                        await req('POST','asignaciones',{**body,'docente_id':other.id,'vigente_desde':'2094-06-01'})
                        period=m.Periodo(gestion_id=year.id,numero=1,fecha_inicio=date(2094,2,1),fecha_fin=date(2094,5,31));db.add(period);db.flush()
                        db.add(m.Evaluacion(asignacion_id=first['id'],curso_id=course.id,gestion_id=year.id,periodo_id=period.id,titulo='Temporal',tipo='PRUEBA',fecha_aplicacion=date(2094,5,1),puntaje_maximo=100));db.flush()
                        await req('PUT',f"asignaciones/{first['id']}",{**body,'docente_id':other.id,'vigente_hasta':'2094-05-31'},409)
                        await req('PUT',f"asignaciones/{first['id']}",{**body,'vigente_hasta':'2094-04-30'},409)
                        await req('PUT',f'gestiones/{year.id}',{'anio':2094,'fecha_inicio':'2094-03-01','fecha_fin':'2094-11-30'},409)
                        rows=await req('GET','asignaciones',status=200)
                        self.assertTrue(any(r['id']==first['id'] and r['materia_nombre']=='Materia temporal 2094' for r in rows))
                        teacher.activo=False;db.flush()
                        await req('POST','asignaciones',{**body,'vigente_desde':'2094-07-01'},422)
                        app.dependency_overrides[get_current_user]=lambda:teacher
                        await req('GET','materias',status=403)
                        await req('POST','materias',{'nombre':'Sin permiso'},403)
                        app.dependency_overrides[get_current_user]=lambda:m.Usuario(id=admin.id,rol='Director')
                        await req('GET','materias',status=200)
                        self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(m.AuditoriaCambio.tabla_afectada=='asignaciones_docentes')),0)
                finally:
                    app.dependency_overrides.clear();db.close();outer.rollback()
        asyncio.run(run())

if __name__=='__main__':unittest.main()
