# Experimento: ampliar la etiqueta de abandono a "no aprueba el año"

Ejecución del 16 de noviembre de 2026. Script: `backend/predictivo/experimento_etiqueta_ampliada.py`.

**Archivos:**
- `docs/experimento_etiqueta_ampliada.json`: reporte completo.
- `docs/experimento_etiqueta_ampliada_curva.csv`: curva de aprendizaje por repetición.

**No se modificó el modelo de producción, los umbrales, las reglas RP01-RP05 ni la base de datos.**

## Motivo
Observación del ingeniero: con 11 abandonos (9 estudiantes) hay muy pocos casos. Ninguna técnica sobre esos mismos 11 casos mejoró el modelo (ajuste de hiperparámetros, calibración, SMOTE, peso y umbral). Se probó si una **etiqueta real más amplia** resuelve la falta de casos y se midió **cuánto depende el modelo de la cantidad de casos**.

## Datos y protocolo
- **Etiqueta ampliada:** `y_reprobacion` del dataset real, es decir, no aprueba el año. Tiene **35 positivos (31 estudiantes)** y **contiene los 11 abandonos**.
  - Por gestión: 2021 = 4, 2022 = 3, 2023 = 2, 2024 = 14, 2025 = 12.
  - Se usa solo como etiqueta: los predictores son las mismas 19 variables del T1, sin POST_*.
- **Validación cruzada:** igual que el modelo en uso. StratifiedGroupKFold de 5 pliegues por estudiante × 20 repeticiones (semillas 1607 a 1626), IC 95 % por bootstrap de estudiantes y umbral 0,5 fijo.
- **Líneas base:** regresión logística y reglas simples cuyo umbral se elige en el entrenamiento.
- **Prueba temporal:** entrenar con 2021-2024 y evaluar en 2025. Hay dos variantes:
  - **realista:** toda la gestión 2025 (150 matrículas, 12 casos), como se usaría el sistema;
  - **estricta:** sin estudiantes que ya estaban en el entrenamiento (36 matrículas, 1 caso).
- **Curva de aprendizaje:** misma validación cruzada, pero en cada pliegue de entrenamiento se conserva solo el 25 %, 50 %, 75 % o 100 % de los estudiantes positivos. Se evalúa siempre en el pliegue de prueba completo.
- **Versiones:** scikit-learn 1.4.1.post1 y xgboost 2.0.3. La validación del abandono reproduce exactamente las métricas del modelo en uso (AP 0,859).

## Resultados

### 1. Etiqueta ampliada (35 casos): validación cruzada

| Modelo | AUC | AP [IC 95 %] | Sensibilidad | Precisión | F1 |
|---|---|---|---|---|---|
| XGBoost | 1,000 | 0,996 [0,97-1,00] | 0,98 | 0,94 | 0,96 |
| Regresión logística | 1,000 | 0,994 [0,98-1,00] | 1,00 | 0,87 | 0,93 |
| **Regla: promedio T1 bajo** | **1,000** | **0,995 [0,98-1,00]** | 0,94 | 0,94 | **0,94** |
| Regla: áreas < 51 | 0,857 | 0,727 | 0,71 | 1,00 | 0,83 |
| Azar | 0,5 | 0,044 | — | — | — |

**Una regla simple rinde prácticamente igual que XGBoost.** La nota anual incluye la del T1: quien va mal en el T1 casi siempre reprueba. No es fuga de información, porque el T1 se conoce en la fecha de corte, pero el problema es fácil y no demuestra el valor de XGBoost.

### 2. Prueba temporal en 2025 (etiqueta ampliada)

| Variante | Modelo | Detectados | Falsas alarmas | F1 |
|---|---|---|---|---|
| Realista (150 matrículas, 12 casos) | XGBoost | 12 de 12 | 6 | 0,80 |
| | Regresión logística | 12 de 12 | 6 | 0,80 |
| | **Regla: promedio T1** | **12 de 12** | **3** | **0,89** |
| | Regla: áreas < 51 | 8 de 12 | 0 | 0,80 |
| Estricta (36 matrículas, 1 caso) | todos | 1 de 1 | 0 a 3 | no concluyente |

