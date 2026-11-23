# Matriz de operacionalización de variables

Sistema de alerta temprana del riesgo de abandono escolar, U.E. "16 de Julio" (primaria). Versión del 23/11/2026.

**Criterio**, según la observación del docente revisor:
- una **variable** es un factor de riesgo (por ejemplo, el rendimiento académico);
- los **indicadores** son cómo se mide (por ejemplo, la nota de cada una de las 9 áreas).

Así, las 9 notas por área, el promedio, la nota más baja y las áreas por debajo de 51 son **una sola variable con 12 indicadores**.

Cada indicador lleva entre paréntesis el **nombre exacto de la columna en el software**, para que el documento y el sistema coincidan.

**Uso**, en la última columna:

| Sigla | Significado |
|---|---|
| **M** | Modelo en uso (`backend/predictivo/real_t1.py`, corte al 30 de abril) |
| **R** | Indicador calculado desde los registros pedagógicos originales, día por día y actividad por actividad (`backend/predictivo/variables_detalladas.py` y `dataset_institucion.py`) |
| **S** | Indicador que el sistema calcula con sus propios registros para reentrenar el modelo (`backend/predictivo/features.py` y `asistencia_materia.py`, versión `primaria-materia-v2`) |

## Variables de riesgo

### Dimensión académica

**1. Rendimiento académico.** Nivel de logro del estudiante en las 9 áreas al cierre del período observado.
- **Indicadores:**
  - nota de cada área (`CNAT_T1`, `LCO_T1`, `SOC_T1`, `APV_T1`, `EFI_T1`, `EMU_T1`, `MAT_T1`, `TTG_T1`, `VER_T1`);
  - promedio (`promedio_T1`), nota más baja (`nota_minima_T1`), áreas con nota menor a 51 (`n_areas_bajo_51_T1`);
  - en el sistema: promedio normalizado (`promedio_notas`) y proporción de notas bajas (`proporcion_notas_bajas`).
- **Escala:** 0 a 100 (escala de valoración de la Ley 070; aprobación desde 51) y conteos.
- **Fuente:** registro pedagógico (centralizador) y módulo de calificaciones.
- **Uso:** M, R, S.

**2. Desempeño por dimensión.** Logro en cada dimensión de evaluación del currículo, por área.
- **Indicadores:**
  - SABER, HACER y DECIDIR de cada área (`<ÁREA>_saber`, `<ÁREA>_hacer`, `<ÁREA>_decidir`);
  - medias por dimensión (`saber_media`, `hacer_media`, `decidir_media`).
- **Escala:** proporción del puntaje, de 0 a 1.
- **Fuente:** registro pedagógico (hojas de evaluación por área).
- **Uso:** R.

**3. Evolución del aprendizaje.** Cambio del rendimiento dentro del período: si mejora o cae.
- **Indicadores:**
  - tendencia de las actividades por área (`<ÁREA>_tendencia`) y media (`tendencia_actividades`);
  - áreas en caída (`areas_en_caida`);
  - actividades con menos del 51 % (`<ÁREA>_bajas`, `actividades_bajas`);
  - diferencia entre áreas (`dispersion_areas`);
  - en el sistema: cambio de notas en el tiempo (`cambio_notas`).
- **Escala:** pendiente (positiva sube, negativa cae), conteos y desviación estándar.
- **Fuente:** registro pedagógico y módulo de calificaciones.
- **Uso:** R, S.

**4. Cumplimiento de tareas.** Responsabilidad con las tareas asignadas.
- **Indicadores:** tareas vencidas (`tareas_vencidas`), proporción entregada (`proporcion_entregas`), no entregada (`proporcion_no_entregadas`) y entregada tarde (`proporcion_entregas_tardias`), cobertura del registro (`cobertura_tareas`), por revisar (`tareas_por_revisar`).
- **Escala:** proporciones de 0 a 1 y conteos.
- **Fuente:** módulo de seguimiento de tareas.
- **Uso:** S.

### Dimensión de actitud

