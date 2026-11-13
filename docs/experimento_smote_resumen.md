# Experimento: SMOTE frente a scale_pos_weight para el desbalance de clases

Ejecución del 9 de noviembre de 2026. Script: `backend/predictivo/experimento_smote.py`. Resultados por repetición: `docs/experimento_smote_resultados.csv`. Tabla resumida: `docs/experimento_smote_resumen_tabla.csv`. Detalle por pliegue (k usado, estado del remuestreo, filas tras remuestrear): `docs/experimento_smote_pliegues.csv`. **No se modificó el modelo de producción, los umbrales, las reglas RP ni la base de datos.**

## Protocolo

- **Datos:** `data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx` (hoja DATOS_REAL), con la misma carga que `real_t1.py`. Son 790 matrículas, 523 estudiantes y **11 abandonos** (9 estudiantes), sin valores faltantes.
- **Variables y modelo:** los mismos de producción. Las 19 variables del corte T1 (sin POST_*) y el mismo XGBoost: 80 árboles, profundidad 3, lr 0,05, subsample y colsample 0,8, `random_state=1607`. Umbral fijo 0,5.
- **Validación:** la misma de `real_t1.py`. StratifiedGroupKFold de 5 pliegues agrupado por estudiante, con **20 repeticiones (semillas de partición 1607 a 1626)**. Se reporta la media y la desviación estándar entre repeticiones. Todas las variantes usan exactamente los mismos pliegues.
- **Remuestreo:** solo dentro del pliegue de entrenamiento. El pliegue de prueba y el año de prueba nunca se remuestrean. La semilla del remuestreo es la de la repetición (1607 + r).
- **k_neighbors** = `min(5, positivos de entrenamiento − 1)`. En la validación cruzada los pliegues de entrenamiento tuvieron entre 5 y 11 positivos, por lo que **k fue 4 o 5**. En la prueba temporal hubo 9 positivos y **k = 5**. BorderlineSMOTE usa además `m_neighbors=10` y `kind='borderline-1'`; ADASYN usa `n_neighbors = k`.
- **Validación temporal:** igual que `sensibilidad_real.py`. Se entrena con 2021-2023 (221 matrículas, 9 abandonos) y se evalúa en 2024 sin estudiantes compartidos (320 matrículas, 2 abandonos). Las variantes con remuestreo se repitieron con 20 semillas.
- **Versiones:** imbalanced-learn **0.12.4**, scikit-learn 1.4.1.post1, xgboost 2.0.3, Python 3.12.2.

## Variantes

| Variante | Qué hace |
|---|---|
| a) Sin balanceo | XGBoost con `scale_pos_weight = 1` |
| b) scale_pos_weight | **Línea base de producción**: peso = negativos / positivos del entrenamiento |
| c) SMOTE | Sobremuestreo sintético hasta igualar las clases |
| d) BorderlineSMOTE | SMOTE solo a partir de los positivos cercanos a la frontera |
| e) ADASYN | Sobremuestreo adaptativo, con más muestras donde la clase es más difícil |
| f) SMOTE parcial + pesos | SMOTE hasta que la minoría sea el 10 % de la mayoría, más `scale_pos_weight` sobre lo remuestreado. Se fijó antes de ejecutar, no a la vista de los resultados |

## Resultados: validación cruzada agrupada (media ± desviación estándar, 20 repeticiones)

| Variante | ROC AUC | AP | Sensibilidad | Precisión | F1 | Detectados de 11 | Falsas alarmas | ΔAP vs. b) | Reps. con AP > b) |
|---|---|---|---|---|---|---|---|---|---|
| a) Sin balanceo | 0,988 ± 0,023 | 0,862 ± 0,081 | 0,500 ± 0,108 | 0,941 ± 0,098 | 0,648 ± 0,103 | 5,50 ± 1,19 | 0,35 | +0,003 ± 0,035 | 11/20 |
| **b) scale_pos_weight (base)** | **0,989 ± 0,020** | **0,859 ± 0,079** | **0,841 ± 0,093** | **0,774 ± 0,037** | **0,804 ± 0,057** | **9,25 ± 1,02** | **2,70** | — | — |
| c) SMOTE | 0,993 ± 0,004 | 0,739 ± 0,126 | 0,705 ± 0,144 | 0,600 ± 0,110 | 0,646 ± 0,119 | 7,75 ± 1,59 | 5,20 | −0,120 ± 0,108 | 1/20 |
| d) BorderlineSMOTE | 0,995 ± 0,002 | 0,834 ± 0,070 | 0,627 ± 0,114 | 0,869 ± 0,086 | 0,722 ± 0,083 | 6,90 ± 1,25 | 1,10 | −0,024 ± 0,071 | 8/20 |
| e) ADASYN | 0,990 ± 0,005 | 0,635 ± 0,146 | 0,659 ± 0,147 | 0,479 ± 0,109 | 0,553 ± 0,119 | 7,25 ± 1,62 | 8,00 | −0,224 ± 0,129 | 0/20 |
| f) SMOTE parcial + pesos | 0,990 ± 0,017 | 0,832 ± 0,086 | 0,841 ± 0,102 | 0,713 ± 0,087 | 0,768 ± 0,080 | 9,25 ± 1,12 | 3,85 | −0,026 ± 0,049 | 4/20 |

