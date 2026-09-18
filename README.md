# Sistema de Alerta Temprana — U.E. 16 de Julio

Aplicación escolar con Vue 3, FastAPI y MySQL. Incluye usuarios, gestiones, cursos, estudiantes, matrículas, materias, asignaciones docentes, calificaciones, asistencias y tareas. El modelo XGBoost y los módulos de intervención siguen pendientes; consulta docs/REVISION_INTEGRAL.md.

## Ejecutar localmente

1. Instalar Python 3.12, Node.js y MySQL 8.
2. En backend, instalar dependencias con `python -m pip install -r requirements.txt`.
3. Preparar un esquema vacío con database_schema.sql y los ajustes documentados en docs/VARIABLES_PERMANENCIA.md. No ejecutar scripts de creación sobre una base con datos sin revisar su contenido.
4. Configurar DATABASE_URL o backend/.database-url con la conexión privada a MySQL. Ejemplo de formato: `mysql+pymysql://USUARIO:CONTRASENA@localhost/NOMBRE_BASE`.
5. Ejecutar en backend: `python -m uvicorn main:app --host 127.0.0.1 --port 8000`.
6. Ejecutar en frontend: `npm ci`, luego `npm run dev -- --host 127.0.0.1`.
7. Abrir http://localhost:5173. Se necesita un usuario previamente creado en la base; no se incluyen contraseñas iniciales.

La clave de sesión se configura con JWT_SECRET_KEY o se genera en backend/.jwt-secret. No compartir este archivo ni .database-url.

## Verificación

Desde backend: `python -m unittest discover -v`. Las pruebas necesitan una base local configurada con registros mínimos; las escrituras temporales se revierten. Desde frontend: `npm run build`.

## Qué conserva Git

Código, dependencias, estructura SQL y documentación técnica. Se excluyen conexiones privadas, claves, datos escolares, documentos personales y respaldos. Los datos de MySQL necesitan un respaldo independiente, guardado de forma privada. El proyecto local permanece completo; excluir un archivo de Git no lo elimina.

## Otro dispositivo y datos simulados

Consulta [la guía de traslado](docs/OTRO_EQUIPO.md). La estructura completa vigente está en `database_schema_actual.sql` y la carga ficticia corregida en `seeds/seed_150_estudiantes_matriculas.sql`. Las migraciones anteriores se conservan como historial.
