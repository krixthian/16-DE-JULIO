# Gestiones, cursos, estudiantes y matrículas

Implementados en la API `/escolar` y en las cuatro pantallas `/escolar/gestiones`, `/escolar/cursos`, `/escolar/estudiantes` y `/escolar/matriculas`.

## Uso

Ingresar como Admin o Director. El panel muestra cantidades consultadas de la base y accesos a los módulos. El menú lateral también permite abrirlos. Los docentes y orientadores no tienen acceso a la administración general de estudiantes.

1. En Gestiones, editar 2026 y completar las fechas reales del calendario. También se pueden registrar otras gestiones.
2. En Cursos, crear grados/paralelos y seleccionar opcionalmente un docente asesor activo. El grado está limitado a primaria.
3. En Estudiantes, registrar nombres, apellidos y opcionalmente RUDE y nacimiento. El identificador interno se genera automáticamente y se conserva al editar.
4. En Matrículas, seleccionar estudiante y curso, fechas y origen REAL/SIMULADO. Una fecha final vacía significa permanencia hasta el fin de la gestión, no ausencia de límite temporal.

Las tablas tienen búsqueda, paginación y filtros de gestión donde corresponde. Los formularios permiten crear y editar; no hay borrado de historial. Para cambiar de curso se cierra el segmento anterior y se crea otro con fechas posteriores. Un cierre de matrícula no confirma abandono. Si una matrícula ya tiene registros académicos, la edición se bloquea hasta disponer del flujo específico de revisión del historial.

## Validaciones y permisos

- Fechas completas de calendario, ordenadas y pertenecientes al año indicado.
- Matrícula dentro del calendario, posterior al nacimiento y sin solapamiento con otra del estudiante. El estudiante y la gestión se bloquean transaccionalmente al verificar el solapamiento.
- Año, curso por grado/paralelo y RUDE únicos, respetando las restricciones de MySQL.
- No cambiar la identidad de un curso que tenga registros ni estudiante/curso de una matrícula existente.
- Auditoría en la misma transacción que cada alta o edición.
- Permisos de Admin/Director en la API, además de la navegación. El selector de asesores solo expone identificador y nombre de docentes activos.

## Verificación

Desde backend: `python -m unittest test_database_v2 test_escolar -v`.

Las pruebas HTTP ejecutan altas, ediciones, errores de duplicado, límites de fechas, cambios de curso y permisos contra MySQL. Utilizan una transacción exterior que revierte los registros temporales. El frontend se compila con `npm run build` y se revisó en Chrome: panel, cuatro pantallas, apertura de formularios y visualización de errores de guardado.

La API se inicia desde backend con `python -m uvicorn main:app --reload`; el frontend desde frontend con `npm run dev`. No es necesario ejecutar de nuevo la migración ni recrear la base. Esta entrega no incluye el registro de asistencia, notas, tareas, apoderados ni entrenamiento XGBoost.
