"""Flujo HTTP real contra MySQL, con todas las escrituras revertidas."""
import asyncio
import unittest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import httpx
from database import engine, get_db
from api.auth import get_current_user
from main import app
import models as m


class EscolarTests(unittest.TestCase):
    def test_crud_validation_permissions_and_audit(self):
        async def run():
            with engine.connect() as conn:
                tx=conn.begin()
                db=Session(bind=conn,join_transaction_mode='create_savepoint')
                user=db.scalar(select(m.Usuario).where(m.Usuario.rol=='Admin'))
                app.dependency_overrides[get_db]=lambda:db
                app.dependency_overrides[get_current_user]=lambda:user
                try:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                        async def post(path,body,status=201):
                            r=await client.post('/escolar/'+path,json=body)
                            self.assertEqual(r.status_code,status,r.text)
                            return r.json()
                        for path in ['gestiones','cursos','estudiantes','matriculas','docentes']:
                            r=await client.get('/escolar/'+path)
                            self.assertEqual(r.status_code,200,r.text)
                        # Missing calendars and inconsistent dates are not silently accepted.
                        await post('gestiones',{'anio':2097,'fecha_inicio':'2097-12-01','fecha_fin':'2097-01-01'},422)
                        g=await post('gestiones',{'anio':2097,'fecha_inicio':'2097-02-01','fecha_fin':'2097-11-30'})
                        await post('gestiones',{'anio':2097,'fecha_inicio':'2097-02-01','fecha_fin':'2097-11-30'},409)
                        c=await post('cursos',{'gestion_id':g['id'],'grado':3,'paralelo':'a'})
                        self.assertEqual(c['paralelo'],'A')
                        await post('cursos',{'gestion_id':g['id'],'grado':3,'paralelo':'A'},409)
                        await post('cursos',{'gestion_id':g['id'],'grado':7,'paralelo':'B'},422)
                        s=await post('estudiantes',{'nombre':'Prueba temporal','apellido':'Transacción','codigo_rude':'TEST-ROLLBACK-2097'})
                        s2=await post('estudiantes',{'nombre':'Otro','apellido':'Temporal'})
                        await post('estudiantes',{'nombre':' ','apellido':'Temporal'},422)
                        await post('estudiantes',{'nombre':'Duplicado','apellido':'Temporal','codigo_rude':'TEST-ROLLBACK-2097'},409)
                        r=await client.put('/escolar/estudiantes/'+str(s['id']),json={'nombre':'Prueba editada','apellido':'Transacción','codigo_rude':'TEST-ROLLBACK-2097'})
                        self.assertEqual(r.status_code,200,r.text)
                        self.assertEqual(r.json()['codigo_anonimo'],s['codigo_anonimo'])
                        body={'estudiante_id':s['id'],'curso_id':c['id'],'fecha_ingreso':'2097-02-02','origen':'SIMULADO'}
                        await post('matriculas',{**body,'fecha_ingreso':'2097-01-01'},422)
                        enrollment=await post('matriculas',body)
                        await post('matriculas',body,409)
                        other=await post('cursos',{'gestion_id':g['id'],'grado':3,'paralelo':'B'})
                        await post('matriculas',{**body,'curso_id':other['id']},409)
                        r=await client.put('/escolar/matriculas/'+str(enrollment['id']),json={**body,'fecha_fin':'2097-03-31'})
                        self.assertEqual(r.status_code,200,r.text)
                        await post('matriculas',{**body,'curso_id':other['id'],'fecha_ingreso':'2097-04-01'})
                        r=await client.put('/escolar/cursos/'+str(c['id']),json={'gestion_id':g['id'],'grado':4,'paralelo':'A'})
                        self.assertEqual(r.status_code,409,r.text)
                        r=await client.put('/escolar/gestiones/'+str(g['id']),json={'anio':2097,'fecha_inicio':'2097-03-01','fecha_fin':'2097-11-30'})
                        self.assertEqual(r.status_code,409,r.text)
                        pending=m.Gestion(anio=2096)
                        db.add(pending);db.flush()
                        pc=await post('cursos',{'gestion_id':pending.id,'grado':1,'paralelo':'Z'})
                        await post('matriculas',{**body,'curso_id':pc['id'],'fecha_ingreso':'2096-02-01'},422)
                        self.assertGreater(db.scalar(select(func.count()).select_from(m.AuditoriaCambio).where(m.AuditoriaCambio.tabla_afectada=='matriculas')),0)
                        app.dependency_overrides[get_current_user]=lambda:m.Usuario(id=user.id,rol='Docente',activo=True)
                        self.assertEqual((await client.get('/escolar/estudiantes')).status_code,403)
                        self.assertEqual((await client.post('/escolar/gestiones',json={'anio':2095,'fecha_inicio':'2095-01-01','fecha_fin':'2095-12-31'})).status_code,403)
                        app.dependency_overrides[get_current_user]=lambda:m.Usuario(id=user.id,rol='Director',activo=True)
                        self.assertEqual((await client.get('/escolar/docentes')).status_code,200)
                finally:
                    app.dependency_overrides.clear();db.close();tx.rollback()
        asyncio.run(run())

if __name__=='__main__':unittest.main()
