# Guion de demostración para la defensa

Cada punto tiene tres partes: **Mostrar** (qué abrir o hacer en el sistema), **Decir** (guion breve, en voz alta) y **Si preguntan** (respuesta preparada). Todas las cifras son reales y se pueden reproducir con los comandos de `RESUMEN_PARA_CHAT.md`.

**Duración sugerida:** 15 a 20 minutos de demo. Los tiempos de cada punto son orientativos.

## Antes de empezar (checklist)

- [ ] Backend y frontend encendidos (`.claude/launch.json`). `http://localhost:5173` abierto.
- [ ] Una terminal en `backend` y VS Code con el proyecto abierto.
- [ ] Sesión **no** iniciada todavía: el login es parte de la demo.
- [ ] Figuras de `docs/figuras/` (1 a 10) a mano, por si piden detalle del modelo.
- [ ] Decidir de antemano en qué alerta se hará la demo de intervención (punto 7): **registrar una intervención escribe en la base real** y queda auditado. Recomendado: una alerta de 2025 (cohorte actual), por ejemplo la de **Estudiante 0012 · 1° A**, o hacer un respaldo justo antes.

---

## 1. Presentación del sistema (1 min)

**Mostrar:** la pantalla de login.

**Decir:**
> "Este es el sistema de alerta temprana de la U.E. 16 de Julio. Su objetivo es identificar, al cierre del primer trimestre, a los estudiantes de primaria con mayor prioridad de seguimiento por riesgo de abandono, y apoyar la intervención pedagógica. El sistema tiene tres capas: un backend en FastAPI con MySQL, un frontend en Vue y un modelo XGBoost integrado. El modelo apoya, no sustituye, el criterio docente."

**Si preguntan, por qué al cierre del 1.er trimestre:**
> "Porque es el primer momento con información académica suficiente (notas de 9 áreas, faltas, atrasos), y todavía queda casi todo el año para intervenir."

## 2. Autenticación y roles (1-2 min)

**Mostrar:** iniciar sesión con tu usuario Admin. Señalar el menú lateral.

**Decir:**
> "El acceso es con correo y contraseña. Las contraseñas se guardan con hash y la sesión usa un token JWT que vence en 2 horas. Cada rol ve solo lo que le corresponde: Admin y Director administran la parte escolar; Docente registra asistencia, notas y tareas de **sus** asignaciones; Orientación y Dirección gestionan las alertas."

**Si preguntan, cómo se garantiza el control de acceso:**
> "No depende solo del menú: el backend valida el rol en cada endpoint. En las pruebas integrales se probaron los 58 endpoints con los 4 roles, y sin sesión todos responden 401."

## 3. Administración escolar (1-2 min)

**Mostrar:** Gestiones → Cursos → Estudiantes → Matrículas.

**Decir:**
> "Aquí se registran gestiones, cursos, estudiantes y matrículas. Los datos reales están **anonimizados**: los estudiantes aparecen como 'Estudiante 0042', sin nombre ni RUDE. Hay 790 matrículas reales de 523 estudiantes, de 2021 a 2025. Cada alta o corrección queda registrada en la tabla de auditoría."

**Si preguntan, por qué anonimizado:**
> "Por protección de datos de menores. El modelo no necesita la identidad; necesita el historial académico. En la escuela, el código se puede vincular con el registro real bajo responsabilidad de Dirección."

## 4. Calificaciones, asistencia y tareas (1-2 min)

**Mostrar:** Calificaciones (periodos y evaluaciones) y Seguimiento de tareas. Asistencia diaria brevemente.

**Decir:**
> "Estos módulos alimentan los indicadores. El docente registra notas por evaluación y trimestre, la asistencia diaria y la entrega de tareas, siempre limitado a los cursos y materias que tiene asignados."

**Si preguntan, por qué la asistencia diaria está vacía:**
> "Los datos históricos vienen del cuaderno pedagógico, que trae faltas, atrasos y licencias por trimestre. El modelo usa esos totales. El registro diario queda listo para usarse desde ahora."

## 5. Datos y modelo (3-4 min). Aquí se defiende el objetivo del modelo

**Mostrar:** la terminal, desde `backend`:
```powershell
python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1
```
Luego las figuras de comparación (CI) y de umbrales en `docs/figuras/`.

**Decir:**
> "Se consolidaron 790 matrículas reales. El modelo usa **19 variables del primer trimestre**: notas de las 9 áreas, promedio, nota mínima, número de áreas bajo 51, faltas, atrasos, licencias, tasa de asistencia, edad, grado y género. **No usa ninguna variable del segundo o tercer trimestre**, porque eso sería fuga de información.
>
> La validación es cruzada **agrupada por estudiante** (5 pliegues, repetida 20 veces), para que un mismo estudiante nunca esté en entrenamiento y evaluación a la vez. Los intervalos de confianza se calcularon por bootstrap.
>
> Resultado: AUC 0,989 (IC 95 % 0,90 a 1,00), AP 0,86, sensibilidad 0,84, precisión 0,77 y F1 0,80, marcando solo el 1,5 % de las matrículas. En promedio detecta 9,2 de los 11 abandonos con 2,7 falsas alarmas."

