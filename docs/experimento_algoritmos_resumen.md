# Experimento: ¿un algoritmo más sencillo rinde igual que XGBoost?

Ejecución del 22 de noviembre de 2026, por la observación del docente revisor: "si los datos no están desglosados, un algoritmo más sencillo podría dar mejor resultado".

- **Script:** `backend/predictivo/experimento_algoritmos.py`.
- **Reporte:** `docs/experimento_algoritmos.json`.

**No se modificó el modelo en uso ni la base.**

## Protocolo

- **Datos:** las mismas 19 variables del 1.er trimestre del modelo en uso, sin POST_*.
- **Validación:** la misma del modelo en uso. StratifiedGroupKFold de 5 pliegues por estudiante × 20 repeticiones (semillas 1607 a 1626), umbral 0,5.
- **Incertidumbre:** IC 95 % por bootstrap de estudiantes y diferencia pareada de AP frente a XGBoost.
- **Prueba temporal:** entrenar con 2021-2023 y evaluar en 2024.
- **Hiperparámetros fijados antes de ejecutar, sin búsqueda.** Con 11 abandonos, ajustar cada algoritmo sería elegir el resultado a posteriori.

| Algoritmo | Configuración |
|---|---|
| Árbol de decisión | profundidad 3, mínimo 5 por hoja, clases balanceadas |
| Random Forest | 300 árboles, mínimo 3 por hoja, clases balanceadas por submuestra |
| Regresión logística | estandarizada, clases balanceadas |
| XGBoost | parámetros del modelo en uso |

## Resultados (media de 20 repeticiones)

| Algoritmo | AUC | AP [IC 95 %] | Sensibilidad | Precisión | F1 | Detecta (de 11) | Falsas alarmas |
|---|---|---|---|---|---|---|---|
| **XGBoost (en uso)** | 0,989 | **0,859** [0,53-1,00] | 0,84 | 0,77 | 0,80 | 9,3 | 2,7 |
| Regresión logística | 1,000 | 0,974 [0,85-1,00] | 1,00 | 0,66 | 0,80 | 11,0 | 5,7 |
| Random Forest | 0,993 | 0,883 [0,61-1,00] | 0,70 | 1,00 | 0,82 | 7,7 | 0,0 |
| Árbol de decisión | 0,852 | **0,550** [0,18-0,89] | 0,71 | 0,51 | 0,59 | 7,8 | 7,6 |
| Regla: promedio T1 | 0,971 | 0,303 | 0,95 | 0,28 | 0,43 | 10,5 | 26,9 |
| Azar | 0,500 | 0,014 | — | — | — | — | — |

**Diferencia de AP frente a XGBoost**, bootstrap pareado de estudiantes:

| Algoritmo | Diferencia | IC 95 % | Lectura |
|---|---|---|---|
| Regresión logística | +0,12 | −0,05 a +0,42 | no distinguible |
| Random Forest | +0,02 | −0,08 a +0,18 | no distinguible |
| Árbol de decisión | −0,29 | −0,68 a −0,02 | **peor de forma distinguible** |

**Prueba temporal 2021-2023 → 2024** (320 matrículas, 2 abandonos): los cuatro algoritmos detectan los 2, con 9 o 10 falsas alarmas (AP 0,14 a 0,18).

## Conclusiones

1. **Un solo árbol de decisión es peor** de forma distinguible: con 11 casos, un árbol solo es inestable y da pocos puntajes distintos, así que ordena mal.
2. **La regresión logística, un método más sencillo, rinde igual que XGBoost**: la diferencia no es distinguible. Tiene la AP más alta, pero casi el doble de falsas alarmas al umbral 0,5. **Random Forest** también rinde igual.
3. **XGBoost no es superior.** Se mantiene por las explicaciones SHAP de cada alerta (lo que ve el docente) y por el manejo nativo del desbalance y de los datos faltantes. La regresión logística es una alternativa igual de válida y más simple, y queda documentada.
4. **Por qué todos rinden parecido:** las notas del T1 de quienes abandonaron se registraron de forma estándar ([HALLAZGO_REGISTROS_PEDAGOGICOS.md](HALLAZGO_REGISTROS_PEDAGOGICOS.md)), y cualquier método que use el promedio las separa. Con datos desglosados y registrados día a día, la comparación debe repetirse.

## Reproducir

Desde `backend` (unos 10 minutos):

```powershell
python -m predictivo.experimento_algoritmos --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida ../docs
```
