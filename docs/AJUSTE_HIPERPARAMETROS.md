# Objetivo 2: ajuste de hiperparámetros de XGBoost

Ejecución del 4 de noviembre de 2026 sobre el dataset real (790 matrículas, 523 estudiantes, 11 abandonos de 9 estudiantes). Código: `backend/predictivo/ajuste_real.py`. Artefactos: `backend/artifacts/real_t1_ajuste_v1/`, excluidos de Git. Cifras agregadas, sin datos personales.

## Protocolo

- **Validación anidada agrupada por estudiante.** Bucle externo: StratifiedGroupKFold de 5 pliegues × 20 repeticiones (semilla 1607 + repetición), los mismos pliegues que la versión base. Bucle interno: StratifiedGroupKFold de 4 pliegues solo sobre el entrenamiento externo.
- **Selección.** Se elige la configuración con mayor average precision interna. Los empates se resuelven a favor del modelo más simple.
- **Espacio (108 configuraciones).** max_depth {2, 3, 4} × learning_rate {0,03; 0,05; 0,1} × n_estimators {50, 80, 150} × min_child_weight {1, 3} × subsample = colsample_bytree {0,8; 1,0}. scale_pos_weight se calcula solo con el entrenamiento y la semilla es 1607.
- **Comparación.** XGBoost base (80 árboles, profundidad 3, lr 0,05), regresión logística y la regla de promedio_T1 se evalúan en los mismos pliegues externos.
- **Umbral.** 0,5 fijo; no se ajusta con los datos de evaluación.
- **Calibración.** Sigmoide e isotónica, ajustadas con las predicciones internas fuera de pliegue y aplicadas al pliegue externo.
- **Intervalos.** IC 95 % por bootstrap de estudiantes (2000 réplicas). Las diferencias entre modelos usan las mismas réplicas (pareadas).
- **Criterio de adopción, fijado antes de ejecutar.** El modelo ajustado se adopta solo si el IC 95 % pareado de AP (ajustado − base) queda entero por encima de 0. Una calibración se adopta solo si el IC 95 % de Brier (calibrado − sin calibrar) queda entero por debajo de 0 sin empeorar la AP de forma distinguible.

## Resultados (validación anidada, umbral 0,5)

| Modelo | ROC-AUC [IC 95 %] | AP [IC 95 %] | Sensibilidad | Precisión | F1 | % marcados | Brier |
|---|---|---|---|---|---|---|---|
| XGBoost base | 0,989 [0,90-1,00] | 0,859 [0,53-1,00] | 0,84 | 0,77 | 0,80 | 1,5 % | 0,0049 |
| XGBoost ajustado | 0,982 [0,84-1,00] | 0,854 [0,48-1,00] | 0,83 | 0,76 | 0,79 | 1,5 % | 0,0067 |
| Base + sigmoide | 0,961 [0,73-1,00] | 0,828 [0,46-1,00] | 0,75 | 0,79 | 0,77 | 1,3 % | 0,0047 |
| Ajustado + sigmoide | 0,957 [0,73-1,00] | 0,828 [0,46-1,00] | 0,72 | 0,86 | 0,77 | 1,2 % | 0,0048 |
| Ajustado + isotónica | 0,956 [0,78-1,00] | 0,767 [0,38-1,00] | 0,72 | 0,80 | 0,75 | 1,3 % | 0,0053 |
| Regresión logística | 1,000 [1,00-1,00] | 0,974 [0,85-1,00] | 1,00 | 0,66 | 0,80 | 2,1 % | 0,0059 |
| Regla promedio T1 | 0,971 [0,96-0,98] | 0,303 [0,11-0,51] | 0,95 | 0,28 | 0,43 | 4,7 % | — |

Las métricas del base coinciden exactamente con la versión `real_t1_v1`, porque se usan los mismos pliegues externos.

**Diferencias pareadas (IC 95 %):**

| Comparación | ΔAP [IC 95 %] | ΔAUC [IC 95 %] | ΔBrier [IC 95 %] |
|---|---|---|---|
| Ajustado − base | −0,005 [−0,201; +0,156] | −0,007 [−0,118; +0,048] | +0,002 [−0,002; +0,007] |
| Base − logística | −0,115 [−0,420; +0,046] | — | — |
| Sigmoide − base (sin calibrar) | — | — | −0,000 [−0,002; +0,002] |

