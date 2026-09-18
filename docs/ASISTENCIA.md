# Asistencia diaria

Acceso en el menú y panel: `/asistencia`. Administración y dirección gestionan todos los cursos. Un docente ve cursos que se le asignaron y solo consulta o registra fechas dentro de su vigencia. Ser asesor de curso por sí solo no sustituye a la asignación docente.

Seleccionar curso y fecha y pulsar Consultar lista. Se muestran únicamente estudiantes con matrícula vigente ese día. Consultar no crea registros. Se puede marcar cada estudiante o usar Marcar pendientes como presentes y ajustar las excepciones. Los estados son Presente, Falta, Atraso y Licencia. La justificación puede estar confirmada, rechazada o pendiente; no se infiere automáticamente del estado.

Se permiten listas parciales. Un estudiante sin estado permanece sin registro y no se convierte en falta. Una asistencia guardada puede corregirse con un motivo, pero no borrarse volviendo a sin registro. La auditoría conserva antes/después, responsable y fecha. El formulario avisa antes de abandonar cambios sin guardar.

Administración y dirección pueden registrar un día sin clases con su motivo. No se crean asistencias ese día; un día que ya tiene asistencias requiere revisión del historial antes de convertirse en no lectivo. No se infieren feriados ni fines de semana automáticamente. La selección de una fecha anterior permite consultar y corregir su lista. No se permite guardar fechas futuras.

La lista se guarda en una transacción. Una revisión calculada sobre lista, matrículas y jornada detecta cambios desde la consulta. Si otro usuario guardó o cambió la lista, se responde 409 y se solicita recargar, sin sobrescribirlo. Se bloquean curso/gestión y se usan lecturas actuales al validar para serializar escrituras concurrentes de la jornada.

API: GET `/asistencia/cursos`; GET y PUT `/asistencia/{curso_id}/{fecha}`. PUT exige una revisión y la lista de todas las matrículas mostradas; los estados sin registrar se envían como null. No admite estudiantes fuera del curso/fecha ni duplicados. No se requiere migración nueva.

Pruebas: `python -m unittest test_database_v2 test_escolar test_asignaciones test_asistencia -v`. Los datos de integración se revierten. La prueba visual del formulario usa respuestas interceptadas, sin insertar datos de demostración en MySQL.
