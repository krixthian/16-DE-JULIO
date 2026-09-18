# Base de datos para alerta temprana escolar — propuesta v2

Caso: Unidad Educativa 16 de Julio. Alcance: primaria, un registro de asistencia por día y matrícula. Diseño basado en el esquema compartido y en el Excel simulado de 30 estudiantes. No presupone que existan datos reales ni un modelo entrenado.

## Decisiones principales

La identidad del estudiante permanece estable. Cada matrícula representa su permanencia en un curso durante una gestión; el curso contiene la gestión. Un cambio de paralelo cierra una matrícula y abre otra sin borrar sus notas. La aplicación debe impedir segmentos simultáneos incompatibles.

Las calificaciones pertenecen a evaluaciones parciales con fecha y escala. Los docentes registran asistencia por lista y notas en una cuadrícula. Las tareas tienen destinatarios y vencimiento: no se guarda solamente un total trimestral. El historial distingue continuidad observada, abandono confirmado y traslado.

La predicción, la alerta y la intervención son entidades diferentes. Se conservan predicciones aunque no produzcan alertas. Cada resultado referencia un corte de variables y una versión del modelo. Las recomendaciones son propuestas pedagógicas revisadas por una persona; XGBoost no genera por sí mismo el texto de una intervención.

## Tablas y propósito

### 1. `usuarios`

Acceso del personal. El usuario establece su contraseña al activar la cuenta. Un rol por usuario en esta primera versión.

Campos: `id`, `nombre`, `apellido`, `email`, `password_hash`, `rol`, `activo`, `creado_en`.

### 2. `tokens_acceso`

Tokens de un solo uso. Se almacena el hash, nunca el enlace secreto ni una contraseña en texto plano.

Campos: `id`, `usuario_id`, `token_hash`, `proposito`, `vence_en`, `usado_en`, `creado_en`.

### 3. `gestiones`

Calendario anual definido por el colegio.

Campos: `id`, `anio`, `fecha_inicio`, `fecha_fin`.

### 4. `periodos`

Trimestres con fechas reales. La aplicación controla que pertenezcan a la gestión y no se solapen.

Campos: `id`, `gestion_id`, `numero`, `fecha_inicio`, `fecha_fin`.

### 5. `cursos`

Sección de un grado en una gestión. Se crea otra fila para la siguiente gestión.

Campos: `id`, `gestion_id`, `nivel`, `grado`, `paralelo`, `docente_asesor_id`.

### 6. `estudiantes`

Identidad estable. Curso e historial académico se registran en matrículas, no en esta tabla.

Campos: `id`, `codigo_anonimo`, `codigo_rude`, `nombre`, `apellido`, `fecha_nacimiento`, `creado_en`.

### 7. `apoderados`

Contactos familiares. Un apoderado puede estar relacionado con varios estudiantes.

Campos: `id`, `nombre_completo`, `telefono`, `email`.

### 8. `estudiante_apoderado`

Relación familiar con vigencia para conservar contactos históricos.

Campos: `estudiante_id`, `apoderado_id`, `parentesco`, `contacto_principal`, `vigente_desde`, `vigente_hasta`.

### 9. `matriculas`

Permanencia en un curso. Un cambio de paralelo cierra el segmento y crea otro, sin sobrescribir el historial.

Campos: `id`, `estudiante_id`, `curso_id`, `fecha_ingreso`, `fecha_fin`, `origen`, `registrado_por`, `creado_en`.

### 10. `situaciones_escolares`

Evidencia del resultado escolar y alcance del seguimiento. No se utiliza como predictor de su propio resultado.

Campos: `id`, `matricula_id`, `tipo`, `fecha_efectiva`, `observado_hasta`, `fuente_verificacion`, `observacion`, `registrado_por`, `registrado_en`.

### 11. `materias`

Catálogo de materias.

Campos: `id`, `nombre`, `sigla`.

### 12. `asignaciones_docentes`

Permite verificar qué docente registra en un curso y materia, incluyendo reemplazos con vigencia.

Campos: `id`, `curso_id`, `materia_id`, `docente_id`, `vigente_desde`, `vigente_hasta`.

### 13. `jornadas_clase`

Calendario diario por curso para distinguir días de clase, suspensiones y falta de registro. Una asistencia diaria, no por materia.

Campos: `id`, `curso_id`, `fecha`, `es_lectiva`, `motivo_no_lectiva`.

### 14. `asistencias`

Estado diario. La falta de una fila significa sin registro; nunca se convierte automáticamente en falta o presencia.

Campos: `id`, `matricula_id`, `jornada_id`, `curso_id`, `estado`, `justificada`, `observacion`, `registrado_por`, `registrado_en`.