**Ajuste de hiperparámetros (objetivo 2):**
> "Ajusté 108 combinaciones con validación anidada y un criterio de adopción fijado **antes** de ver los resultados. El modelo ajustado no mejora de forma distinguible: la diferencia de AP es −0,005, con un intervalo de −0,20 a +0,16. La conclusión honesta es que el modelo base ya era adecuado. Además, en 100 pliegues se eligieron 43 configuraciones distintas: con 11 casos ninguna domina."

**Si preguntan, ¿no son métricas demasiado altas?** (la pregunta más probable)
> "Sí, y lo reporto como advertencia. Solo hay **11 abandonos**, por eso los intervalos son amplios. Además, en 2021-2023 todas las matrículas con promedio del primer trimestre ≤ 66 abandonaron: es una separación casi perfecta que infla las métricas. En la prueba temporal, entrenando con 2021-2023 y evaluando en 2024, detectó los 2 abandonos, pero con 10 falsas alarmas (AP 0,14). Por eso el sistema lo presenta como **ranking de prioridad** y no como diagnóstico."

**Si preguntan, ¿XGBoost es mejor que algo más simple?**
> "No de forma distinguible: la regresión logística obtiene resultados iguales o mejores y los intervalos se solapan. XGBoost se mantiene porque permite explicar cada predicción con sus factores (valores SHAP), que es lo que se muestra en las alertas. Una regla simple de promedio tiene AP 0,30: el modelo sí aporta sobre esa regla."

**Si preguntan, ¿por qué no calibraron las probabilidades?**
> "Se probó la calibración sigmoide e isotónica y no mejoró de forma distinguible: el Brier cambió −0,0002, con un IC que incluye el 0. Con 11 casos no se puede calibrar con confianza; por eso el puntaje se usa para ordenar, no como porcentaje de riesgo."

## 6. Módulo de alertas (2 min)

**Mostrar:** **Alertas de riesgo**. Señalar el aviso azul, las tarjetas (790 predicciones, 11 alta, 2 media) y los filtros. Filtrar **2024 + Alto** (quedan 2) y abrir **Estudiante 0136 · 3° A · 2024**.

**Decir:**
> "Cada matrícula tiene una predicción; las que superan el umbral generan una alerta. El nivel **es un ranking de prioridad**: este estudiante es el puesto 1 de 419 en 2024. Los umbrales, MEDIO desde 0,5 y ALTO desde 0,8, son una propuesta pendiente de validar con Dirección.
>
> El panel muestra **por qué** está priorizado: el promedio del primer trimestre (66) es el factor que más eleva su prioridad, seguido de Artes Plásticas y Educación Musical. Se puede asignar un responsable, cambiar el estado y cerrar la alerta con un motivo obligatorio. Todo cambio queda en el historial de auditoría."

**Mostrar luego:** las alertas de 2025 (Estudiante 0012 y 0139, nivel MEDIO).
> "Las alertas de 2021 a 2024 son retrospectivas, porque esos años se usaron para entrenar. Las de 2025 son la cohorte actual: son las que la escuela trabajaría hoy."

**Si preguntan, ¿qué pasa con un falso positivo?**
> "El costo de una falsa alarma es una revisión o una citación: bajo comparado con no detectar un abandono. Igual, el docente decide; la alerta se puede cerrar con motivo, por ejemplo 'asiste con normalidad'."

## 7. Recomendaciones e intervenciones (2 min)

**Mostrar:** en la alerta elegida, bajar a **Recomendaciones pedagógicas**. Registrar una como intervención y llevarla a **Realizada** con tipo, fecha y resultado. *(Escribe en la base: hacerlo solo en la alerta decidida de antemano.)*

**Decir:**
> "A partir de los factores de cada alerta, el sistema sugiere acciones con **reglas explícitas y legibles**, de RP01 a RP05. Por ejemplo, RP01 se activa con promedio ≤ 68 y propone reforzamiento y citación al apoderado; RP05 pide una reunión de caso para toda prioridad alta. Cada regla muestra el dato que la dispara. Los umbrales vienen de la escala de la Ley 070 y de percentiles de la escuela, **no** de los casos de abandono. Son una propuesta pendiente de validar con docentes y Dirección.
>
> Una recomendación se convierte en intervención solo cuando alguien la registra, y al ejecutarla se anota qué se hizo, cuándo y con qué resultado."

