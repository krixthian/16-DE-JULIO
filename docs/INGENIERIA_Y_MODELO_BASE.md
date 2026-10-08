# Tareas 11 y 12: indicadores y entrenamiento base

Implementación del 8 de octubre de 2026. El corte inicial acordado es el **31 de marzo**, con objetivo de abandono confirmado después del corte y hasta el final de la misma gestión.

## Alcance implementado

- Servicio reutilizable `backend/predictivo/features.py`: 48 variables numéricas, incluidas las 27 observaciones de contexto del esquema.
- Lectura de las tablas de MySQL o del JSON de tablas fuente utilizado para generar el Excel simulado. No importa ese Excel automáticamente a MySQL.
- API de consulta y guardado de cortes para Admin y Director. El entrenamiento se ejecuta por consola, fuera de las peticiones web.
- XGBoost base, artefacto JSON recargable, reporte de métricas, diccionario y manifiesto de particiones.
- Registro opcional de metadatos en `modelos_predictivos`. No activa el modelo, no crea predicciones ni alertas.

No se modificó el esquema SQL. Los formularios de contexto, convivencia y situaciones escolares siguen pendientes. El servicio puede consumir esas tablas cuando estén pobladas por un proceso autorizado.

## Contrato de los indicadores

Los identificadores sirven para relacionar registros y separar estudiantes; no son variables de entrenamiento. No se utilizan nombres, RUDE, teléfonos, correos, descripciones libres ni datos económicos o laborales.

| Grupo | Cálculos |
|---|---|
| Asistencia | Jornadas configuradas, observaciones, cobertura, faltas, faltas explícitamente injustificadas, atrasos y máxima racha de faltas. |
| Calificaciones | Cantidad, media simple normalizada sobre 100, proporción menor a 51 y cambio entre primera/última fecha por materia cuando existe historial. |
| Tareas | Vencidas no exentas, cobertura de confirmación, entregas, no entregadas confirmadas, retrasos y casos por revisar. |
| Convivencia | Cantidad de incidentes registrados. No disponer de incidentes no demuestra ausencia de problemas. |
| Contexto | Disponibilidad y antigüedad de la ficha más reciente; sus 27 variables, manteniendo los valores desconocidos. |

Las tasas son proporciones entre 0 y 1. Una división sin denominador produce un valor ausente, no cero. El promedio normalizado es un indicador analítico; no reemplaza el promedio oficial ponderado del colegio. El umbral 51 es un parámetro técnico de esta primera versión y requiere ratificación institucional.

Suficiencia técnica inicial: al menos 5 asistencias, cobertura de jornadas configuradas de 0,8, una nota y una tarea vencida confirmada. Estos valores no son umbrales validados de riesgo. Una matrícula terminada queda fuera de seguimiento. Esta política está versionada como `primaria-marzo-v1`.

El diccionario completo se obtiene con `GET /predictivo/variables` o en `diccionario.json` al preparar datos.

## Fechas y prevención de información futura

- Fechas escolares locales, con resolución de segundos igual que los campos DATETIME de MySQL; el corte termina a las 23:59:59.
- Se consideran las fechas de los hechos y sus fechas de registro. Una nota ingresada después del corte no se utiliza como si hubiera estado disponible antes.
- Se revierten en memoria las correcciones/altas auditadas posteriores al corte. La base de datos no se modifica durante esta reconstrucción.
- Una importación o corrección directa sin auditoría puede impedir reconstruir el estado histórico. No se inventa el valor anterior. Los registros importados requieren procedencia y fechas verificables.
- Una ficha de contexto es completa, no un parche: no se rellenan sus vacíos copiando datos de fichas anteriores.
- Los cortes guardados conservan versión y origen. Repetir el mismo corte devuelve el existente; intentar sobrescribirlo con indicadores distintos produce conflicto.
- El calendario configurado puede ser incompleto. La cobertura calculada no demuestra que todas las jornadas oficiales estén cargadas.

## Etiquetas y particiones

`1`: abandono confirmado después del corte y antes o al final de la gestión. `0`: continuidad confirmada con seguimiento hasta fin de gestión. Se excluyen traslados, cambios de curso, reingresos, otros resultados, abandono previo al corte, resultados contradictorios y seguimiento insuficiente.

Las etiquetas y su fecha de disponibilidad se guardan aparte de las 48 variables. No se mezclan orígenes REAL y SIMULADO. Los resultados posteriores al límite de observación no se utilizan.

La última gestión elegida se reserva para evaluación. El entrenamiento utiliza gestiones anteriores y elimina a los estudiantes presentes en la evaluación. Además exige que las etiquetas de entrenamiento ya estuvieran disponibles antes del corte de evaluación. La purga reduce la muestra y puede cambiar su distribución, por lo que debe revisarse con los datos reales.

El modelo utiliza 80 árboles, profundidad 3, tasa de aprendizaje 0,05 y semilla 1607. El peso de la clase minoritaria se calcula solo con entrenamiento. XGBoost procesa valores ausentes de forma nativa. No se escalan ni imputan datos usando estadísticas del conjunto de evaluación.

El umbral 0,5 se usa exclusivamente para el reporte inicial; no define niveles de alerta. Se reportan precisión, sensibilidad, F1, matriz de confusión, average precision y ROC-AUC, además de la referencia de predecir continuidad siempre. No se realizó búsqueda de hiperparámetros ni calibración. Corresponden a la tarea 13.

