# Revisión integral del sistema — 17/09/2026

## Resultado
Los módulos implementados utilizan MySQL `alerta_temprana_v2`. No se detectaron listas académicas simuladas en el frontend ni almacenamiento de notas, tareas o asistencia en localStorage. El almacenamiento del navegador se usa para sesión y tema. Tener una tabla en el diagrama no significa que su módulo esté implementado.

## Conectado y probado
| Funcionalidad | API / tablas | Evidencia |
|---|---|---|
| Inicio de sesión y usuarios | /auth, /users; usuarios | Login con contraseña, sesión, permisos, alta, edición, desactivación, reactivación; lectura directa de SQL tras guardar |
| Gestiones, cursos y estudiantes | /escolar; gestiones, cursos, estudiantes | Pruebas CRUD, validación y auditoría |
| Matrículas | /escolar/matriculas; matriculas | Fechas, superposiciones, identidad e historial |
| Materias y docentes por curso | /escolar; materias, asignaciones_docentes | Vigencia, permisos, actividades y reemplazos |
| Trimestres y notas | /calificaciones; periodos, evaluaciones, calificaciones | Evaluaciones parciales, escala, fechas, permisos y correcciones |
| Asistencias | /asistencia; jornadas_clase, asistencias | Lista por matrícula, estados, justificación, días sin clases y correcciones |
| Tareas | /tareas; tareas, entregas_tareas | Plazos, estados, fecha real, entregas tardías y correcciones |
| Panel de inicio | /escolar | Contadores obtenidos de la API, sin números prefijados |
| Auditoría académica | auditoria_cambios | Escritura desde los módulos académicos; no existe visor independiente de auditoría |

## Pendiente de implementar
- `contextos_permanencia`: las 27 variables tienen tabla, modelo y pruebas de restricciones; falta API, formulario y su incorporación a indicadores predictivos.
- `registros_convivencia` y `situaciones_escolares`: estructura presente; falta registro operativo desde el sistema.
- `apoderados` y `estudiante_apoderado`: existen contactos migrados, pero no hay módulo de mantenimiento ni relaciones familiares completadas.
- `cortes_predictivos`, `modelos_predictivos`, `predicciones`, `alertas`: falta construcción de variables, entrenamiento/validación de XGBoost, predicción y presentación de alertas.
- `intervenciones`, `citaciones`, `notificaciones`: tablas preparadas; falta el flujo funcional y el envío de correo.
- `tokens_acceso`: falta invitación y recuperación de contraseña. El formulario actual crea usuarios con contraseña; no envía correos.

## Datos existentes que explican listas vacías
La consulta inicial encontró 3 usuarios, 1 gestión, 1 curso, 2 estudiantes, 2 apoderados y 1 período. Matrículas, materias y asignaciones docentes: 0. Asistencias, evaluaciones, notas, tareas y entregas: 0. Los 2 apoderados no tienen vínculos en estudiante_apoderado.
No se completaron fechas, matrículas o relaciones familiares inventadas. Para operar los módulos, registrar primero materias, asignaciones docentes y matrículas con información confirmada. El archivo backend/migracion_v2_pendientes.json conserva referencias de la migración para revisar esos vínculos.

## Correcciones realizadas
1. Usuarios: validar nombres, longitudes, valores nulos y contraseña; informar correos duplicados sin error interno; evitar autodesactivar o quitar el propio rol administrador.
2. Usuarios: mostrar fallos de carga y desactivación; agregar Orientador y opción de reactivación; impedir doble envío al guardar.
3. /health: consultar MySQL realmente y devolver 503 si falla, sin revelar detalles de conexión.
4. Conexión web: permitir también el origen local 127.0.0.1:5173 y configurar el destino API mediante VITE_API_URL.
5. Lecturas con bloqueo: refrescar objetos para no reutilizar información anterior a una modificación concurrente.
6. Calendario: impedir que una corrección deje fechas de tareas fuera de la gestión. Matrículas: incluir contextos de permanencia en la protección de historial asociado.
7. Sesión: tolerar información local mal formada. Sustituir la clave JWT fija por JWT_SECRET_KEY o backend/.jwt-secret generado localmente y excluido de Git. Las sesiones anteriores deben iniciar sesión otra vez. Las contraseñas de usuarios no cambiaron.

## Verificación y límites
- 12 pruebas aprobadas: `C:\Python312\python.exe -m unittest discover -v` desde backend. Se ejercitan API y MySQL, con datos temporales revertidos mediante transacciones. No se introdujeron alumnos o calificaciones de prueba persistentes.
- Frontend: `npm run build` aprobado.
- Auditoría de lectura: 28 tablas, 47 claves foráneas, 0 diferencias de nombres de columnas respecto a modelos, 0 relaciones huérfanas; 43 operaciones de API inventariadas. No equivale a una comparación exhaustiva de todos los tipos, índices y restricciones.
- Evidencia agregada sin información personal: docs/auditoria_conexion.json. Repetir con `python audit_system.py` desde backend.
- Se reinició el backend para aplicar las correcciones y se comprobó /health por HTTP.
- El navegador sigue en inicio de sesión. No se completó un recorrido visual autenticado, ni pruebas de carga, ni una validación con datos reales del colegio. La compilación y las pruebas de API no sustituyen esas verificaciones.
- Persiste una advertencia de obsolescencia interna en python-jose; no produjo fallos en las pruebas.

Los documentos de integración más antiguos describen etapas anteriores; este informe refleja el estado actual de los módulos revisados.