### 15. `evaluaciones`

Actividad parcial fechada. Dimensiones y ponderaciones quedan pendientes de la planilla oficial del colegio.

Campos: `id`, `asignacion_id`, `curso_id`, `gestion_id`, `periodo_id`, `titulo`, `tipo`, `dimension`, `fecha_aplicacion`, `puntaje_maximo`, `ponderacion`, `registrado_en`.

### 16. `calificaciones`

Nota de un estudiante en una evaluación. Cero es una nota real; pendiente y no presentada mantienen puntaje NULL.

Campos: `id`, `evaluacion_id`, `matricula_id`, `curso_id`, `estado`, `puntaje`, `registrado_por`, `registrado_en`.

### 17. `tareas`

Actividad con plazo. Si se califica, se vincula con evaluaciones, sin duplicar la nota.

Campos: `id`, `asignacion_id`, `curso_id`, `evaluacion_id`, `titulo`, `fecha_asignacion`, `fecha_limite`, `registrado_en`.

### 18. `entregas_tareas`

Una fila por estudiante destinatario de la tarea. La tardanza se calcula comparando entrega con vencimiento.

Campos: `id`, `tarea_id`, `matricula_id`, `curso_id`, `estado`, `fecha_entrega`, `registrado_por`, `registrado_en`.

### 19. `registros_convivencia`

Observaciones con criterios acordados. No contiene diagnósticos psicológicos ni una puntuación inventada de conducta.

Campos: `id`, `matricula_id`, `fecha_hecho`, `categoria`, `descripcion_objetiva`, `accion_inmediata`, `registrado_por`, `registrado_en`.

### 20. `modelos_predictivos`

Versiones inmutables del modelo y sus umbrales. No se insertan métricas ni umbrales ficticios por defecto.

Campos: `id`, `version`, `algoritmo`, `objetivo`, `version_variables`, `origen_datos`, `entrenado_en`, `datos_hasta`, `artefacto_uri`, `artefacto_sha256`, `umbral_medio`, `umbral_alto`, `protocolo_validacion`, `metricas`.

### 21. `cortes_predictivos`

Fotografía inmutable de variables conocidas al corte. JSON tiene contrato versionado; no sustituye a los registros escolares.

Campos: `id`, `matricula_id`, `fecha_corte`, `disponible_hasta`, `version_variables`, `variables`, `cobertura_asistencia`, `estado`, `motivo`, `generado_en`.

### 22. `predicciones`

Resultado del modelo. Factores explicativos no se presentan como causas de abandono.

Campos: `id`, `corte_id`, `modelo_id`, `probabilidad`, `nivel`, `factores`, `generada_en`.

### 23. `alertas`

Caso de atención generado desde una predicción; una predicción de riesgo bajo no necesita abrir un caso.

Campos: `id`, `prediccion_id`, `responsable_id`, `estado`, `creada_en`, `cerrada_en`, `motivo_cierre`.

### 24. `intervenciones`

Varias actuaciones por alerta. Conserva propuesta, aprobación humana, ejecución y resultado.

Campos: `id`, `alerta_id`, `recomendacion`, `regla_version`, `responsable_id`, `fecha_planificada`, `estado`, `aprobada_por`, `aprobada_en`, `accion_realizada`, `resultado`, `realizada_en`, `creada_en`.

### 25. `citaciones`

Reuniones con la familia, con o sin alerta, y acuerdos de seguimiento.

Campos: `id`, `matricula_id`, `apoderado_id`, `intervencion_id`, `fecha_programada`, `motivo`, `estado`, `acuerdos`, `registrado_por`, `registrado_en`.

### 26. `notificaciones`

Seguimiento de correo o boleta. Enviado no significa leído; una boleta impresa no equivale a entregada.

Campos: `id`, `citacion_id`, `canal`, `destino`, `estado`, `intentos`, `referencia_externa`, `ultimo_error`, `creada_en`, `enviada_en`, `entregada_en`.

### 27. `auditoria_cambios`

Historial de correcciones escrito por la aplicación en la misma transacción. Excluir contraseñas, tokens y contenido clínico.

Campos: `id`, `usuario_id`, `tabla_afectada`, `registro_id`, `operacion`, `motivo`, `antes`, `despues`, `registrado_en`.

## Reglas que la API debe implementar

El SQL incluye claves foráneas, unicidad, coherencia de curso mediante claves compuestas y comprobaciones de valores de una misma fila. No basta con importar el SQL para tener un sistema operativo. Las siguientes reglas requieren validación transaccional en FastAPI y pruebas de integración:

