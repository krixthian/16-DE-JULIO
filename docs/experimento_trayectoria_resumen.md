# Experimento de trayectoria escolar previa (23/11/2026)

**Pregunta:** ¿se puede anticipar el abandono desde febrero con lo que la escuela ya sabe del estudiante por la gestión anterior?

Script: `backend/predictivo/experimento_trayectoria.py`. Resultado completo: `docs/experimento_trayectoria.json`.

## Datos

- Dataset completo de la institución, gestiones 2022 a 2025. La gestión 2021 no tiene año anterior registrado.
- 1444 matrículas y 7 abandonos.
- Azar: AP 0,005, que es la prevalencia.

## Variables de trayectoria

Todas salen de la gestión anterior, así que existen en febrero y no son fuga de información:

- estudiante nuevo;
- repite el grado;
- desfase de edad (edad menos grado);
- abandono previo;
- reprobó la gestión anterior;
- promedio anual previo y áreas reprobadas;
- proporción de faltas del año anterior y de su último trimestre;
- gestiones que lleva en la escuela;
- edad y grado.

## Protocolo

- Validación por estudiante, 5 pliegues × 20 repeticiones.
- IC 95 % por bootstrap de estudiantes.
- Parámetros fijos y umbral 0,5.
- Criterio fijado antes de correr: la trayectoria anticipa solo si el IC 95 % de su AP queda entero por encima del azar.

## Lo que muestran los datos

| Condición | Matrículas | Abandonos |
|---|---|---|
| Repite el grado | 50 | 0 |
| Sobreedad (desfase ≥ 7) | 0 | 0 |
| Estudiante nuevo | 231 | 1 |
| Ya estaba en la escuela | 1213 | 6 |
| Abandonó la gestión anterior | 0 | 0 (ningún estudiante que abandonó volvió después) |

| Indicador del año anterior (mediana) | Abandonos | Resto |
|---|---|---|
| Promedio anual previo | 76,5 | 76 |
| Proporción de faltas en el año | 1,8 % | 1,2 % |
| Faltas en su último trimestre | 2,9 % | 1,9 % |

## Resultados (media de 20 repeticiones)

| Conjunto | Modelo | AUC [IC 95 %] | AP [IC 95 %] | Detectados (de 7) | Falsas alarmas |
|---|---|---|---|---|---|
| Trayectoria (febrero) | XGBoost | 0,41 [0,17-0,69] | 0,005 [0,002-0,012] | 0 | 76 |
| Trayectoria (febrero) | Logística | 0,43 [0,14-0,75] | 0,008 [0,002-0,045] | 1,9 | 404 |
| Global, T1 (abril) | XGBoost | 0,75 [0,53-0,91] | 0,016 [0,004-0,059] | 0 | 9 |
| Global, T1 (abril) | Logística | 0,70 [0,42-0,94] | 0,057 [0,004-0,344] | 2,8 | 109 |
| Global + trayectoria (abril) | XGBoost | 0,73 [0,50-0,93] | 0,018 [0,004-0,071] | 0 | 7 |
| Global + trayectoria (abril) | Logística | 0,61 [0,34-0,85] | 0,123 [0,002-0,481] | 1,8 | 73 |

**Conclusión: no cumple el criterio.**

- La trayectoria sola rinde igual o peor que el azar: el AUC queda por debajo de 0,5 y el AP es igual a la prevalencia.
- Sumar la trayectoria a las variables del T1 tampoco mejora de forma significativa: todos los IC de la diferencia de AP incluyen el 0.

Los abandonos de esta escuela los protagonizan estudiantes con una trayectoria normal: no repiten, no tienen sobreedad y tuvieron un año anterior típico. Dejan de asistir de golpe. Con los registros disponibles no hay variable previa que los distinga, y lo que sí funciona es detectar a tiempo la inasistencia continua (5 faltas seguidas: 11 de 11 detectados y 0 falsas alarmas).