La variante b) reproduce exactamente las métricas del modelo de producción (`real_t1_v1`: AUC 0,989, AP 0,859, F1 0,80, 9,2 detectados y 2,7 falsas alarmas). Eso confirma que la comparación usa el mismo pipeline.

## Resultados: validación temporal 2021-2023 → 2024

| Variante | AP | Sensibilidad | Detectados de 2 | Falsas alarmas |
|---|---|---|---|---|
| Todas (a a f) | 0,141 | 1,00 | 2 | 10 |

Las seis variantes dan exactamente el mismo resultado, en las 20 semillas. La razón: en 2021-2023 los 9 abandonos tienen promedio_T1 ≤ 66 y ninguna matrícula sin abandono lo tiene. Con datos perfectamente separables, cualquier variante aprende la misma frontera. Entre la probabilidad más baja de los marcados (0,67) y la más alta de los no marcados (0,03) hay tanta distancia que el balanceo no cambia qué matrículas se marcan.

## Observaciones del remuestreo

- **BorderlineSMOTE** no generó ninguna muestra en 81 de 100 pliegues de la validación cruzada ni en la prueba temporal, porque casi no hay positivos "en la frontera" (otra vez, la separación por promedio). En esos pliegues equivale a la variante a).
- **ADASYN** falló (`RuntimeError`: ningún vecino de la clase mayoritaria) en 1 de 100 pliegues de la CV y en las 20 corridas temporales. En esos casos se entrenó sin remuestreo, y queda registrado en `experimento_smote_pliegues.csv`.
- **Variables enteras:** SMOTE y sus variantes interpolan todas las variables, incluidas las enteras o binarias (grado, género, número de áreas bajo 51). Por eso generan valores no enteros. Una alternativa sería SMOTENC, que no se probó.
- **Alcance de la desviación estándar:** la desviación entre repeticiones mide solo el azar de la partición, no la incertidumbre por tener pocos casos. El IC 95 % por bootstrap de estudiantes del modelo base es mucho más amplio: AP 0,53 a 1,00 (`docs/MODELO_REAL_T1.md`).

## Conclusión

1. **SMOTE no mejora el modelo; lo empeora.** Con SMOTE la AP baja de 0,859 a 0,739 (ΔAP −0,12 y AP menor en 19 de 20 repeticiones), detecta menos abandonos (7,75 frente a 9,25) y casi duplica las falsas alarmas (5,2 frente a 2,7). ADASYN empeora aún más: AP 0,635 y 8 falsas alarmas.
2. **BorderlineSMOTE y SMOTE parcial con pesos quedan cerca de la base** (ΔAP −0,02 y −0,03), pero sin superarla. Ninguna variante mejora a la vez la AP y la detección.
3. **Las mejoras de AUC no son relevantes:** SMOTE 0,993 y BorderlineSMOTE 0,995, frente a 0,989. Son diferencias de milésimas sobre una AUC ya saturada, dentro del ruido, y van acompañadas de peor AP y peor F1 al umbral de trabajo.
4. **Sin balanceo** se pierde casi la mitad de los abandonos (5,5 de 11). Tratar el desbalance sí es necesario, y **`scale_pos_weight` es suficiente y la mejor opción probada**.
5. **En la validación temporal no hay ninguna diferencia** entre variantes, porque los datos de entrenamiento son perfectamente separables por el promedio.
6. **Las diferencias pequeñas pueden ser ruido:** con solo 11 positivos (9 estudiantes), diferencias de pocas centésimas no son distinguibles. Lo que sí es consistente entre repeticiones es el empeoramiento de SMOTE y ADASYN.

**Decisión:** se mantiene el modelo de producción con `scale_pos_weight`. SMOTE queda documentado como alternativa evaluada y descartada con evidencia.

## Reproducir

Desde `backend` (unos 60 segundos):

```powershell
python -m predictivo.experimento_smote --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
```
