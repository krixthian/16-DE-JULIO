# Asistencias y seguimiento de tareas

Implementación verificada el 17 de septiembre de 2026.

## Acceso
Iniciar sesión en http://localhost:5173. Menú: Control de asistencias y Seguimiento de tareas. Admin y Director pueden gestionar todos los cursos; Docente solo sus asignaciones. Se usan las tablas existentes de MySQL; no requiere migración adicional.

## Asistencias
Seleccionar curso y fecha, consultar la lista de matrículas vigentes y registrar presente, falta, atraso o licencia. Las justificaciones y correcciones quedan registradas. Dirección puede indicar días no lectivos. Una fila sin registrar no se interpreta como falta.

## Tareas
1. Elegir curso y materia y pulsar Consultar tareas. Requiere una asignación docente y el calendario de la gestión.
2. Crear tarea con título, fecha y hora de asignación y plazo.
3. Abrir Ver entregas y registrar cada estudiante: Pendiente, Entregada, No entregada o Exenta.
4. Para Entregada, indicar la fecha real. Se identifica si llegó fuera de plazo. No entregada solo se admite después del vencimiento.
5. Guardar seguimiento. Modificar registros anteriores requiere motivo de corrección. Las modificaciones concurrentes se rechazan para evitar sobreescribir información.

La lista corresponde a matrículas vigentes en la fecha de asignación. Sin registro no equivale a incumplimiento. Cuando existen entregas registradas, las fechas y la evaluación asociada se conservan para proteger el historial. Las tareas no modifican automáticamente las calificaciones. Las fechas usan hora local sin zona horaria; el servidor debe operar con la hora del colegio.

## Verificación
Backend: python -m unittest test_database_v2 test_contextos test_escolar test_asignaciones test_asistencia test_calificaciones test_tareas -v
Resultado: nueve pruebas aprobadas en MySQL. Incluyen permisos, matrículas, plazos, entregas tardías, validaciones, revisiones y auditoría. Los datos temporales se revierten mediante transacciones.
Frontend: npm run build, correcto.
Navegador: servidor iniciado y pantalla de inicio de sesión accesible. La revisión visual de las pantallas protegidas requiere una sesión del usuario.

Archivos principales nuevos: backend/api/tareas.py, backend/test_tareas.py, frontend/src/views/TasksView.vue. Integración en main.py, router, menú e inicio. El módulo de asistencias existente se verificó con su prueba funcional.

## Automatización de estados
Las tareas nuevas crean registros Pendiente para las matrículas de la fecha de asignación. Las tareas anteriores conservan sus registros. Al vencer el plazo, Pendiente se presenta como Vencida, por revisar, calculado al consultar y actualizado en pantalla. No se almacena como incumplimiento. Confirmar por primera vez una pendiente no exige motivo; corregir un estado confirmado sí. Al seleccionar Entregada se completa fecha y hora local actual, editable antes de guardar.