1. Fechas: períodos dentro de la gestión y sin solapamiento; asistencia, evaluaciones y entregas dentro de la permanencia del estudiante y la vigencia docente. No insertar notas de actividades posteriores a una salida definitiva. Diferenciar la fecha de una actividad de la fecha en que se registró su nota.
2. Matrículas: impedir permanencias simultáneas incompatibles usando bloqueo transaccional por estudiante. En cambios de curso, preservar el vínculo por estudiante y consolidar sus segmentos al preparar ejemplos de entrenamiento.
3. Notas: comprobar que el puntaje no exceda el máximo de la evaluación. Una evaluación con notas no debe cambiar de escala sin una corrección auditada. Definir con el colegio las dimensiones, ponderaciones y reglas de cierre; este diseño no inventa una fórmula oficial de boletín.
4. Tareas: al asignarlas, crear filas de destinatarios; no interpretar la ausencia de una fila como incumplimiento. Verificar que evaluación y tarea vinculadas correspondan a la misma materia. Una entrega tardía se deriva de sus fechas, no de un campo redundante.
5. Acceso: cada docente actúa solo sobre sus asignaciones vigentes y estudiantes del curso. Dirección confirma situaciones escolares. Validar también que apoderado, citación, intervención y alerta pertenezcan al mismo estudiante. Las claves simples por sí solas no garantizan esa última regla.
6. Correcciones: escribir auditoría en la misma transacción que el cambio y prohibir edición de esa auditoría mediante permisos. No borrar registros escolares para corregirlos. Definir la política de conservación antes de producción.
7. Predicción: comprobar compatibilidad de versión de variables y modelo, origen real/simulado y estado elegible del corte. Calcular nivel con los umbrales de la versión. No inventar una probabilidad cuando faltan datos. Cortes, modelos y predicciones son inmutables para la aplicación; el DDL no impone esa inmutabilidad automáticamente.
8. Alertas: evitar abrir casos repetidos para el mismo estudiante en cada corte. Antes de crear un caso, revisar los que ya están abiertos; fijar una política de consolidación. Solo cerrar con motivo y fecha. Las actuaciones aprobadas o ejecutadas requieren aprobación identificada.
9. Cuentas: crear usuario inactivo; enviar enlace con token aleatorio, guardar solo hash y consumirlo atómicamente antes del vencimiento. Establecer contraseña con hash adecuado y activar cuenta. Nunca enviar la contraseña por correo. Los correos requieren configuración del proveedor.

## Variables propuestas para la primera versión

Contrato inicial de `cortes_predictivos.variables`, documentado y validado en la API. Cada registro representa un estudiante en una fecha de corte, asociado a su matrícula vigente. Los nombres siguientes son candidatos, pendientes de disponibilidad real:

| Variable | Cálculo y cautela |
|---|---|
| dias_lectivos_esperados | Jornadas lectivas durante la permanencia hasta el corte. |
| dias_con_registro | Jornadas esperadas con asistencia válida. |
| faltas_ultimos_20_dias_lectivos | Faltas explícitas en la ventana; no contar registros ausentes. |
| tasa_faltas_observadas | Faltas / días con registro. Acompañar con cobertura para no ocultar datos faltantes. |
| faltas_consecutivas | Racha sobre calendario lectivo. Una jornada sin registro interrumpe la certeza de la racha. |
| atrasos_ultimos_20_dias_lectivos | Atrasos explícitos. Definir tratamiento de licencia con el colegio. |
| promedio_parcial_normalizado | Resumen de puntajes / máximo × 100, solo de notas conocidas; no equivale automáticamente a nota oficial. |
| evaluaciones_calificadas | Tamaño de la evidencia que respalda el promedio. |
| cambio_promedio | Diferencia entre ventanas comparables; NULL si no hay evidencia suficiente. |
| tareas_vencidas_exigibles | Destinatarios no exentos cuyo vencimiento ya pasó. |
| tasa_tareas_no_entregadas | Solo incumplimientos confirmados / tareas exigibles con estado conocido; conservar cobertura. |
| entregas_tardias | Entregas posteriores al vencimiento y conocidas al corte. |
| incidentes_convivencia | Opcional, solo si hay criterios consistentes y disponibilidad real. |

No usar nombre, correo, RUDE ni código anónimo como variables predictoras. El código anónimo es únicamente una clave de unión. No usar situación final, fecha de abandono ni notas futuras como entradas. Las intervenciones posteriores a una alerta tampoco explican retrospectivamente esa predicción.

`fecha_corte` delimita los hechos incluidos y `disponible_hasta` delimita qué información era conocida. Una nota cargada después del corte no debe aparecer retrospectivamente como conocida. Para reconstrucción histórica, utilizar versiones de auditoría, no solo el valor actual. Si no existe fecha histórica fiable de disponibilidad, documentar que el experimento es retrospectivo y no demuestra la misma anticipación operativa. Importar una nota antigua hoy no prueba que se conociera en aquella fecha.

