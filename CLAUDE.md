# Proyecto: Sistema de alerta temprana (XGBoost), U.E. 16 de Julio

Proyecto de grado: predice el riesgo de abandono escolar en primaria (La Paz) al cierre del 1.er trimestre. Stack: FastAPI + SQLAlchemy/PyMySQL (`backend/`), Vue 3 + Tailwind + Chart.js (`frontend/`), MySQL 8 (base `alerta_temprana_v2`: 30 tablas, 54 FK, 43 CHECK desde el 22/11/2026, con asistencia por materia y citaciones con origen: `docs/AMPLIACION_ASISTENCIA_POR_MATERIA.sql`). **Desde el 22/11/2026 el sistema usa `alerta_temprana_v3`**: copia de v2 con los registros completos de la institución 2021-2025 (1889 matrículas, notas T1-T3 y 306.917 días de asistencia), cargados con `backend/predictivo/cargar_institucion_v3.py`. v2 queda intacta (versión parcial); para volver a ella, copiar `backend/.database-url.v2` sobre `backend/.database-url` (ambos fuera de Git). Respaldo previo: `Desktop/RESPALDOS_BD/alerta_temprana_v2_antes_v3_20261122.sql`. Rama de trabajo: `mejoras-alertas` (la más completa; respaldo previo en la rama `version-preliminar-defensa` y la etiqueta `v0.9-preliminar`). El estado detallado está en `RESUMEN_PARA_CHAT.md` (fuera de Git) y en `docs/`.

## Reglas del autor (obligatorias)

- **Base de datos:** no ejecutar DELETE, TRUNCATE, DROP ni cambios destructivos sin confirmación expresa. Antes de escribir en la base, mostrar qué se va a insertar y esperar el OK. La limpieza de datos simulados (`seeds/LIMPIEZA_DATOS_SIMULADOS.sql`) la ejecuta el autor.
- **Credenciales:** no escribir contraseñas ni claves. El login lo hace el autor.
- **Privacidad:** sin nombres, RUDE ni datos personales **de estudiantes** en pantallas, reportes, commits o capturas; se muestran como "Estudiante 0042". El nombre del usuario admin (el autor) sí puede aparecer en capturas.
- **Modelo:** prohibido usar columnas `POST_*` (T2, T3, anual) como predictores, porque son fuga de información.
- **Validación:** siempre agrupada por estudiante, con IC por bootstrap y comparación contra baselines. No elegir a posteriori el resultado más favorable ni ajustar umbrales con los datos de evaluación. Solo hay 11 abandonos: no inflar métricas.
- **Probabilidades:** no están calibradas; presentarlas como ranking de prioridad, no como riesgo absoluto. Los umbrales MEDIO ≥ 0,5 y ALTO ≥ 0,8 son una propuesta pendiente de validar con Dirección.
- **No inventar datos:** todo lo que se muestre debe salir de la base.
- **Al terminar cada actividad:** tests, `npm run build`, evidencia en `docs/figuras/evidencia_terminal/` y `evidencia_pantalla/`, y confirmar con el autor.

## Modelo vigente: seguimiento continuo

- `backend/predictivo/seguimiento.py` (artefactos en `backend/artifacts/seguimiento_mensual_v1/`): un XGBoost por fin de mes (15 variables, solo con lo registrado hasta la fecha) y la alerta inmediata de 5 faltas seguidas. Endpoint `GET /alertas/seguimiento?gestion=&fecha=` (solo lectura); pestaña "Seguimiento a la fecha" en Alertas.
- Para gestiones pasadas usa el modelo entrenado SIN esa gestión. Reentrenar: `python -m predictivo.seguimiento entrenar` (desde `backend`).
- El modelo de corte único al 30 de abril (`real_t1_v1`, AP 0,86) se entrenó con la versión parcial; con los registros completos no anticipa (AP 0,008 frente a 0,006 del azar). No presentarlo como resultado vigente.

## Comandos

- **Backend:** desde `backend`, `python -m unittest discover -p "test_*.py"` (54 tests, unos 25 minutos; la prueba sobre MySQL se omite salvo que se defina `MYSQL_PRUEBAS_DB`).
- **Frontend:** `npm --prefix frontend run build`.
- **Reproducibilidad del modelo** (desde `backend`): `python -m predictivo metricas-real --directorio artifacts/real_t1_v1 --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx` y `python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1`.
- **Servidores:** ver `.claude/launch.json` (backend en 127.0.0.1:8000, frontend en 5173).
- **Instalación en otro equipo:** `docs/OTRO_EQUIPO.md`.