## Uso desde backend

Las dependencias de XGBoost, pandas, NumPy y scikit-learn ya están en `requirements.txt`.

```powershell
python -m predictivo --help

# Leer datos locales sin escribir en MySQL.
python -m predictivo preparar --json data/tablas_fuente.json --origen SIMULADO --observado-hasta 2025-12-31 --salida artifacts/experimento/datos

# Alternativa: leer las tablas de la conexión MySQL configurada.
python -m predictivo preparar --mysql --origen REAL --observado-hasta 2025-12-31 --salida artifacts/real/datos

# Entrenar en un directorio nuevo. Rechaza sobrescribir un experimento anterior.
python -m predictivo entrenar --dataset artifacts/experimento/datos/dataset.json --gestion-evaluacion 2025 --salida artifacts/experimento/modelo

# Consultar cortes de una gestión, sin guardar.
python -m predictivo cortes --gestion-id 1 --fecha 2026-03-31 --origen SIMULADO
```

`--gestion-id` debe ser el identificador existente de la gestión y la fecha debe pertenecer a su calendario. Para persistir cortes calculados desde MySQL se añade `--guardar`. No se permite importar directamente los cortes del JSON a matrículas cuyos identificadores podrían pertenecer a otras personas.

Para registrar un modelo se dispone de `python -m predictivo registrar-modelo --help`. Requiere el directorio del artefacto y umbrales medio/alto explícitos; deben acordarse antes de usarlos. Se comprueba la huella SHA-256 y no se permite reutilizar la versión. El registro no activa un modelo.

Los directorios `backend/artifacts/` y `data/` están excluidos de Git. Respaldarlos de forma privada para conservar modelos y conjuntos de datos.

## API

Reiniciar el backend si no está ejecutándose con recarga automática. Los endpoints aparecen en `/docs`, utilizando la autenticación existente.

- `GET /predictivo/variables`: diccionario y criterio inicial de suficiencia.
- `POST /predictivo/cortes/consultar`: consulta sin escrituras.
- `POST /predictivo/cortes`: guarda cortes, sin predicciones.

Cuerpo para ambos POST:

```json
{"gestion_id": 1, "fecha_corte": "2026-03-31", "origen": "SIMULADO"}
```

El administrador debe comprobar gestión y origen antes de guardar. Docente y Orientador no pueden acceder a estos endpoints. Esta etapa no incorpora una nueva pantalla al frontend.

## Evidencia del experimento inicial

Fuente: tablas utilizadas para generar el Excel de 2.400 matrículas simuladas de 2022–2025. La muestra contiene cinco jornadas por curso/gestión y una evaluación por materia; no representa un historial escolar anual completo.

| Resultado | Cantidad |
|---|---:|
| Cortes generados | 2.400 |
| Elegibles según criterio inicial | 1.984 |
| Datos insuficientes | 416 |
| Continuidad confirmada ficticia | 2.224 |
| Abandono confirmado ficticio | 75 |
| Situaciones no comparables (traslados) | 101 |
| Filas utilizadas en entrenamiento tras filtros y purga | 706 |
| Filas de evaluación (gestión 2025) | 491 |

El cambio de notas queda ausente porque no hay dos fechas de evaluación por materia. Se conserva esa limitación en lugar de inventar una tendencia.

Resultado inicial: precisión 0,0370; sensibilidad 0,0909; F1 0,0526; ROC-AUC 0,5448. Matriz de confusión: 417 verdaderos negativos, 52 falsos positivos, 20 falsos negativos y 2 verdaderos positivos. El desempeño es bajo y no justifica uso operativo. Estos números corresponden exclusivamente al experimento simulado y no validan predicciones sobre estudiantes reales.

Los artefactos finales del experimento quedan en `backend/artifacts/primaria_marzo_v1_final/`: dataset y diccionario en `datos/`; modelo, reporte y particiones en `modelo/`. La fuente reproducible local está en `backend/data/primaria_simulada_tablas.json`, excluida de Git. La primera ejecución se conserva en `primaria_marzo_v1/` como antecedente.

La lectura de la base MySQL local se comprobó sin escrituras. Sus 150 matrículas simuladas fueron ingresadas después del 31 de marzo de 2026: no hay matrículas disponibles a ese corte según sus fechas de registro. El calendario actual de 2026 sí está completado, pero la auditoría muestra que esas fechas se completaron más tarde. No se alteraron fechas ni se trasladaron los registros de septiembre al pasado. Por eso el experimento utiliza el conjunto histórico simulado separado.

## Verificación

```powershell
python -m unittest test_predictivo test_predictivo_api -v
```

Las pruebas verifican normalización de notas, faltantes, tareas pendientes/exentas, correcciones posteriores al corte, contexto, rachas, etiquetas, separación temporal y por estudiante, ambas clases, serialización y recarga del modelo, permisos, consultas sin escrituras, cortes inmutables y registro de metadatos.

La integración API/ORM se prueba en SQLite temporal, sin tocar MySQL. No sustituye pruebas de concurrencia específicas de MySQL. El ensayo de 2.400 registros utiliza archivos locales; no carga estudiantes ficticios en la base escolar ni genera alertas.

## Referencias técnicas

- [XGBoost: API Python](https://xgboost.readthedocs.io/en/stable/python/python_api.html).
- [Scikit-learn: prevención de fuga de información](https://scikit-learn.org/stable/common_pitfalls.html).