**5. Actitud y autopercepción.** Disposición del estudiante hacia el aprendizaje y la convivencia en el aula.
- **Indicadores:**
  - SER de cada área: respeto, interés, asistencia a clases (`<ÁREA>_ser`), con su media (`ser_media`) y su mínimo (`ser_minimo`);
  - autoevaluación por área (`<ÁREA>_auto`) y media (`autoevaluacion_media`).
- **Escala:** SER de 0 a 1 (indicadores de 1 a 5) y autoevaluación de 0 a 10.
- **Fuente:** registro pedagógico (dimensión SER y autoevaluación).
- **Uso:** R.

### Dimensión de asistencia

**6. Asistencia.** Presencia del estudiante en las clases.
- **Indicadores:**
  - % de asistencia (`tasa_asistencia_T1`) y faltas (`faltas_T1`);
  - proporción de faltas por mes (`faltas_feb`, `faltas_abr`);
  - en el sistema: proporción de faltas (`proporcion_faltas`), faltas injustificadas (`proporcion_faltas_injustificadas`), cobertura (`cobertura_asistencia`), **% de asistencia por materia** (`asistencia_materia_media`, `asistencia_materia_minima`), **materias con asistencia menor al 80 %** (`materias_asistencia_baja`), horas registradas por materia (`clases_materia_observadas`).
- **Escala:** proporciones de 0 a 1 y conteos. **Por materia: clases asistidas ÷ clases dictadas de esa materia.**
- **Fuente:** registro pedagógico (asistencia diaria A/F/R/L) y módulos de asistencia diaria y por materia.
- **Uso:** M, R, S.

**7. Patrón de inasistencia.** Cómo se distribuyen las faltas en el tiempo; detecta el alejamiento progresivo.
- **Indicadores:**
  - tendencia semanal de las faltas (`tendencia_faltas`);
  - faltas en las últimas 4 semanas (`faltas_ultimas_4_semanas`) y su cambio frente a las primeras 4 (`cambio_faltas_final_inicio`);
  - racha más larga de faltas seguidas (`racha_max_faltas`, `racha_faltas`) y racha al cierre (`racha_final_faltas`);
  - faltas en lunes o viernes (`faltas_lunes_viernes`).
- **Escala:** pendiente, proporciones y días.
- **Fuente:** registro pedagógico (asistencia día por día) y módulo de asistencia.
- **Uso:** R, S.

**8. Puntualidad.** Llegadas tarde y su evolución.
- **Indicadores:** atrasos (`atrasos_T1`, `proporcion_atrasos`), retrasos en las últimas 4 semanas (`retrasos_ultimas_4_semanas`).
- **Escala:** conteos y proporciones.
- **Fuente:** registro pedagógico y módulo de asistencia.
- **Uso:** M, R, S.

**9. Licencias.** Ausencias con permiso, incluidas las del estudiante que llega y se retira.
- **Indicadores:** licencias (`licencias_T1`), **días con licencia parcial** (`dias_licencia_parcial`).
- **Escala:** conteos.
- **Fuente:** registro pedagógico y módulo de asistencia por materia (por hora).
- **Uso:** M, R, S.

### Dimensión de seguimiento

**10. Citaciones.** Llamados a la familia por motivos académicos o de conducta, según su origen.
- **Indicadores:**
  - total (`citaciones_total`);
  - por dirección (`citaciones_direccion`), por orientación (`citaciones_orientacion`) y por docentes de materia (`citaciones_docente_materia`);
  - materias con citación (`materias_con_citacion`);
  - máximo en una sola materia (`citaciones_max_una_materia`).
- **Escala:** conteos.
- **Fuente:** módulo de citaciones (origen y materia).
- **Uso:** S.

**11. Convivencia y seguimiento familiar.** Incidentes de conducta y respuesta de la familia.
- **Indicadores:** incidentes registrados (`incidentes_registrados`), reuniones convocadas y atendidas (`contexto_reuniones_*`), contactos realizados y respondidos (`contexto_contactos_*`), acuerdos evaluables y cumplidos (`contexto_acuerdos_*`).
- **Escala:** conteos.
- **Fuente:** módulos de convivencia y ficha de permanencia.
- **Uso:** S.

