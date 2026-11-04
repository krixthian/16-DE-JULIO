# Modelo con datos reales: corte al cierre de T1

Implementación del 4 de noviembre de 2026. Fuente: `data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx`, hoja DATOS_REAL (790 matrículas, 523 estudiantes, gestiones 2021-2025). Versión de variables `real-t1-v1`. Las cifras de este documento son agregadas; no contienen códigos ni datos personales.

## Variables y protocolo

- 19 predictores al cierre de T1: notas de las 9 áreas, promedio_T1, nota_minima_T1, n_areas_bajo_51_T1, faltas, atrasos y licencias de T1, tasa de asistencia T1 (días asistidos / días lectivos), edad al 31 de marzo, grado y género.
- Excluidas: todas las columnas POST_* (T2, T3, anual), gestión, paralelo, fuente y códigos.
- XGBoost: 80 árboles, profundidad 3, tasa de aprendizaje 0,05, semilla 1607, subsample y colsample 0,8, `scale_pos_weight` calculado solo con el pliegue de entrenamiento, umbral 0,5. Sin búsqueda de hiperparámetros ni calibración.
- Validación: StratifiedGroupKFold de 5 pliegues agrupado por estudiante, repetido 20 veces. IC 95 % por bootstrap de estudiantes (2000 réplicas). No hay holdout temporal posible porque 2025 no tiene abandonos.
- Baselines: regresión logística (estandarizada, `class_weight=balanced`), reglas sobre promedio_T1, n_areas_bajo_51_T1 y faltas_T1 (umbral elegido con F1 solo en el pliegue de entrenamiento) y "siempre continuidad".

## Resultados: abandono dentro de la gestión (11 casos, 9 estudiantes)

| Modelo | ROC-AUC [IC 95 %] | AP [IC 95 %] | Sensibilidad [IC 95 %] | Precisión | F1 | % marcados |
|---|---|---|---|---|---|---|
| XGBoost | 0,989 [0,90-1,00] | 0,859 [0,53-1,00] | 0,84 [0,45-1,00] | 0,77 | 0,80 | 1,5 % |
| Regresión logística | 1,000 [1,00-1,00] | 0,974 [0,85-1,00] | 1,00 [1,00-1,00] | 0,66 | 0,80 | 2,1 % |
| Regla promedio_T1 | 0,971 [0,96-0,98] | 0,303 [0,11-0,51] | 0,95 [0,67-1,00] | 0,28 | 0,43 | 4,7 % |
| Regla n_areas < 51 | 0,531 [0,48-0,66] | 0,104 [0,01-0,34] | 0,28 [0,00-0,71] | 0,02 | 0,04 | 19,9 % |
| Regla faltas_T1 | 0,649 [0,41-0,85] | 0,117 [0,01-0,35] | 0,11 [0,00-0,38] | 0,12 | 0,11 | 1,4 % |
| Siempre continuidad | 0,500 | 0,014 | 0 | 0 | 0 | 0 % |

XGBoost en promedio por repetición: 9,2 de 11 abandonos detectados con 2,7 falsas alarmas sobre 790 matrículas. Brier 0,005. Variables con mayor ganancia: TTG_T1, promedio_T1, APV_T1, EMU_T1.

### Sensibilidad

- **Separación casi perfecta en 2021-2023.** Las 9 matrículas de 2021-2023 con promedio_T1 ≤ 66 son abandonos y ninguna sin abandono baja de 67. En 2024 hay 2 abandonos y 12 sin abandono con promedio ≤ 66; en 2025 hay 15 sin abandono. Las métricas altas reflejan este patrón histórico; XGBoost no supera a la regresión logística y los intervalos se solapan.
- **Temporal 2021-2023 → 2024** (320 matrículas sin estudiantes compartidos, 2 abandonos): XGBoost AUC 0,97, AP 0,14, detecta 2/2 con 10 falsas alarmas (precisión 0,17, 3,8 % marcados). Es la estimación más realista para una gestión nueva.
- **Sin el caso ya ausente en T1** (1 abandono con 0 % de asistencia y notas de 18 en T1): XGBoost AUC 0,996, AP 0,93.

## No continúa la gestión siguiente (exploratorio)

Solo definido para 2024 (349 matrículas, 17 casos, causa sin confirmar y sobrestimado por los 11 cursos de 2025 no cargados). XGBoost AUC 0,53 [0,38-0,70], AP 0,058 frente a 0,049 de la tasa base: con las variables de T1 no hay señal útil para este objetivo.

## Integración en el sistema

- `modelos_predictivos`: modelo `xgb-real-t1-v1-20261104155014`, origen REAL, umbrales medio 0,5 y alto 0,8, no activado. Entrenado con las 790 filas.
- 790 `cortes_predictivos` (fecha de corte 30 de abril), 790 `predicciones` y 13 `alertas` (responsable: usuario Admin). Las predicciones de 2021-2024 se marcan `RETROSPECTIVO_EN_ENTRENAMIENTO`: son datos de entrenamiento y sus 11 alertas ALTO coinciden con los abandonos conocidos. Las 2 alertas MEDIO de 2025 son la cohorte actual. Solo se tocaron matrículas REAL, así que la limpieza de las SIMULADO no queda bloqueada.
- Pantalla `/alertas` (Admin, Director, Orientador): resumen, filtros, factores SHAP por alerta, estados e intervenciones.

```powershell
# Desde backend
python -m predictivo entrenar-real --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --salida artifacts/real_t1_v1
python -m predictivo.sensibilidad_real ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx artifacts/real_t1_v1
python -m predictivo registrar-modelo --directorio artifacts/real_t1_v1 --umbral-medio 0.5 --umbral-alto 0.8
python -m predictivo generar-alertas-real --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --modelo-id 1            # simulacro, revierte
python -m predictivo generar-alertas-real --excel ../data/DATASET_REAL_CONSOLIDADO_2021_2025.xlsx --modelo-id 1 --confirmar
```

## Limitaciones

Pocos positivos e intervalos amplios; etiqueta de abandono inferida del cuaderno y pendiente de confirmar con Dirección; 2021-2023 proceden de pocos cursos con tasa de abandono mayor (posible sesgo de selección); probabilidades sin calibrar; sin asistencia diaria.
