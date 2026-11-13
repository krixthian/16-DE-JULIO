# Proyecto: Sistema de alerta temprana (XGBoost), U.E. 16 de Julio

Proyecto de grado: predice el riesgo de abandono escolar en primaria (La Paz) al cierre del 1.er trimestre. Stack: FastAPI + SQLAlchemy/PyMySQL (`backend/`), Vue 3 + Tailwind + Chart.js (`frontend/`), MySQL 8 (base `alerta_temprana_v2`: 28 tablas, 47 FK, 40 CHECK). Rama de trabajo: `recomendaciones-ingeniero`. El estado detallado está en `RESUMEN_PARA_CHAT.md` (fuera de Git) y en `docs/`.

## Reglas del autor (obligatorias)

- **Base de datos:** no ejecutar DELETE, TRUNCATE, DROP ni cambios destructivos sin confirmación expresa. Antes de escribir en la base, mostrar qué se va a insertar y esperar el OK. La limpieza de datos simulados (`seeds/LIMPIEZA_DATOS_SIMULADOS.sql`) la ejecuta el autor.
- **Credenciales:** no escribir contraseñas ni claves. El login lo hace el autor.
- **Privacidad:** sin nombres, RUDE ni datos personales **de estudiantes** en pantallas, reportes, commits o capturas; se muestran como "Estudiante 0042". El nombre del usuario admin (el autor) sí puede aparecer en capturas.
- **Modelo:** prohibido usar columnas `POST_*` (T2, T3, anual) como predictores, porque son fuga de información.
- **Validación:** siempre agrupada por estudiante, con IC por bootstrap y comparación contra baselines. No elegir a posteriori el resultado más favorable ni ajustar umbrales con los datos de evaluación. Solo hay 11 abandonos: no inflar métricas.
- **Probabilidades:** no están calibradas; presentarlas como ranking de prioridad, no como riesgo absoluto. Los umbrales MEDIO ≥ 0,5 y ALTO ≥ 0,8 son una propuesta pendiente de validar con Dirección.
- **No inventar datos:** todo lo que se muestre debe salir de la base.
- **Al terminar cada actividad:** tests, `npm run build`, evidencia en `docs/figuras/evidencia_terminal/` y `evidencia_pantalla/`, y confirmar con el autor.

## Comandos

- **Backend:** desde `backend`, `python -m unittest discover -p "test_*.py"` (54 tests, unos 25 minutos; la prueba sobre MySQL se omite salvo que se defina `MYSQL_PRUEBAS_DB`).
- **Frontend:** `npm --prefix frontend run build`.
- **Reproducibilidad del modelo** (desde `backend`): `python -m predictivo metricas-real --directorio artifacts/real_t1_v1 --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx` y `python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1`.
- **Servidores:** ver `.claude/launch.json` (backend en 127.0.0.1:8000, frontend en 5173).
- **Instalación en otro equipo:** `docs/OTRO_EQUIPO.md`.
