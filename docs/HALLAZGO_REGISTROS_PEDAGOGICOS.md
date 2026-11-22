# Hallazgo: lo que muestran los registros pedagógicos originales

Análisis del 22 de noviembre de 2026, en respuesta a las observaciones del docente revisor ("el análisis es superficial; hay que mirar la asistencia y las notas en detalle").

- **Script:** `backend/predictivo/analisis_registros.py`.
- **Reporte:** `docs/analisis_registros_detallados.json`, con cifras agregadas y sin datos personales.
- **Fuente:** registros pedagógicos digitales (Excel) **entregados por la Dirección de la U.E. "16 de Julio"**:
  - 34 cursos, 2021-2025 (27 de 2021-2024 y 7 de 2025);
  - **asistencia día por día** (A / F / R / L por fecha) de febrero a noviembre;
  - **notas por actividad** en cada dimensión (SER, SABER, HACER, DECIDIR) y autoevaluación.

**No se modificó el modelo en uso ni la base de datos.**

## Método

- **Lectura:** `backend/predictivo/registros_pedagogicos.py`. No se lee la hoja de filiación (carnet, RUDE, teléfonos, direcciones) y los nombres no se devuelven.
- **Emparejamiento sin nombres:** `backend/predictivo/emparejar_registros.py`. Cada estudiante se identifica por su curso y sus 9 notas del 1.er trimestre, que ya están en el dataset anonimizado. Resultado: **790 de 790 matrículas emparejadas**. En todas, las faltas, retrasos y licencias de febrero a abril coinciden con los totales del dataset.
- **Variables detalladas del 1.er trimestre:** `backend/predictivo/variables_detalladas.py`, 19 variables:
  - asistencia en el tiempo: faltas por mes, tendencia semanal, últimas 4 semanas, rachas, lunes y viernes, retrasos recientes;
  - notas por dimensión y su evolución: SABER, HACER, DECIDIR, tendencia de las actividades, áreas en caída;
  - actitud: SER (respeto, interés, asistencia) y autoevaluación.

## Hallazgos

### 1. Las notas del 1.er trimestre de quienes abandonaron son "planas"

| Señal | Abandonaron (11) | Continuaron (779) |
|---|---|---|
| Notas casi iguales en las 9 áreas (desviación < 4 puntos de 100) | **11** | **1** |
| Desviación mediana entre áreas | 2,8 | 10,3 (el 5 % más parejo: 6,8) |
| SER exactamente 3 de 5 en todas las áreas | 5 | 0 |
| Autoevaluación exactamente 6,0 | 7 | 0 |

Un estudiante tiene normalmente notas distintas entre materias. Quienes abandonaron tienen notas casi idénticas, entre 62 y 66 en todas las áreas, con SER y autoevaluación repetidos. Esto indica que **sus notas se registraron de forma estándar**, no actividad por actividad.

### 2. El abandono figura desde el último día de un mes

- **Abandonos en el T2:** de los 11 abandonos, 10 asistieron alguna vez, y esos 10 tienen su **última asistencia el último día de clases de un mes**: fin de mayo para los 8 de este grupo que asistieron (el noveno no asistió ningún día del año).
- **Abandonos en el T3:** los 2 tienen su última asistencia a fin de agosto.
- Desde el día siguiente, todos tienen **falta todos los días** hasta noviembre.

### 3. Ningún estudiante que continuó faltó 3 días seguidos

En aproximadamente 160 días de clase, la racha más larga de faltas de los 779 que continuaron es de **2 días** (34 estudiantes). Ninguno tiene 3 o más.

### 4. La asistencia del 1.er trimestre no anticipa el abandono

Modelos con **solo asistencia**, sin notas, con la misma validación (5 pliegues por estudiante × 20 repeticiones):

| Variables | AUC | AP | Detecta (de 11) | Falsas alarmas |
|---|---|---|---|---|
| Asistencia total del T1 | 0,51 | 0,016 | 0,2 | 51,0 |
| Asistencia total + día por día | 0,59 | 0,025 | 0,4 | 29,3 |
| Azar | 0,50 | 0,014 | — | — |

Quienes abandonaron asistían con normalidad de febrero a abril: 9 de 11 abandonaron en el T2.

## Qué significa

1. **El patrón que aprende el modelo T1 (promedio de 62 a 66, sin áreas reprobadas) es en buena parte un patrón de registro.** Corresponde a las notas estándar de quienes se fueron, no a una señal temprana de su comportamiento. Esto explica por qué las métricas son tan altas (AP 0,86) y por qué la asistencia no aporta.
2. **No se agregaron al modelo variables de "uniformidad" de notas.** Darían una separación casi perfecta, pero sería inflar las métricas con un artefacto del registro.
3. **La regla "k faltas seguidas"** detecta 11 de 11 sin falsas alarmas en estos registros, pero **ese resultado no es una validación**:
   - el abandono figura como faltas continuas desde fin de mes;
   - ningún estudiante que continuó tiene rachas de 3 o más.

   Su utilidad real se medirá con la asistencia que el sistema registre día a día.
4. **El sistema y la metodología siguen siendo válidos:** validación por estudiante, intervalos, líneas base, explicaciones y seguimiento. Lo que no se puede afirmar con estos datos es **cuánto anticipa el modelo en la realidad**.

## Pendiente con la escuela

Confirmar con la Dirección **cómo se completan las notas y la asistencia de un estudiante que deja de asistir**: si se llenan al cierre del trimestre con valores estándar, si la fecha de "última asistencia" es real o de cierre de mes, y si las faltas de varios días seguidos se registran como tales.

## Reproducir

Desde `backend` (aproximadamente 1 minuto). Necesita los registros originales en la PC del autor; no están en GitHub.

```powershell
python -m predictivo.analisis_registros --registros "C:/Users/Cristhian/Documents/DATOS_HISTORICO" "C:/Users/Cristhian/Documents/DATOS" --salida ../docs/analisis_registros_detallados.json
```