**Si preguntan, ¿por qué reglas y no IA para las recomendaciones?**
> "Porque deben ser explicables y auditables por los docentes. Una regla se puede discutir y ajustar en una reunión; una recomendación generada por un modelo no."

## 8. Panel analítico (1-2 min)

**Mostrar:** **Panel analítico**. Pasar el mouse por "Evolución por gestión" (se ve el tooltip). Cambiar el filtro a 2024.

**Decir:**
> "El panel resume la situación para Dirección: alertas por nivel y curso, distribución del promedio del primer trimestre por grado según la escala de la Ley 070, evolución de alertas por gestión y estado de las intervenciones. Todo se calcula en el momento desde la base; no hay cifras fijas."

## 9. Reportes (1 min)

**Mostrar:** en el panel, elegir gestión 2024 y pulsar **Descargar PDF**; abrirlo. Mencionar el CSV.

**Decir:**
> "Se generan reportes PDF imprimibles y CSV por gestión o curso, con alertas, factores, reglas e intervenciones. Los estudiantes salen anonimizados y cada reporte incluye la fecha, la aclaración de que el nivel es un ranking y la nota de que el modelo apoya, no sustituye, el criterio docente."

## 10. Base de datos (1 min)

**Mostrar:** el diagrama EER de Workbench o `docs/diagrama_relaciones.mmd`.

**Decir:**
> "La base tiene 28 tablas, 47 claves foráneas y 40 restricciones CHECK. Verifiqué que la base real, el modelo en código y el script SQL coinciden exactamente. Las restricciones protegen la integridad: por ejemplo, una alerta no puede quedar cerrada sin fecha ni motivo, y una intervención no puede marcarse como realizada sin describir la acción."

**Si preguntan por las tablas sin uso (apoderados, citaciones, notificaciones):**
> "Son parte del diseño para módulos futuros: citación formal y notificación a la familia. Hoy la citación se registra como tipo de intervención."

## 11. Pruebas (1 min)

**Mostrar:** `docs/PLAN_PRUEBAS.md` y la evidencia en `docs/figuras/evidencia_terminal/`. *(No correr la batería completa en vivo: tarda unos 10 minutos.)*

**Decir:**
> "Hay 49 pruebas automáticas en verde: unitarias, por módulo, del esquema e integrales. La prueba integral recorre el flujo completo: alerta, recomendación, intervención, cierre, panel, reporte y auditoría. Se ejecutó también sobre MySQL real en una base de pruebas, con las claves foráneas y las restricciones activas."

## 12. Cierre: limitaciones y trabajo futuro (1 min)

**Decir:**
> "Las limitaciones, con honestidad:
> 1. **Solo 11 abandonos.** Las métricas tienen intervalos amplios y hay una separación casi perfecta por promedio que las infla.
> 2. **Etiquetas por confirmar.** Se infirieron del cuaderno y falta confirmarlas con Dirección.
> 3. **Validación pendiente.** Los umbrales y las reglas RP aún deben validarse con la escuela.
>
> Como trabajo futuro: incorporar los paralelos faltantes de 2021-2023 y los cursos de 2025 para tener más casos, validar con Dirección, y usar el registro diario de asistencia y la citación formal a la familia.
>
> En conclusión, el sistema cumple su propósito: **ordenar a quién revisar primero y registrar qué se hizo**, dejando la decisión en manos de los docentes."

---

## Preguntas difíciles: respuestas cortas

| Pregunta | Respuesta |
|---|---|
| ¿Cuántos casos positivos hay? | 11 abandonos en 790 matrículas (9 estudiantes). |
| ¿Cómo evitaste el sobreajuste? | Validación agrupada por estudiante, repetida 20 veces, ajuste anidado y criterio fijado antes de ver resultados. |
| ¿Hay fuga de información? | No: solo variables disponibles al 30 de abril. Hay un test que verifica que ninguna columna POST_* entre al modelo. |
| ¿Por qué umbral 0,5? | No se ajustó con los datos de evaluación. Con 0,5 se detectan 9,2 de 11 con 2,7 falsas alarmas; con 0,8, 7,3 con 0,9. Por eso 0,5 alerta y 0,8 prioriza. |
| ¿El modelo funciona para otros años? | En la prueba temporal 2021-2023 → 2024 detectó los 2 de 2 casos, con 10 falsas alarmas. Sirve para priorizar; hay que reevaluar con más datos. |
| ¿Qué pasa si el modelo se equivoca? | La alerta es un aviso para revisar, no una decisión. Se cierra con motivo y todo queda auditado. |
| ¿Se puede reproducir? | Sí: `metricas-real --excel` y `metricas-ajuste --excel` recalculan todo y confirman "reproducido exactamente". |