### Dimensión de contexto

**12. Contexto del estudiante.** Condiciones personales y del entorno de estudio.
- **Indicadores:**
  - edad al 31 de marzo (`edad_31marzo`), que permite ver sobreedad, y grado (`grado`);
  - ficha de permanencia (`contexto_*`): actividades propuestas, iniciadas y completadas; participación en clase; dificultades observadas de lectura, escritura y cálculo; apoyo en casa, espacio, internet y dispositivo para estudiar; adulto referente; repitencias, interrupciones y cambios de escuela previos; dificultades de integración, acoso, desmotivación y necesidad de apoyo emocional reportados.
- **Escala:** años, grado de 1 a 6, conteos y valores 0/1.
- **Fuente:** dataset (edad y grado) y ficha de permanencia (`contextos_permanencia`).
- **Uso:** M (edad y grado), S.

## Datos del estudiante que no son variables de riesgo

| Dato | Indicador | Uso | Observación |
|---|---|---|---|
| Género | `genero_f` | M | No es accionable y su peso en el modelo es prácticamente nulo. Se propone retirarlo como predictor y usarlo solo para verificar que el sistema trate igual a niños y niñas. |

## Variable dependiente (lo que se quiere anticipar)

| Variable | Definición | Indicador |
|---|---|---|
| **Abandono dentro de la gestión** | El estudiante deja de asistir durante el año, en el 2.º o 3.er trimestre | `y_abandono_intra_anual` = 1 si no asistió ningún día del T3 o sus notas del T3 quedan en 18; `trimestre_caida` indica en qué trimestre ocurrió |

## Lo que se excluye a propósito

- **Información posterior al corte** (notas y asistencia del T2, T3 y anual, columnas `POST_*`): sería fuga de información, porque no existe en la fecha en que se predice.
- **Datos personales:** nombres, carnet, RUDE, fecha de nacimiento, teléfono y dirección. Los estudiantes se identifican con un código anónimo.
- **Gestión, paralelo y códigos:** no describen al estudiante.

## Resumen

| Dimensión | Variables | Indicadores en el modelo en uso (M) | Indicadores en los registros (R) | Indicadores en el sistema (S) |
|---|---|---|---|---|
| Académica | 4 (rendimiento, desempeño por dimensión, evolución, tareas) | 12 | 64 | 10 |
| Actitud | 1 | 0 | 21 | 0 |
| Asistencia | 4 (asistencia, patrón, puntualidad, licencias) | 4 | 13 | 12 |
| Seguimiento | 2 (citaciones, convivencia y familia) | 0 | 0 | 13 |
| Contexto | 1 | 2 (+ género) | 2 (+ género) | 24 |
| **Total** | **12 variables de riesgo** | **19 indicadores** | **101 indicadores** | **59 indicadores** |

Detalle de los registros (R):
- **Académica (64):** los 12 del modelo; SABER, HACER y DECIDIR por área (27); tendencia y actividades bajas por área (18); 7 resúmenes (medias de SABER, HACER y DECIDIR, tendencia media, áreas en caída, actividades bajas, diferencia entre áreas).
- **Actitud (21):** SER y autoevaluación por área (18) y 3 resúmenes.
- **Asistencia (13):** los 4 del modelo y 9 de asistencia día por día.

El experimento "desglosado" usa 91 de ellos: los 19 del modelo, los 9 de asistencia día por día y los 63 por área, sin los 10 resúmenes.

**Resultado con los registros completos (1889 matrículas, 11 abandonos):** ningún conjunto de indicadores anticipa el abandono al 30 de abril, ni los 19, ni los 38 por dimensión, ni los 91 desglosados (`docs/experimento_desglosado.json`). Por eso se evalúa el **seguimiento continuo**: recalcular el riesgo en cada mes con lo acumulado hasta esa fecha.
