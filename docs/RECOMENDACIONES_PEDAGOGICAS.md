# Recomendaciones pedagógicas (reglas RP01 a RP05, versión RP-v1)

> **Propuesta pendiente de validación con docentes y Dirección.** Las reglas sugieren, no deciden. Una recomendación solo se convierte en intervención cuando un usuario de Dirección, Orientación o Administración la registra, y su ejecución la documenta una persona.

Código: `backend/predictivo/recomendaciones.py`. Endpoints: `GET /alertas/{id}/recomendaciones` y `POST /alertas/{id}/recomendaciones/{codigo}`.

## De dónde salen los datos

Cada alerta proviene de una predicción, y esa predicción tiene un corte (`cortes_predictivos.variables.indicadores`). El corte guarda los 19 indicadores del 1.er trimestre que vio el modelo. Las reglas leen esos mismos valores; no usan columnas POST_* ni datos posteriores al corte.

## Cómo se fijaron los umbrales

- **Notas:** escala de valoración de primaria de la Ley 070: ED 1-50 (en desarrollo), DA 51-68 (desarrollo aceptable), DO 69-84 (desarrollo óptimo), DP 85-100 (desarrollo pleno).
- **Faltas y atrasos:** percentil 95 de las 790 matrículas reales (faltas_T1 = 3 y atrasos_T1 = 4), calculado sin mirar quién abandonó.
- **Sin ajuste a las etiquetas:** ninguna regla se ajustó con las etiquetas de abandono, para no repetir la separación por promedio_T1 ≤ 66 que infla las métricas.

## Reglas

| Código | Nombre | Condición | Dato que la dispara (ejemplo) | Recomendación | Tipo de acción sugerido |
|---|---|---|---|---|---|
| RP01 | Rendimiento global bajo | promedio_T1 ≤ 68 (por debajo de "desarrollo óptimo") | `promedio_T1 = 62` | Plan de reforzamiento con el docente asesor y citación al apoderado para acordar apoyo en casa. | Reforzamiento pedagógico |
| RP02 | Áreas en desarrollo | Alguna área con nota < 51 | `Áreas < 51: Matemática (45), Comunicación y Lenguajes (48)` | Reforzamiento específico en las áreas indicadas, con tareas graduadas y revisión quincenal. | Reforzamiento pedagógico |
| RP03 | Inasistencia | faltas_T1 ≥ 3 o asistencia < 90 % | `faltas_T1 = 5, asistencia = 86 %` | Citación al apoderado para conocer las causas de las faltas y acordar un compromiso de asistencia. | Citación al apoderado |
| RP04 | Atrasos frecuentes | atrasos_T1 ≥ 4 | `atrasos_T1 = 5` | Entrevista con el estudiante y el apoderado sobre rutina y traslado; registrar acuerdos de puntualidad. | Entrevista |
| RP05 | Revisión de caso | Prioridad ALTA, o alerta sin otra regla activa | `nivel = ALTO` | Reunión de caso (docente asesor, orientación y Dirección) para revisar la situación y definir seguimiento. | Reunión de caso |

RP05 asegura que toda alerta tenga al menos una recomendación. Una alerta puede activar varias reglas a la vez.

## Flujo en el sistema (pantalla /alertas)

1. **Ver las reglas activas.** Al abrir una alerta se muestran las reglas que se activan, cada una con la condición y el dato concreto.
2. **Registrar como intervención.** El botón crea una intervención en estado PROPUESTA con `regla_version = RPxx@RP-v1`. Cada regla se registra una sola vez por alerta (si se repite, el sistema responde 409), y no se puede registrar sobre una alerta cerrada.
3. **Avanzar la intervención.** Pasa por APROBADA, luego EN CURSO y finalmente REALIZADA. Al marcarla como REALIZADA se registran:
   - el tipo de acción (citación, reforzamiento, entrevista, reunión de caso, derivación u otra);
   - la fecha de ejecución, que no puede ser futura;
   - qué se hizo y el resultado.
4. **Auditoría.** Cada paso queda en `auditoria_cambios` (alta y correcciones, con el antes y el después) y se ve en el historial de la alerta.

## Qué falta validar con la escuela

- Si los umbrales (68, < 51, 3 faltas, 90 %, 4 atrasos) y las acciones propuestas son adecuados para cada grado.
- Quién ejecuta cada tipo de acción y en qué plazo.
- Si RP05 debe aplicarse también a las alertas de prioridad MEDIA.
