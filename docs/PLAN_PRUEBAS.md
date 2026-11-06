# Plan y resultados de pruebas generales e integrales (actividad 20)

Sistema de alerta temprana, U.E. 16 de Julio. Ejecución del 6 de noviembre de 2026.

## Alcance y método

| Nivel | Qué se prueba | Herramienta | Datos |
|---|---|---|---|
| Unitario | Reglas de negocio, variables, validación del modelo, reglas RP | `unittest` | Ficticios |
| API / módulo | Cada router: validaciones, permisos, auditoría | `unittest` + `httpx` sobre FastAPI | SQLite temporal, ficticios |
| **Integral** | **La aplicación completa (`main.app`)**: matriz de permisos de los 58 endpoints × 4 roles, acceso sin sesión y flujo de punta a punta | `backend/test_integral.py` | SQLite temporal, ficticios |
| Esquema | `models.py` = SQL = diagrama (28 tablas, 47 FK, 40 CHECK) | `backend/test_esquema.py` | — |
| **Integral sobre MySQL** | El mismo flujo de punta a punta sobre MySQL 8, con FK y CHECK reales | `backend/test_integral_mysql.py` | Base desechable `alerta_temprana_v2_pruebas`, ficticios |
| Sistema (manual) | Pantallas reales con la base real, en el navegador | Revisión visual y capturas | Base real (solo lectura) |
| Reproducibilidad | Métricas del modelo y del ajuste | `python -m predictivo metricas-real / metricas-ajuste --excel` | Dataset real anonimizado |

Ninguna prueba automática usa la base real ni datos personales. Comandos (desde `backend`):

```powershell
python -m unittest discover -p "test_*.py"
$env:MYSQL_PRUEBAS_DB = "alerta_temprana_v2_pruebas"; python -m unittest test_integral_mysql -v
```

La prueba sobre MySQL solo corre si la base indicada termina en `_pruebas` y está vacía. Se crea con `database_schema_actual.sql` cambiando el nombre de la base, y nunca toca `alerta_temprana_v2`.

## Casos por actividad del cronograma

| N.º | Actividad | Casos automáticos (archivo › prueba) | Verificación manual | Resultado |
|---|---|---|---|---|
| 1-2 | Arquitectura y modelado de la base | `test_database_v2` › estructura, CHECK y FK de curso; `test_esquema` (4) | Comparación con la base real y con el EER de Workbench (`docs/REVISION_ESQUEMA_BD.md`) | ✅ |
| 3 | Autenticación | `test_system` › auth y lecturas; `test_predictivo_api` › rutas requieren autenticación; `test_integral` › 401 sin sesión en todos los endpoints protegidos, login inválido 401, token falso 401 | Inicio de sesión real del autor | ✅ |
| 4 | Usuarios y roles | `test_system`; `test_database_v2` › permisos y tokens; `test_integral` › matriz 58 endpoints × 4 roles | Menú lateral según rol | ✅ |
| 5 | Estudiantes y cursos | `test_escolar` › CRUD, validación, permisos y auditoría; `test_asignaciones` › flujo | — | ✅ |
| 6 | Calificaciones | `test_calificaciones` › periodos, evaluaciones y notas | — | ✅ |
| 7 | Asistencias | `test_asistencia` › registro diario | Sin datos reales de asistencia diaria (0 filas) | ✅ (funcional) |
| 8 | Tareas | `test_tareas` › tareas, entregas, permisos e historial; `test_system` › calendario | — | ✅ |
| 9-10 | Consolidación y limpieza de datos | `test_predictivo` › escalas, duplicados, origen, notas inválidas | 790 matrículas reales cargadas; limpieza de 150 SIMULADO pendiente del autor | ⚠️ limpieza pendiente |
| 11 | Variables de riesgo | `test_predictivo` (13); `test_alertas` › columnas POST_* nunca son variables | — | ✅ |
| 12 | Entrenamiento base XGBoost | `test_alertas` › pliegues sin estudiantes compartidos, umbral de regla con entrenamiento; `test_predictivo` › guardar/recargar | `metricas-real --excel`: "métricas reproducidas exactamente" | ✅ |
| 13 | Ajuste de hiperparámetros | `test_ajuste` (5) | `metricas-ajuste --excel`: "ajuste reproducido exactamente" | ✅ |
| 14 | Integración del modelo | `test_predictivo_api` › registro de modelo; `test_alertas` › generación idempotente | 790 predicciones y 13 alertas en la base real | ✅ |
| 15 | Alertas de riesgo | `test_alertas` › estados, filtros, responsable, ranking, auditoría | Capturas 15a-15c | ✅ |
| 16 | Recomendaciones | `test_alertas` › reglas RP y registro de ejecución | Captura 16a | ✅ |
| 17 | Dashboards | `test_alertas` › agregados = base | Capturas 17a-17b | ✅ |
| 18 | Reportes | `test_alertas` › reportes anonimizados y filtrados | Endpoints 200 con datos reales; PDF/CSV de ejemplo 18b-18c | ✅ |
| 19 | Diseño final de la base | `test_esquema` (4) | `docs/REVISION_ESQUEMA_BD.md` | ✅ |
| 20 | Pruebas integrales | `test_integral` (3); `test_integral_mysql` (1, sobre MySQL) | Este documento | ✅ |