**Matriz de confusión media (de 790):**

| Modelo | Detectados | No detectados | Falsas alarmas | Verdaderos negativos |
|---|---|---|---|---|
| Base | 9,2 | 1,8 | 2,7 | 776,3 |
| Ajustado | 9,1 | 1,9 | 3,0 | 776,0 |

**Estabilidad de la elección:** 43 configuraciones distintas en 100 pliegues externos. La más frecuente (d2, lr 0,1, 150 árboles) aparece solo en el 8 %, y la combinación exacta del base en el 0 %. Por parámetro: profundidad 4 en el 45 %, lr 0,1 en el 46 %, 150 árboles en el 51 %, min_child_weight 1 en el 61 % y subsample 0,8 en el 91 %. Con 11 casos, ninguna configuración domina.

## Decisión

**Se ajustó y el modelo base resultó adecuado.** El ajuste no mejora de forma distinguible: el IC de ΔAP incluye el 0. Tampoco se adopta calibración: ningún IC de Brier queda por debajo de 0, y la sigmoide reduce la sensibilidad de 0,84 a 0,75 con el umbral 0,5. Se mantiene el modelo registrado `xgb-real-t1-v1-20261104155014`; no se registra una versión nueva ni se escribe en la base.

## Prueba temporal 2021-2023 → 2024

320 matrículas sin estudiantes compartidos, 2 abandonos. El bucle interno, solo con 2021-2023, eligió d2, lr 0,03, 50 árboles, min_child_weight 3.

| Modelo | AUC | AP | Detectados (umbral 0,5) | Falsas alarmas (0,5) | Detectados (0,8) | Falsas alarmas (0,8) |
|---|---|---|---|---|---|---|
| XGBoost base | 0,972 | 0,141 | 2 | 10 | 2 | 10 |
| XGBoost ajustado | 0,972 | 0,141 | 2 | 10 | 1 | 9 |
| Regresión logística | 0,972 | 0,141 | 2 | 9 | 2 | 9 |

## Umbrales (XGBoost base, media de 20 repeticiones)

| Umbral | Detectados de 11 | Falsas alarmas | Precisión | % marcados |
|---|---|---|---|---|
| 0,3 | 9,3 | 3,5 | 0,73 | 1,6 % |
| 0,5 | 9,2 | 2,7 | 0,77 | 1,5 % |
| 0,7 | 8,6 | 1,9 | 0,81 | 1,3 % |
| 0,8 | 7,3 | 0,9 | 0,89 | 1,1 % |
| 0,9 | 5,7 | 0,1 | 0,99 | 0,7 % |

**Propuesta, a validar con Dirección:**
- Mantener 0,5 como umbral de alerta (nivel MEDIO), porque bajar a 0,3 apenas añade detecciones y sí falsas alarmas.
- Usar 0,8 solo para priorizar (nivel ALTO), no para decidir si se alerta: con 0,8 se pierden en promedio 2 de cada 11 abandonos.
- La tabla es descriptiva; el umbral no se ajustó con estos datos.

## Advertencias

- En 2021-2023 todas las matrículas con promedio_T1 ≤ 66 son abandonos: separación casi perfecta que infla las métricas y hace que la regresión logística llegue a AUC 1,0.
- Solo 11 abandonos (9 estudiantes): intervalos muy amplios.
- Etiqueta de abandono inferida del cuaderno, pendiente de confirmar con Dirección.
- 2021-2023 provienen de pocos cursos con mayor tasa de abandono: posible sesgo de selección.

## Reproducir (desde `backend`)

```powershell
python -m predictivo ajustar-real --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida artifacts/real_t1_ajuste_v1
python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1
python -m predictivo metricas-ajuste --directorio artifacts/real_t1_ajuste_v1 --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx
python -m predictivo.figuras_ajuste artifacts/real_t1_ajuste_v1 ../docs/figuras
```

El segundo comando muestra el reporte en segundos. El tercero recalcula toda la validación anidada (unos 15 minutos) y confirma "ajuste reproducido exactamente".
