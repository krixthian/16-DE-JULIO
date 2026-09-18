# Integración del rediseño en el proyecto

Se creó `alerta_temprana_v2` en la instancia local existente de MySQL 8.0.46, con 27 tablas y 45 claves foráneas. La base original `alerta_temprana_db` permanece intacta. Se conserva una copia del backend y SQL anterior en `backups/antes_bd_v2_*`.

## Qué cambió

- `database_schema.sql` contiene la nueva estructura para un esquema vacío. No debe ejecutarse sobre las tablas antiguas.
- `backend/models.py` define los 27 modelos SQLAlchemy con tipos MySQL, índices, claves compuestas y restricciones CHECK.
- `backend/migrate_v2.py` copia usuarios, estudiantes, contactos y cursos a una base nueva, verifica la estructura y luego cambia la conexión local. No altera tablas de la base anterior y rechaza sobrescribir un destino existente.
- `backend/database.py` lee `DATABASE_URL` o el archivo local `backend/.database-url`. Una variable de entorno tiene prioridad; revisar su valor si la aplicación utiliza otra base.
- El arranque de FastAPI ya no crea tablas automáticamente.
- El listado de usuarios exige administrador también en el backend. Se conserva el contrato actual de usuarios y los roles Admin, Director y Docente; se añade Orientador.
- El seed de estudiantes antiguo se deshabilitó porque utilizaba columnas eliminadas. Su código original está en la copia de seguridad.

## Adaptaciones respecto de la propuesta

Las fechas de gestiones y períodos admiten NULL mientras se completa el calendario. Los módulos académicos deberán rechazar el registro operativo si el calendario no está completo. Los usuarios creados mediante el formulario actual siguen activos y con contraseña obligatoria. La tabla de tokens está preparada, pero el flujo de invitación y envío de correo todavía no está implementado.

Se copiaron dos usuarios preservando sus hashes y roles, dos estudiantes con códigos internos LEGACY y un curso. Los contactos familiares se conservaron como apoderados. El archivo `backend/migracion_v2_pendientes.json` registra qué estudiante correspondía a qué curso y contacto en el origen. No se crearon matrículas ni relaciones familiares con fechas inventadas. Confirmar fechas de ingreso, origen REAL/SIMULADO, parentesco y vigencia del contacto antes de completarlas.

## Ejecutar

Desde `backend`, usar el entorno Python del proyecto y ejecutar `python -m uvicorn main:app --reload`. Desde `frontend`, ejecutar `npm run dev`. Reiniciar el backend que estuviera abierto antes del cambio.

`python -m unittest test_database_v2 -v` verifica estructura real, restricciones de curso y grado, y autorización HTTP. Las escrituras de prueba se revierten por transacción. El frontend conserva las pantallas existentes. No están implementadas aún las pantallas y API de registro académico ni el entrenamiento XGBoost; esta integración corresponde a la estructura de datos y compatibilidad con usuarios.

## Reversión local

Detener el backend, restaurar el backend de `backups/antes_bd_v2_*` y arrancarlo con la base original. La versión anterior de `database.py` está en esa copia. No borrar la base nueva para revertir. Los cambios realizados en v2 después de la migración no se trasladan automáticamente al esquema anterior.