## Prueba integral de punta a punta (`test_end_to_end_follow_up_workflow`)

1. Se entrena un modelo con datos ficticios, se registra y se generan predicciones y alertas.
2. **Orientación** lista las alertas: la primera tiene el puesto 1 del ranking. La asume (responsable, EN_REVISION), registra la recomendación RP activa y la lleva por APROBADA → EN_CURSO → REALIZADA (citación, fecha y resultado). Luego cierra la alerta con motivo; una alerta cerrada ya no acepta intervenciones (409).
3. **Dirección** ve en el panel 1 intervención ejecutada y 1 alerta cerrada, y descarga el CSV (que incluye la acción ejecutada) y el PDF.
4. El historial tiene al menos 6 registros de auditoría (alerta e intervención).
5. **Docente** recibe 403 en alertas, panel e historial.

## Matriz de permisos verificada

| Módulo | Admin | Director | Orientador | Docente |
|---|---|---|---|---|
| `/users` | ✅ | 403 | 403 | 403 |
| `/escolar/*`, `/predictivo/*`, `/calificaciones/periodos` | ✅ | ✅ | 403 | 403 |
| `/asistencia`, `/calificaciones`, `/tareas` | ✅ | ✅ | 403 | ✅ (solo sus asignaciones) |
| `/alertas`, `/intervenciones`, `/dashboard`, `/reportes` | ✅ | ✅ | ✅ | 403 |
| `/auth/me` | ✅ | ✅ | ✅ | ✅ |
| Sin sesión, cualquier endpoint protegido | 401 | | | |

## Resultados

- **Pruebas automáticas:** ver `docs/figuras/evidencia_terminal/20_tests_backend.txt`.
- **Frontend:** `npm run build` sin errores.
- **Prueba sobre MySQL (6/11/2026):** la base de pruebas se creó con `database_schema_actual.sql` (28 tablas, 47 FK, 40 CHECK, sin errores). El flujo completo pasó: 80 predicciones, 10 alertas (1 cerrada), 1 intervención REALIZADA (`RP01@RP-v1`, citación, fecha y resultado) y 6 registros de auditoría. La base real siguió sin cambios (940 matrículas, 13 alertas, 0 intervenciones). Evidencia: `docs/figuras/evidencia_terminal/20_flujo_mysql_pruebas.txt`.
- **Hallazgos:** ninguno de la aplicación. Se corrigieron tres supuestos de los propios tests:
  1. El login con credenciales falsas responde 401 (correcto).
  2. Crear o editar trimestres está reservado a Admin y Director (correcto).
  3. Los datos ficticios insertaban cursos antes que su gestión. SQLite no lo detecta y MySQL sí, porque valida las FK. Se ordenaron las inserciones del test; la aplicación ya guarda registro por registro.

## Limitaciones (lo que estas pruebas no cubren)

- **Frontend:** no hay pruebas automáticas de navegador. Las pantallas se verificaron manualmente con el usuario Admin. Los roles Director, Orientador y Docente se verificaron en la API, no en el navegador.
- **Rendimiento y carga:** no se midieron. El volumen actual es bajo (790 predicciones).
- **Aceptación:** pendiente con Dirección y docentes, junto con la validación de los umbrales y las reglas RP.