## Resultado de entrenamiento y evaluación

Pregunta propuesta: riesgo de abandono confirmado después del corte y hasta el cierre de la gestión. Generar la etiqueta en un proceso separado a partir de situaciones escolares verificadas. Un cero necesita seguimiento suficiente hasta el horizonte, no solo estar activo el día del corte. Un traslado no se etiqueta automáticamente como continuidad o abandono; se excluye o trata como seguimiento incompleto con política documentada.

Separar entrenamiento y evaluación por estudiantes y tiempo según el protocolo. Varios cortes o materias del mismo estudiante no son alumnos independientes. Los 30 estudiantes simulados y tres abandonos del Excel solo permiten pruebas del flujo. No se establecen umbrales, precisión ni eficacia sin validación. Comparar eventualmente XGBoost con una regla sencilla de asistencia.

## Correspondencia con tu esquema anterior

| Tabla anterior | Cambio |
|---|---|
| estudiantes | Se retira curso y contacto familiar directo; se usan matrículas y apoderados. |
| cursos | Sigue existiendo, asociado a gestión. |
| materias / usuarios | Se conservan y se conectan mediante asignaciones docentes. |
| calificaciones | Cada nota pertenece a una evaluación fechada, no solo a trimestre. |
| asistencias | Se vincula a matrícula y jornada de clase. |
| cumplimiento_tareas | Se reemplaza por tareas y entregas individuales. |
| alertas_riesgo | Se divide en cortes, modelos, predicciones y alertas. |
| recomendaciones | Se integra en intervenciones con aprobación y seguimiento. |
| citaciones | Se conserva y se relaciona con apoderado e intervención opcional. |

## Cómo aprovechar el Excel recibido

1. Usar sus códigos anónimos para crear estudiantes de prueba claramente sintéticos, sin convertirlos en RUDE. Marcar las matrículas como SIMULADO y trabajar en una base de pruebas separada.
2. Crear gestión 2025, cursos, materias y matrículas. El archivo no proporciona fechas de matrícula, docentes, calendario oficial ni fechas de aplicación de notas: no inventarlas como hechos. Cualquier dato de soporte para una demo debe identificarse como supuesto simulado.
3. Importar asistencia por fecha después de definir calendario; el archivo no demuestra qué feriados o suspensiones existieron.
4. Conservar notas trimestrales como fuente histórica de resumen. No transformarlas en evaluaciones parciales ficticias ni asignarlas a semanas anteriores. La versión operativa propuesta se alimentará con evaluaciones fechadas. Si el colegio entrega solo cierres trimestrales, añadir una tabla específica de resúmenes oficiales en la siguiente revisión.
5. Revisar notas posteriores a salidas, particularmente A004 y su tercer trimestre. Resolver inconsistencias antes de entrenar.
6. Importar situaciones finales indicando fuente simulada en la verificación. Para una versión real exigir fecha, fuente y alcance del seguimiento de continuidad.

## Alcance inicial y ampliaciones

Primero implementar usuarios, estructura escolar, matrícula, asistencia, evaluaciones, tareas y situaciones. Luego los cortes y predicciones; finalmente alertas y seguimiento. Convivencia es opcional. No se incluyen evaluaciones psicológicas clínicas: solo se diseñarán si existen personal competente, instrumentos y necesidad confirmada. El acceso familiar se realiza mediante contactos; no se presupone un portal de padres.

Pendiente de validar con el colegio: planilla oficial y sus ponderaciones, frecuencia de registro, calendario, criterio de abandono, docentes por curso y materia, información histórica disponible y canal de comunicación. Estos pendientes no impiden desarrollar el núcleo propuesto.

## Archivos y verificación

`esquema_mysql_v2.sql`: creación de 27 tablas en un esquema vacío de MySQL 8.4. No migra ni borra la base anterior. `diagrama_relaciones.mmd`: relaciones completas en Mermaid. Puede usarse el SQL para generar un diagrama EER mediante ingeniería inversa desde un script en MySQL Workbench.

Se revisaron estáticamente tablas, campos y correspondencia de claves foráneas con claves únicas. No se ejecutó el DDL en un servidor MySQL en este entorno. La importación y las reglas de FastAPI quedan pendientes de pruebas de integración. MySQL no hace atómica toda una secuencia de DDL: si la importación falla, revisar el esquema de pruebas antes de reintentar.

Referencias de compatibilidad: [claves foráneas de MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html) y [restricciones CHECK](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html).
