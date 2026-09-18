from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from database import get_db
from api import auth, users, escolar, asignaciones, asistencia, calificaciones, tareas

# Crear las tablas en la BD si no existen
# Aplicar migrate_v2.py de forma explícita; el arranque no modifica el esquema.

app = FastAPI(
    title="API - Sistema de Alerta Temprana (SAT)",
    description="Backend para la detección del riesgo de deserción escolar usando XGBoost",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(escolar.router)
app.include_router(asignaciones.router)
app.include_router(asistencia.router)
app.include_router(calificaciones.router)
app.include_router(tareas.router)

@app.get("/")
def read_root():
    return {"message": "Bienvenido al Sistema de Alerta Temprana - U.E. 16 de Julio"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except SQLAlchemyError:
        return JSONResponse(status_code=503,content={"status":"error","database":"unavailable"})
    return {"status": "ok", "service": "SAT Backend API", "database":"connected"}
