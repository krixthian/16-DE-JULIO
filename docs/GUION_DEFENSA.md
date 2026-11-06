# Guion de demostración para la defensa (actividades 9 a 20 del cronograma)

Cada actividad tiene tres partes: **Mostrar** (qué abrir o hacer), **Decir** (guion breve, en voz alta) y **Si preguntan** (respuesta preparada). Todas las cifras son reales y reproducibles. Duración sugerida: 1 a 2 minutos por actividad, unos 20 minutos en total.

## Antes de empezar (checklist)

- [ ] Backend y frontend encendidos (`.claude/launch.json`); `http://localhost:5173` abierto y sesión iniciada como Admin.
- [ ] VS Code con el proyecto y una terminal en `backend`. Para que se vean bien las tildes, antes de nada:
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  ```
- [ ] Figuras de `docs/figuras/` (1 a 10) a mano.
- [ ] Decidir en qué alerta se hará la intervención en vivo (actividad 16): **escribe en la base real** y queda auditado. Recomendado: una de 2025, por ejemplo **Estudiante 0012 · 1° A**, o hacer un respaldo justo antes.

**Apertura (30 s):**
> "Presento el sistema de alerta temprana de la U.E. 16 de Julio. Su propósito es identificar, al cierre del primer trimestre, a los estudiantes de primaria con mayor prioridad de seguimiento por riesgo de abandono, y registrar las intervenciones. Lo recorreré siguiendo el cronograma, desde los datos hasta las pruebas. El modelo apoya, no sustituye, el criterio docente."

---

## Actividad 9: Extracción y consolidación de registros históricos

**Mostrar:** en VS Code, el Excel `data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx` (hoja `DATOS_REAL`) y luego en la terminal:
```powershell
python -c "from predictivo import real_t1 as r; f=r.load('../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx'); print(len(f), 'matrículas,', f.codigo_anonimo.nunique(), 'estudiantes'); print(f.groupby('gestion').agg(matriculas=('codigo_anonimo','size'), abandonos=('y_abandono_intra_anual','sum')))"
```
Después, en el sistema: **Matrículas**.

**Decir:**
> "Los datos se extrajeron de los cuadernos pedagógicos de la escuela y se consolidaron en un solo dataset: **790 matrículas de 523 estudiantes, de 2021 a 2025**. Por gestión: 98 en 2021, 73 en 2022, 50 en 2023, 419 en 2024 y 150 en 2025. Cada fila tiene las notas de las 9 áreas por trimestre, faltas, atrasos, licencias, días asistidos y el resultado del año. Los registros se cargaron a la base con origen REAL y se ven aquí, en Matrículas."

**Si preguntan, ¿por qué hay pocos registros de 2021 a 2023?**
> "De esos años solo se recuperaron algunos cursos. Lo reporto como limitación: además, esos cursos tienen una tasa de abandono mayor, lo que puede introducir un sesgo de selección."

## Actividad 10: Limpieza y preprocesamiento de datos

**Mostrar:** en el sistema, **Estudiantes** (se ven como "Estudiante 0042"). En la terminal, la verificación de calidad del dataset:
```powershell
python -c "import pandas as pd; from predictivo import real_t1 as r; d=pd.read_excel('../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx',sheet_name='DATOS_REAL'); n=[a+'_T1' for a in r.AREAS]+['promedio_T1','nota_minima_T1']; print('notas fuera de 0-100:', int(((d[n]<0)|(d[n]>100)).sum().sum())); print('duplicados estudiante+gestión:', int(d.duplicated(['codigo_anonimo','gestion']).sum())); print('días asistidos > lectivos:', int((d.dias_asistidos_T1>d.dias_lectivos_T1).sum())); print('columnas con nombre o RUDE:', [c for c in d.columns if 'nombre' in c.lower() or 'rude' in c.lower()])"
```
Debe mostrar 0, 0, 0 y `[]`.

**Decir:**
> "Antes de modelar se limpiaron y verificaron los datos:
> - **Anonimización:** cada estudiante tiene un código anónimo, sin nombre ni RUDE en el dataset, y el mismo código entre años permite seguir al estudiante.
> - **Calidad verificada:** ninguna nota fuera de 0 a 100, ningún valor faltante en las variables, ninguna matrícula duplicada por estudiante y gestión, y días asistidos nunca mayores que los lectivos. La tasa de asistencia se calcula como días asistidos sobre días lectivos.
> - **Etiqueta:** el abandono se determinó a partir del cuaderno: 11 casos, 4 en 2021, 3 en 2022, 2 en 2023, 2 en 2024 y ninguno aún en 2025.
>
> Además, la base distingue datos REAL de SIMULADO: las 150 matrículas simuladas de las primeras pruebas se identifican por su origen y nunca entran al modelo."

**Si preguntan, ¿la etiqueta es confiable?**
> "Es una limitación que declaro: se infirió del cuaderno y está pendiente de confirmar con Dirección. Uno de los 11 casos ya estaba ausente en el primer trimestre."

## Actividad 11: Ingeniería de características (variables de riesgo)

**Mostrar:** en VS Code, `backend/artifacts/real_t1_v1/diccionario.json` (variables con su descripción). En la terminal, las primeras líneas de:
```powershell
python -m predictivo metricas-real --directorio artifacts/real_t1_v1
```

**Decir:**
> "Se construyeron **19 variables disponibles al 30 de abril**, el corte del primer trimestre: las notas de las 9 áreas, el promedio, la nota mínima, el número de áreas bajo 51, faltas, atrasos, licencias, tasa de asistencia, edad, grado y género.
>
> La regla más importante: **no se usa ninguna variable del segundo trimestre, del tercero ni anual** (las columnas POST_*), porque el sistema debe predecir con lo que se sabe en abril. Usarlas sería fuga de información. Tampoco se usan la gestión, el paralelo ni los códigos. Un test automático verifica que ninguna columna POST_* entre al modelo."

**Si preguntan, ¿por qué el género o la edad?**
> "Son variables de contexto disponibles al inicio del año. No determinan la alerta por sí solas: en las explicaciones de cada alerta se ve que el peso real lo tienen las notas y la asistencia."

## Actividad 12: Entrenamiento base del modelo predictivo (XGBoost)

**Mostrar:** la salida completa de `metricas-real` (el comando de la actividad 11): primero la línea "SHA-256 … OK, coincide con el archivo" y luego la tabla de abandono. Figuras 1 y 2 de `docs/figuras/`.

**Decir:**
> "El modelo base es un XGBoost de 80 árboles, profundidad 3 y tasa de aprendizaje 0,05, con semilla fija. Se validó con **validación cruzada agrupada por estudiante, 5 pliegues repetidos 20 veces**, para que un estudiante nunca esté a la vez en entrenamiento y evaluación. Los intervalos de confianza son por bootstrap.
>
> Resultados: **AUC 0,989** (IC 0,90 a 1,00), **AP 0,86**, sensibilidad 0,84, precisión 0,77 y F1 0,80, marcando solo el 1,5 % de las matrículas. Lo comparé con baselines: 'siempre continuidad' tiene AP 0,01 y una regla por promedio, AP 0,30. El modelo sí aporta.
>
> El sistema verifica el hash del modelo guardado: lo que se usa en producción es exactamente lo que se evaluó."

**Si preguntan, ¿no son métricas demasiado altas?** (la pregunta más probable)
> "Sí, y lo reporto como advertencia. Solo hay **11 abandonos**, y en 2021-2023 todas las matrículas con promedio ≤ 66 abandonaron: es una separación casi perfecta que infla las métricas. En la prueba temporal, entrenando con 2021-2023 y evaluando en 2024, detectó los 2 abandonos, pero con 10 falsas alarmas (AP 0,14). Por eso el sistema lo usa como **ranking de prioridad**, no como diagnóstico."

**Si preguntan, ¿y la regresión logística?**
> "Obtiene resultados iguales o mejores (AUC 1,00) y los intervalos se solapan: XGBoost no es superior de forma distinguible. Lo mantengo porque explica cada predicción con sus factores (valores SHAP), que es lo que ve el docente en cada alerta."

**Si preguntan, ¿y predecir que no continúa el año siguiente?**
> "Lo evalué y no funciona: AUC 0,53, con 17 casos solo de 2024. Por eso el sistema solo alerta sobre el abandono dentro del año."

## Actividad 13: Sintonización de hiperparámetros y evaluación (F1-Score)

**Mostrar:** en la terminal:
```powershell
python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1
```
Figuras 6 (comparación con IC), 9 (umbrales) y 10 (estabilidad).

**Decir:**
> "Ajusté los hiperparámetros con **validación anidada**: 108 combinaciones de profundidad, tasa de aprendizaje, número de árboles, peso mínimo por hoja y submuestreo. El ajuste se hace dentro de cada pliegue, sin ver los datos de evaluación. El criterio de adopción se fijó **antes** de ver los resultados: adoptar solo si mejora la AP de forma distinguible.
>
> Resultado: el ajustado tiene F1 0,79 frente a 0,80 del base, y la diferencia de AP es −0,005, con un intervalo de −0,20 a +0,16, que incluye el cero. **Se ajustó y el modelo base resultó adecuado.** Además se eligieron 43 configuraciones distintas en 100 pliegues: con 11 casos ninguna domina.
>
> También evalué umbrales: con 0,5 se detectan 9,2 de 11 abandonos con 2,7 falsas alarmas; con 0,8, 7,3 con 0,9. Propongo 0,5 para alertar y 0,8 para priorizar, a validar con Dirección. La calibración tampoco mejoró de forma distinguible, así que no se adoptó."

**Si preguntan, ¿entonces el ajuste no sirvió?**
> "Sirvió para demostrar con evidencia que el modelo base es adecuado. Elegir el resultado más favorable a posteriori habría inflado las métricas; fijar el criterio antes lo evita."

## Actividad 14: Integración del modelo predictivo al sistema central

**Mostrar:** en el sistema, **Alertas de riesgo**: las tarjetas (790 predicciones, modelo `xgb-real-t1-v1-…`, umbrales).

**Decir:**
> "El modelo está registrado en la tabla de modelos con su versión, el hash del archivo, los umbrales y el protocolo de validación. Para cada matrícula se guarda un **corte predictivo** con las 19 variables tal como estaban el 30 de abril, y una **predicción** con su puntaje y sus factores principales. Hay 790 predicciones; las que superan 0,5 generan una alerta: hoy son 13. La generación es idempotente: si se vuelve a ejecutar, no duplica nada."

**Si preguntan, ¿qué pasa cuando haya datos de un año nuevo?**
> "Se cargan las matrículas y las notas del primer trimestre, se genera el corte y el modelo registrado produce las predicciones y las alertas de esa cohorte."

## Actividad 15: Módulo de alertas de riesgo académico

**Mostrar:** en **Alertas de riesgo**, el aviso azul y los filtros. Filtrar **2024 + Alto** (quedan 2) y abrir **Estudiante 0136 · 3° A · 2024**. Bajar hasta **Historial (auditoría)**. Luego quitar el filtro y mostrar las 2 alertas de 2025.

**Decir:**
> "Cada alerta indica su **puesto en el ranking**: este estudiante es el número 1 de 419 en 2024. El nivel es una prioridad, no un porcentaje de riesgo, porque las probabilidades no están calibradas. MEDIO desde 0,5 y ALTO desde 0,8 es una propuesta para Dirección.
>
> El panel explica **por qué**: el promedio del primer trimestre (66) es lo que más eleva su prioridad, seguido de Artes Plásticas y Educación Musical. Se filtra por gestión, curso, nivel y estado; se asigna un responsable; y para cerrar una alerta el motivo es obligatorio. Cada cambio queda en el historial de auditoría.
>
> Las alertas de 2021 a 2024 son retrospectivas, porque esos años se usaron para entrenar. Las 2 de 2025 son la cohorte actual."

**Si preguntan, ¿y los falsos positivos?**
> "Una falsa alarma cuesta una revisión; no detectar un abandono cuesta mucho más. Igual, el docente decide y puede cerrar la alerta con motivo."

## Actividad 16: Módulo de recomendaciones pedagógicas

**Mostrar:** en la alerta elegida, **Recomendaciones pedagógicas**. Registrar una como intervención y avanzarla hasta **Realizada**, con tipo de acción, fecha y resultado. *(Escribe en la base: solo en la alerta decidida.)* Mostrar `docs/RECOMENDACIONES_PEDAGOGICAS.md`.

**Decir:**
> "Las recomendaciones salen de **cinco reglas explícitas**:
> - **RP01:** promedio ≤ 68 → reforzamiento y citación.
> - **RP02:** áreas bajo 51 → reforzamiento en esas áreas.
> - **RP03:** faltas o asistencia baja → citación al apoderado.
> - **RP04:** atrasos frecuentes → entrevista.
> - **RP05:** prioridad alta → reunión de caso.
>
> Cada una muestra el dato que la dispara. Los umbrales vienen de la escala de valoración de la Ley 070 y de percentiles de la escuela, **no** de los casos de abandono. Son una propuesta a validar con docentes y Dirección.
>
> Al registrarla se convierte en intervención, y al ejecutarla se anota qué se hizo, cuándo y con qué resultado."

**Si preguntan, ¿por qué reglas y no un modelo?**
> "Porque deben ser explicables y discutibles por los docentes. Una regla se ajusta en una reunión; una recomendación de una caja negra, no."

## Actividad 17: Dashboards analíticos interactivos

**Mostrar:** **Panel analítico**. Pasar el mouse por "Evolución de alertas por gestión" (tooltip). Cambiar el filtro a 2024. Abrir "Ver los datos en tablas".

**Decir:**
> "El panel es para Dirección y Orientación. Muestra alertas por nivel y curso, la distribución del promedio del primer trimestre por grado según la escala de la Ley 070, la evolución de alertas por gestión (4, 3, 2, 2 y 2 de 2021 a 2025) y el estado de las intervenciones. Se hizo con Chart.js y **todo se calcula en el momento desde la base**: no hay cifras fijas. Cada gráfico tiene su tabla de datos."

## Actividad 18: Módulo de generación de reportes

**Mostrar:** en el panel, gestión 2024 → **Descargar PDF**; abrirlo. Mencionar el CSV.

**Decir:**
> "Se generan reportes **PDF imprimibles y CSV** por gestión o por curso, con alertas, factores, reglas activas e intervenciones con su ejecución. Los estudiantes salen anonimizados. Cada reporte lleva la fecha, la aclaración de que el nivel es un ranking y no un riesgo absoluto, y la nota de que el modelo apoya, no sustituye, el criterio docente. El CSV abre directo en Excel."

## Actividad 19: Diseño final y ajuste definitivo de la base de datos

**Mostrar:** el diagrama EER de Workbench y `docs/REVISION_ESQUEMA_BD.md`.

**Decir:**
> "La base final tiene **28 tablas, 47 claves foráneas y 40 restricciones CHECK**. Verifiqué que la base real, el modelo en código y el script SQL coinciden exactamente. Las restricciones protegen la integridad: una alerta no puede quedar cerrada sin fecha ni motivo, y una intervención no puede marcarse como realizada sin describir la acción. Con EXPLAIN comprobé que las consultas del panel usan índices; dejé propuestos tres índices opcionales para cuando crezca el volumen, sin aplicarlos."

**Si preguntan por las tablas sin uso (apoderados, citaciones, notificaciones):**
> "Forman parte del diseño para módulos futuros: citación formal y notificación a la familia. Hoy la citación se registra como tipo de intervención."

## Actividad 20: Ejecución de pruebas generales e integrales

**Mostrar:** `docs/PLAN_PRUEBAS.md` (matriz de permisos y flujo) y `docs/figuras/evidencia_terminal/20_tests_backend.txt`. *(No correr la batería en vivo: tarda unos 10 minutos.)*

**Decir:**
> "Hay **49 pruebas automáticas en verde**: unitarias, por módulo, del esquema e integrales.
> - **Permisos:** se probaron los 58 endpoints con los 4 roles, y sin sesión todos responden 401.
> - **Flujo completo:** alerta, recomendación, intervención, cierre, panel, reporte y auditoría.
> - **MySQL real:** el mismo flujo se ejecutó en una base de pruebas, con las claves foráneas y las restricciones activas.
>
> No se encontraron errores de la aplicación."

**Si preguntan, ¿qué no se probó?**
> "No hay pruebas automáticas del navegador ni de carga, y falta la prueba de aceptación con la escuela. Están documentadas como limitaciones."

---

## Cierre (1 min)

> "En resumen, el sistema ordena a quién revisar primero y registra qué se hizo, dejando la decisión en los docentes.
>
> Las limitaciones son claras:
> - solo 11 abandonos, con una separación por promedio que infla las métricas;
> - etiquetas por confirmar con Dirección;
> - umbrales y reglas por validar con la escuela.
>
> Como trabajo futuro: incorporar los paralelos faltantes de 2021-2023 y más cursos de 2025, validar con Dirección, y usar la asistencia diaria y la citación formal a la familia."

## Preguntas difíciles: respuestas cortas

| Pregunta | Respuesta |
|---|---|
| ¿Cuántos casos positivos hay? | 11 abandonos en 790 matrículas (9 estudiantes). |
| ¿Cómo evitaste el sobreajuste? | Validación agrupada por estudiante, repetida 20 veces, ajuste anidado y criterio fijado antes de ver resultados. |
| ¿Hay fuga de información? | No: solo variables disponibles al 30 de abril. Un test verifica que ninguna columna POST_* entre al modelo. |
| ¿Por qué umbral 0,5? | No se ajustó con los datos de evaluación. Con 0,5 se detectan 9,2 de 11 con 2,7 falsas alarmas; con 0,8, 7,3 con 0,9. |
| ¿Funciona en otros años? | En la prueba temporal 2021-2023 → 2024 detectó 2 de 2, con 10 falsas alarmas. Sirve para priorizar; hay que reevaluarlo con más datos. |
| ¿Qué pasa si el modelo se equivoca? | La alerta es un aviso para revisar, no una decisión. Se cierra con motivo y todo queda auditado. |
| ¿Se puede reproducir? | Sí: `metricas-real --excel` y `metricas-ajuste --excel` recalculan todo y confirman "reproducido exactamente". |
