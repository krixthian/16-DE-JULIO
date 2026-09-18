# Ampliación de variables de permanencia escolar

Se agrega `contextos_permanencia` a `alerta_temprana_v2`. Relación: estudiantes → matrículas → contextos_permanencia; usuarios → contextos_permanencia mediante registrado_por. Una matrícula puede tener muchas fichas fechadas. Las 27 tablas previas se conservan: ahora son 28 tablas y 47 claves foráneas.

## Diccionario: 27 variables para primaria

Se retiraron los ocho campos de economía, transporte, domicilio, trabajo y cuidado. Se incorporaron quince campos escolares y se conservaron doce del diseño anterior. Son variables candidatas, no indicadores validados de abandono.

| Campo | Definición |
|---|---|
| actividades_propuestas | Cantidad de actividades de aula propuestas durante la ventana |
| actividades_iniciadas | De las propuestas, cuántas inició |
| actividades_completadas | De las iniciadas, cuántas completó |
| clases_observadas | Clases en las que el docente observó la participación |
| clases_con_participacion | De las observadas, clases con al menos una participación vinculada a la actividad; no limitar a hablar en público |
| dificultad_lectura_observada | Sí/no: dificultad observada en actividades de lectura adecuadas al grado |
| dificultad_escritura_observada | Sí/no: dificultad observada en escritura adecuada al grado |
| dificultad_calculo_observada | Sí/no: dificultad observada en cálculo adecuado al grado |
| necesita_apoyo_actividades | Sí/no: necesitó acompañamiento adicional para realizar actividades |
| reuniones_convocadas | Reuniones familiares convocadas cuya fecha ya pasó en la ventana |
| reuniones_atendidas | De las convocadas, reuniones atendidas por el apoderado |
| contactos_realizados | Intentos de contacto con el apoderado, contados una sola vez cada uno |
| contactos_respondidos | De los contactos realizados, cuántos obtuvieron respuesta hasta la observación |
| acuerdos_evaluables | Acuerdos de apoyo familiar cuyo plazo ya venció en la ventana |
| acuerdos_cumplidos | De los evaluables, acuerdos cuyo cumplimiento se verificó |
| dias_apoyo_estudio_semana | Días con acompañamiento para estudiar, semana anterior; 0–7 |
| espacio_estudio | Sí/no: dispone de lugar apropiado para estudiar |
| internet_estudio | Sí/no: acceso a internet para estudiar |
| dispositivo_estudio | Sí/no: acceso a dispositivo para estudiar |
| adulto_referente_disponible | Sí/no: cuenta con adulto de apoyo escolar |
| repitencias_previas | Repitencias anteriores a la matrícula actual |
| interrupciones_previas | Interrupciones escolares anteriores a la matrícula actual |
| cambios_escuela_previos | Cambios de escuela anteriores a la matrícula actual |
| dificultades_integracion_reportadas | Sí/no: dificultades de integración reportadas durante la ventana |
| acoso_reportado | Sí/no: se reporta que recibió acoso; no confirma el hecho |
| desmotivacion_reportada | Sí/no: desmotivación escolar reportada durante la ventana |
| necesidad_apoyo_emocional_reportada | Sí/no: necesidad de apoyo emocional reportada; no es diagnóstico |

Los conteos nuevos corresponden a ventana_desde–fecha_observacion (ambas incluidas), admiten 0–65535 y registran observaciones, no juicios de conducta. Usar los totales como denominadores: cero oportunidades significa tasa no calculable, nunca falta de participación o de apoyo. No comparar cantidades brutas entre ventanas de distinta duración. Las dificultades de aprendizaje son observaciones pedagógicas, no diagnósticos.

Todos admiten NULL: desconocido, no preguntado o no proporcionado. NULL nunca debe convertirse automáticamente en cero o no. No se inventan valores iniciales ni se completan alumnos existentes. Los tres conteos de historial previo admiten 0–255 como límite técnico, no como escala de riesgo.

## Registro y uso temporal

Cada fila incluye matrícula, ventana_desde, fecha_observacion, registrado_en, fuente, instrumento_version, origen REAL/SIMULADO y registrado_por. La fuente identifica quién aporta la información; registrado_por identifica al usuario que la ingresa. Registrar fichas nuevas completas para conservar cambios; no sobrescribir fichas históricas. La ventana describe las respuestas de periodo; los campos de semana o historial tienen sus periodos particulares definidos arriba.

Antes de implementar el formulario, acordar el cuestionario y versionarlo. No mezclar respuestas de distintas fuentes en una ficha: crear fichas independientes. No rellenar campos faltantes con una observación anterior silenciosamente.

Para un corte predictivo solo podrán seleccionarse fichas con fecha_observacion <= fecha_corte y registrado_en <= disponible_hasta. Resolver explícitamente discrepancias entre fuentes y antigüedad de las respuestas; no seleccionar una ficha posterior ni usar datos conocidos después del corte. La extracción para XGBoost aún no está implementada.

La etiqueta de abandono sigue en situaciones_escolares; un traslado no se transforma en abandono. Excluir identificadores, nombres, autor y origen del conjunto de predictores. Separar datos simulados de reales. La disponibilidad de internet o dispositivos debe interpretarse en el contexto de las tareas exigidas por el colegio.

## Alcance y siguientes pasos

Esta entrega amplía la base y los modelos del backend; no añade todavía pantalla ni API para estas fichas. No incluye entrenamiento ni validación de XGBoost. Las variables complementan notas, asistencias, tareas y convivencia ya contempladas en otras tablas.

Antes de recoger información de menores, definir con el colegio necesidad de cada pregunta y acceso por función. El futuro módulo debe restringir los datos familiares y emocionales a personal autorizado, validar fechas dentro de la matrícula, concordancia de origen con matrícula y auditar correcciones. No incorporar textos clínicos o diagnósticos al registro docente general. La evaluación psicológica profesional requiere un diseño específico; este cuestionario no la sustituye.

## Instalación y diagrama

Para actualizar el diseño anterior vacío: `python migrate_contextos_primaria.py`; comprueba que no haya fichas, respalda su definición y aplica un ALTER TABLE. Si hay fichas, se detiene para no perderlas. Para instalaciones nuevas, desde backend: `python migrate_contextos.py`. Crea únicamente la nueva tabla si no existe y verifica sus columnas. No borra ni migra registros previos. El archivo SQL incremental es `database_contextos_permanencia.sql`; el esquema completo para una instalación vacía sigue siendo `database_schema.sql`.

En Workbench, actualizar SCHEMAS para ver la tabla. Para actualizar la imagen del modelo, realizar ingeniería inversa de alerta_temprana_v2 en un modelo nuevo; la imagen database.png anterior no se actualiza automáticamente.

Los conteos de reuniones resumen hechos de seguimiento familiar previos al corte; cuando se implemente el módulo, obtenerlos de citaciones cuando sea posible para no duplicar carga. No usar respuestas o acuerdos conocidos después del corte, ni datos de intervenciones causadas por la propia predicción para validar esa misma predicción.
