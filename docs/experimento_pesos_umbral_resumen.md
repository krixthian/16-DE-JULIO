# Experimento: elegir el peso de clase y el umbral con validación

Ejecución del 13 de noviembre de 2026. Script: `backend/predictivo/experimento_pesos_umbral.py`.

**Archivos de resultados:**
- `docs/experimento_pesos_umbral_resultados.csv`: métricas por repetición.
- `docs/experimento_pesos_umbral_elecciones.csv`: combinación elegida en cada pliegue.
- `docs/experimento_pesos_umbral_rejilla.csv`: rejilla fija descriptiva.

**No se modificó el modelo de producción, los umbrales del sistema ni la base de datos.**

## Pregunta
El modelo en uso compensa el desbalance (11 abandonos frente a 779) con `scale_pos_weight` = negativos / positivos del entrenamiento (≈ 70,8) y alerta desde 0,5. ¿Mejora la detección si el peso y el umbral se **eligen con validación**?

## Protocolo
- **Datos y modelo:** los mismos de `real_t1.py`: 790 matrículas, 11 abandonos, 19 variables del corte T1 sin POST_* y los mismos hiperparámetros de XGBoost (`random_state=1607`).
- **Validación externa:** StratifiedGroupKFold de 5 pliegues por estudiante × **20 repeticiones (semillas 1607 a 1626)**, los mismos pliegues del modelo en uso.
- **Combinaciones:** peso en {1, 5, 10, 20, 35, balanceado (≈ 70,8), 140} × umbral en {0,1; 0,2; 0,3; 0,4; 0,5; 0,6; 0,7}, es decir 49 combinaciones.
- **Selección anidada:** dentro de cada pliegue de entrenamiento, una CV interna de 4 pliegues por estudiante elige la combinación con mayor F1. En caso de empate gana el umbral más alto y luego el peso más cercano al balanceado. El resultado se mide solo en el pliegue externo, que **nunca participa en la elección**.
- **Comparación:** contra el modelo en uso (peso balanceado, umbral 0,5), en los mismos pliegues. El IC 95 % de ΔF1 se calcula por bootstrap pareado de estudiantes (2000 réplicas).
- **Criterio fijado antes de ejecutar:** proponer un cambio solo si el IC 95 % de ΔF1 (anidado − base) queda entero por encima de 0.
- **Validación temporal:** entrenar con 2021-2023 (221 matrículas, 9 abandonos) y evaluar en 2024 sin estudiantes compartidos (320 matrículas, 2 abandonos). La elección usa solo 2021-2023.
- **Versiones:** scikit-learn 1.4.1.post1, xgboost 2.0.3.

## Resultados: validación cruzada (media ± desviación estándar, 20 repeticiones)

| Variante | ROC AUC | AP | Sensibilidad | Precisión | F1 | Detectados de 11 | Falsas alarmas |
|---|---|---|---|---|---|---|---|
| **Base (en uso): peso balanceado, umbral 0,5** | 0,989 ± 0,020 | 0,859 ± 0,079 | 0,841 ± 0,093 | 0,774 ± 0,037 | **0,804 ± 0,057** | 9,25 | 2,70 |
| Peso y umbral elegidos con validación anidada | 0,980 ± 0,041 | 0,837 ± 0,078 | 0,809 ± 0,110 | 0,796 ± 0,059 | **0,799 ± 0,073** | 8,90 | 2,30 |

- **ΔF1 (anidado − base): −0,003, IC 95 % [−0,152; +0,133].** El intervalo incluye el 0: **no hay mejora distinguible.**
- La base reproduce exactamente las métricas del modelo en uso, así que la comparación usa el mismo pipeline.
- **Estabilidad de la elección:** en 100 pliegues se eligieron **34 combinaciones distintas**. La más frecuente, peso balanceado con umbral 0,7, aparece solo en 19.
  - Peso elegido: balanceado 38 veces, 10 → 14, 20 → 13, 35 → 12, 140 → 10, 5 → 7, 1 → 6.
  - Umbral elegido: 0,7 → 38, 0,6 → 18, 0,5 → 16, 0,4 → 10, 0,3 → 9, 0,2 → 6, 0,1 → 3.
  - Con 11 casos no existe una combinación claramente mejor.

## Validación temporal 2021-2023 → 2024

| Variante | Peso | Umbral | AP | Detectados de 2 | Falsas alarmas |
|---|---|---|---|---|---|
| Base | balanceado | 0,5 | 0,141 | 2 | 10 |
| Elegido con validación | 10 | 0,7 | 0,141 | 2 | 10 |

El resultado es idéntico: los datos de 2021-2023 son perfectamente separables por el promedio T1, y cualquier peso o umbral razonable marca a los mismos estudiantes.

## Rejilla fija (descriptiva: NO sirve para decidir)
Media de 20 repeticiones de algunas combinaciones evaluadas directamente en los pliegues externos (tabla completa en `experimento_pesos_umbral_rejilla.csv`):

| Peso | Umbral | F1 | Detectados | Falsas alarmas | AP |
|---|---|---|---|---|---|
| 1 (sin balanceo) | 0,5 | 0,648 | 5,50 | 0,35 | 0,862 |
| 5 | 0,5 | 0,826 | 8,75 | 1,35 | 0,868 |
| 10 | 0,5 | 0,811 | 8,75 | 1,70 | 0,869 |
| **balanceado (en uso)** | **0,5** | **0,804** | **9,25** | **2,70** | **0,859** |
| 140 | 0,5 | 0,797 | 9,25 | 2,90 | 0,852 |
| 1 (sin balanceo) | 0,3 | 0,812 | 8,90 | 1,90 | 0,862 |
| balanceado | 0,3 | 0,783 | 9,35 | 3,55 | 0,859 |

La combinación con mejor F1 en esta tabla, peso 5 con umbral 0,5 (0,826), está **elegida a posteriori sobre los mismos datos de evaluación**. Por eso no es una mejora válida: cuando la elección se hace sin ver esos datos (validación anidada), la ventaja desaparece.

## Conclusión
1. **Elegir el peso y el umbral con validación no mejora el modelo:** F1 de 0,799 frente a 0,804, con un IC de la diferencia de [−0,152; +0,133]. Se mantiene el modelo en uso: peso balanceado y umbral 0,5.
2. **El peso casi no cambia el orden de los estudiantes:** la AP está entre 0,852 y 0,869 para todos los pesos. Lo que cambia es dónde caen los puntajes, y por eso el peso y el umbral se compensan. Un peso menor con el mismo umbral alerta menos: más precisión y menos detección.
3. **El umbral 0,5 con peso balanceado es un buen equilibrio:** detecta 9,25 de 11 abandonos con 2,7 falsas alarmas. Las combinaciones con menos falsas alarmas detectan menos abandonos.
4. **Con 11 abandonos, la elección es inestable** (34 combinaciones distintas en 100 pliegues), y las diferencias de pocas centésimas son ruido.
5. **En la validación temporal no hay ninguna diferencia.**

**Decisión:** se mantiene `scale_pos_weight` = negativos / positivos con umbral 0,5 (nivel MEDIO), y 0,8 para la prioridad ALTA, como propuesta a validar con Dirección.

## Reproducir
Desde `backend` (unos 5 minutos):

```powershell
python -m predictivo.experimento_pesos_umbral --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
```
