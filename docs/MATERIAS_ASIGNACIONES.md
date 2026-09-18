# Materias y asignaciones docentes

Admin y Director pueden crear, consultar y editar el catálogo de materias y las asignaciones desde el menú escolar. Los accesos se comprueban también en la API. El catálogo es común a todas las gestiones; cada asignación pertenece a un curso de una gestión concreta.

## Flujo

1. Registrar el nombre de la materia y su sigla opcional en Materias.
2. Completar las fechas de la gestión y registrar el curso si todavía no existen.
3. En Asignaciones, seleccionar gestión, curso, materia y un usuario Docente activo; indicar fecha inicial y, si corresponde, final.
4. Para reemplazar un docente, editar la asignación anterior y fijar su fecha final. Crear otra asignación a partir de una fecha posterior.

Esta versión contempla un responsable por materia y curso en cada fecha. Un docente puede impartir varias materias y trabajar con varios cursos. No se modelan horarios de clase ni codocencia. El docente asesor de un curso no obtiene automáticamente una asignación de materia.

No se borran asignaciones históricas. Si ya existen evaluaciones o tareas, se conserva su docente, materia y curso. Las correcciones de vigencia no pueden dejar esas actividades fuera del intervalo. Los docentes inactivos no admiten nuevas asignaciones; se permite finalizar su segmento existente sin extenderlo. Una vigencia sin fecha final termina al cierre de la gestión.

## API y pruebas

GET/POST `/escolar/materias`, PUT `/escolar/materias/{id}`.
GET/POST `/escolar/asignaciones`, PUT `/escolar/asignaciones/{id}`.

Las operaciones escriben auditoría en la misma transacción. El bloqueo de la gestión serializa las validaciones de solapamiento. No se necesita una migración nueva: se usan las tablas existentes.

Desde backend ejecutar `python -m unittest test_database_v2 test_escolar test_asignaciones -v`. Las pruebas revierten sus datos temporales. Frontend: `npm run build`.

El registro de asistencia, calificaciones y tareas se implementará después; estas asignaciones constituyen su estructura de referencia.
