# Revisión del diseño final de la base de datos (actividad 19)

Revisión del 6 de noviembre de 2026 sobre la base real `alerta_temprana_v2` (MySQL 8.0.46). Todo se hizo en **solo lectura** (`information_schema`, `SHOW CREATE TABLE`, `EXPLAIN`); no se modificó la base.

## Resultado

| Elemento | Base real | `backend/models.py` | `database_schema_actual.sql` | Tesis |
|---|---|---|---|---|
| Tablas | 28 | 28 | 28 | 28 |
| Claves foráneas | 47 | 47 | 47 | 47 |
| Restricciones CHECK | 40 | 40 | 40 | — |
| Vistas / triggers | 0 / 0 | — | — | — |
| Índices (incluye PK, únicos y de FK) | 92 | — | — | — |

- **Coincidencia exacta** entre la base real, `models.py` y `database_schema_actual.sql`: las mismas columnas, tipos (incluidos UNSIGNED y los valores de cada ENUM), nulos, valores por defecto, únicos, índices, FK y CHECK.
- **Diagrama EER de MySQL Workbench** que compartió el autor: tiene las mismas 28 tablas y columnas que la base real. Workbench muestra `BIGINT` sin `UNSIGNED` y abrevia los `ENUM(...)`, pero es solo una forma de presentarlos.
- **`docs/diagrama_relaciones.mmd` estaba incompleto.** Tenía 34 relaciones y le faltaban 13: las FK compuestas (por ejemplo `calificaciones → evaluaciones (evaluacion_id, curso_id)`) y las dos de `contextos_permanencia`. **Se regeneró desde la base real** y ahora tiene las 47. La única relación 1 a 0..1 es `predicciones → alertas`, porque `prediccion_id` es único.

### CHECK por tabla (40)

`contextos_permanencia` 21 · `evaluaciones` 2 · `periodos` 2 · y uno en cada una de: `alertas`, `asignaciones_docentes`, `calificaciones`, `cortes_predictivos`, `cursos`, `entregas_tareas`, `estudiante_apoderado`, `gestiones`, `intervenciones`, `matriculas`, `modelos_predictivos`, `predicciones`, `situaciones_escolares`, `tareas`, `tokens_acceso`.

## Índices para las consultas de los dashboards

`EXPLAIN` sobre las consultas reales de `/alertas`, `/dashboard` y `/reportes`:

| Consulta | Plan | Comentario |
|---|---|---|
| Panel por gestión | `gestiones` const → `cursos` ref(gestion_id) → `matriculas` ref(curso_id) → `cortes_predictivos` ref(ix_cortes_predictivos_1) → `predicciones` eq_ref(corte_id) | Usa índices en todos los pasos. |
| Ranking dentro de una gestión | Igual, con `Using index` | Correcta. |
| Evolución por gestión (todas) | Recorre el índice de `cortes_predictivos` (≈ 790 filas) | Razonable: necesita todas las filas. |
| Listado de alertas | `alertas` type=ALL (13 filas) + hash join | Es el único recorrido completo; hoy no importa. |
| Historial de una alerta | `auditoria_cambios` ref(ix_auditoria_cambios_1) | Correcta. |

**Conclusión:** con el volumen actual no falta ningún índice. En `docs/AJUSTE_ESQUEMA_PROPUESTO.sql` se proponen 3 índices **opcionales** para cuando crezcan las alertas e intervenciones: `alertas(estado, creada_en)`, `predicciones(modelo_id, nivel, probabilidad)` e `intervenciones(alerta_id, estado)`. **No se aplicaron.** Si se aplican, hay que añadirlos también a `models.py` y regenerar `database_schema_actual.sql`.

## Tablas y columnas sin uso

| Tabla | Filas | Uso en el código | Observación |
|---|---|---|---|
| `apoderados` | 2 | Ninguno | Diseño para citaciones a la familia. |
| `estudiante_apoderado` | 0 | Ninguno | Ídem. |
| `citaciones` | 0 | Solo en la verificación de dependencias antes de borrar una matrícula | La acción "citación" se registra hoy como tipo de intervención. Enlazarla a `citaciones.intervencion_id` queda como trabajo futuro. |
| `notificaciones` | 0 | Ninguno | Envío por correo o boleta: trabajo futuro. |
| `tokens_acceso` | 0 | Ninguno | Activación o recuperación de cuenta: trabajo futuro. |
| `asistencias`, `jornadas_clase` | 0 | Sí (pantalla de asistencia diaria) | Sin datos reales cargados: el modelo usa las faltas del cuaderno (corte T1). |
| `contextos_permanencia`, `registros_convivencia` | 0 | Sí | Sin datos reales recabados. |

Columnas sin referencia en el código: `evaluaciones.ponderacion`, `predicciones.generada_en` (se llena por DEFAULT), `contextos_permanencia.ventana_desde` e `instrumento_version`, y `registros_convivencia.categoria`.

**No se propone eliminar nada.** Quitar tablas o columnas sería destructivo y rompería la correspondencia con el diseño de la tesis (28 tablas y 47 FK).

## Estado de los datos (informativo)

- `matriculas`: 940 en total, 790 REAL y 150 SIMULADO. La limpieza de las simuladas la ejecuta el autor (`seeds/LIMPIEZA_DATOS_SIMULADOS.sql`).
- `predicciones` 790, `alertas` 13, `intervenciones` 0, `auditoria_cambios` 39, `modelos_predictivos` 1.

## Cómo repetir la verificación

Desde `backend`, en solo lectura:

```powershell
python -c "from sqlalchemy import inspect; from database import engine; i=inspect(engine); print(len(i.get_table_names()), sum(len(i.get_foreign_keys(t)) for t in i.get_table_names()))"
```

Debe imprimir `28 47`.