En 2025 la regla del promedio supera a XGBoost: detecta lo mismo con menos falsas alarmas.

### 3. Los 11 abandonos con cada modelo

| Modelo | AP para los 11 abandonos | Abandonos detectados | Total marcados |
|---|---|---|---|
| **Modelo en uso (entrenado con abandono)** | **0,859** | 9,25 | 12 |
| Modelo ampliado (entrenado con reprobación) | 0,192 | 10,45 | 37 |

El modelo ampliado marca a casi todos los abandonos, pero entre 37 estudiantes, porque pone primero a los reprobados de notas bajas. **Para encontrar el abandono, el modelo específico es mucho mejor.**

### 4. Abandono: modelos frente a reglas (mismos pliegues)

| Modelo | AP [IC 95 %] | F1 |
|---|---|---|
| XGBoost (en uso) | 0,859 [0,53-1,00] | 0,80 |
| Regresión logística | 0,974 [0,85-1,00] | 0,80 |
| Regla: promedio T1 bajo | **0,303** [0,11-0,51] | 0,43 |
| Regla: áreas < 51 | 0,104 | 0,04 |
| Azar | 0,014 | 0 |

**El abandono es el problema difícil.**
- **Por qué fallan las reglas:** los que abandonaron tenían promedios de 62 a 66, sin áreas reprobadas. La regla del promedio llega a una AP de 0,30 y la de áreas < 51 casi nunca acierta.
- **Qué logran los modelos:** XGBoost y la regresión logística combinan las 19 variables y llegan a una AP de 0,86-0,97.
- **XGBoost frente a regresión logística:** XGBoost no supera a la regresión logística; los intervalos se solapan, tal como ya estaba documentado.

### 5. Curva de aprendizaje (media ± desviación estándar, 20 repeticiones)

| Abandonos en el entrenamiento | AP (abandono) | Sensibilidad | F1 |
|---|---|---|---|
| ≈ 2,4 | 0,704 ± 0,116 | 0,50 | 0,61 |
| ≈ 4,4 | 0,739 ± 0,107 | 0,58 | 0,65 |
| ≈ 6,5 | 0,797 ± 0,067 | 0,72 | 0,75 |
| ≈ 8,8 (todos) | 0,859 ± 0,079 | 0,84 | 0,80 |

Con la etiqueta ampliada la curva se aplana pronto: AP 0,93 con 7 casos y 0,996 con 28.

**La curva del abandono sigue subiendo y no se ha aplanado.** Cada caso adicional mejora el modelo, así que la limitación es la cantidad de abandonos registrados, no el algoritmo. Es una extrapolación con pocos puntos: indica la tendencia, no cuánto mejoraría.

## Conclusiones
1. **No se adopta la etiqueta ampliada como modelo principal.** La reprobación se predice casi perfectamente con una regla simple (promedio T1 bajo). Un modelo para eso no aporta frente a la regla.
2. **El abandono es el caso difícil, y ahí el aprendizaje automático aporta:**
   - la regla del promedio llega a una AP de 0,30 y los modelos de 19 variables a 0,86-0,97;
   - los estudiantes que abandonan no tienen notas bajas, por eso no los distinguen las reglas sobre notas;
   - XGBoost queda a la par de la regresión logística, no por encima.
3. **La falta de casos es real y medible:** la curva de aprendizaje del abandono sigue subiendo. Con más gestiones registradas, el modelo debería mejorar.
4. **Uso complementario posible:** la regla "promedio T1 bajo o áreas < 51" ya cubre el riesgo de reprobación. Está en el sistema como la pestaña "Riesgo académico por reglas", sin necesidad de otro modelo.

## Reproducir
Desde `backend` (unos 4 minutos):

```powershell
python -m predictivo.experimento_etiqueta_ampliada --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
```
