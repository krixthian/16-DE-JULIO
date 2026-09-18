# Registro de calificaciones parciales

Implementado en `/calificaciones`, accesible desde el menú y panel para Admin, Director y Docente. Se utilizan las tablas existentes; no hay una migración adicional ni se insertaron trimestres o notas de demostración en la base del proyecto.

## Recorrido

1. Administración o dirección configura las fechas reales de los trimestres desde Configurar trimestres. La gestión debe tener calendario completo. Los números 1 a 3 siguen orden temporal y no pueden solaparse.
2. Seleccionar curso, materia y asignación docente y consultar sus evaluaciones. Los docentes solo pueden acceder a sus propias asignaciones, incluso mediante llamadas directas a la API.
3. Crear una evaluación indicando título, trimestre, tipo, fecha de aplicación y puntaje máximo. Dimensión es opcional y debe corresponder a la planilla institucional. La evaluación debe estar dentro del trimestre, la gestión y la vigencia docente.
4. Abrir Registrar notas. La lista incluye exclusivamente estudiantes matriculados en el curso en la fecha de aplicación.
5. Seleccionar Calificada e introducir puntaje (incluido cero), o Pendiente, No presentada o Exenta sin puntaje. Sin registrar no crea una calificación. Se permiten listas parciales.
6. Para corregir notas guardadas, indicar un motivo. Se conserva antes/después, responsable y fecha en auditoría. Una lista desactualizada se rechaza y debe recargarse.

## Límites y protección del historial

Los puntajes admiten dos decimales y deben estar entre cero y el máximo de la evaluación. No se pueden guardar notas para una evaluación futura. Consultar una lista no crea calificaciones ni ceros.

Una evaluación que ya tiene notas o tareas no permite cambiar fecha, trimestre, escala ni dimensión desde este módulo. El título y tipo pueden corregirse con motivo y revisión. No se permite trasladar evaluaciones a otra asignación ni borrar calificaciones convirtiéndolas a Sin registrar. Los trimestres no pueden modificarse dejando evaluaciones fuera de sus fechas.

La aplicación registra notas parciales. No calcula una nota trimestral oficial, aprobación/reprobación ni ponderaciones institucionales: esas reglas deben definirse con la planilla del colegio. No se generan predicciones de riesgo a partir de estas notas todavía.

## API

- GET `/calificaciones/contexto`: asignaciones, gestiones y trimestres visibles.
- POST `/calificaciones/periodos` y PUT `/calificaciones/periodos/{id}`: administración del calendario por Admin/Director.
- GET `/calificaciones/evaluaciones?asignacion_id=...`, POST `/calificaciones/evaluaciones`, PUT `/calificaciones/evaluaciones/{id}`.
- GET y PUT `/calificaciones/evaluaciones/{id}/notas`: lista y guardado transaccional, con revisión para detectar cambios concurrentes.

## Verificación

`python -m unittest test_database_v2 test_escolar test_asignaciones test_asistencia test_calificaciones -v`: siete pruebas de integración, con operaciones temporales revertidas. El flujo nuevo comprueba trimestres solapados, permisos, vigencia de matrícula, cero válido, notas ausentes, máximo, decimales, correcciones y revisiones antiguas.

`npm run build`: compilación correcta. En Chrome se revisó crear trimestre, crear evaluación y guardar cero, decimal y no presentada mediante respuestas interceptadas; esa prueba visual no escribe datos de prueba en MySQL. Las pruebas de API sí ejercitan el guardado en MySQL dentro de una transacción que se revierte.
