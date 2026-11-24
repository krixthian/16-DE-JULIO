# Notas desglosadas en el modelo mensual: 15 frente a 23 variables (23/11/2026)

Prueba técnica con archivos de origen no verificado (`CONSISTENCIA_REGISTROS.md`): 1889 matrículas, 11 abandonos. No mide la predicción en estudiantes reales.

**Criterio fijado antes de entrenar:** adoptar solo si el IC 95 % de la diferencia de AP queda sobre cero en mayo, junio o julio y ningún mes queda bajo cero. Validación StratifiedGroupKFold 5 x 20 por estudiante, mismos pliegues; IC por bootstrap pareado de estudiantes.

| Corte | Azar | AP 15 | AP 23 | Diferencia (IC 95 %) | Detecta 15 / 23 (de 11) | Falsas alarmas 15 / 23 | Peso del desglose |
|---|---|---|---|---|---|---|---|
| feb | 0,006 | 0,008 | 0,008 | 0,000 (0,000 a +0,001) | 2,6 / 2,8 | 271,6 / 271,3 | 0 % |
| mar | 0,006 | 0,015 | 0,015 | 0,000 (-0,004 a +0,005) | 1,8 / 1,8 | 88,2 / 93,6 | 0 % |
| abr | 0,006 | 0,016 | 0,013 | -0,003 (-0,020 a +0,003) | 0,8 / 0,2 | 39,4 / 22,8 | 22,5 % |
| may | 0,006 | 0,009 | 0,009 | 0,000 (-0,002 a +0,004) | 0,1 / 0,1 | 36,5 / 26,4 | 17,0 % |
| jun | 0,006 | 0,803 | 0,793 | -0,010 (-0,021 a -0,001) | 8,7 / 8,6 | 6,0 / 5,5 | 4,0 % |
| jul | 0,006 | 0,791 | 0,780 | -0,011 (-0,029 a +0,004) | 8,7 / 8,6 | 4,7 / 4,3 | 8,4 % |
| ago | 0,006 | 0,754 | 0,721 | -0,033 (-0,122 a +0,015) | 8,3 / 7,7 | 4,2 / 4,7 | 13,6 % |
| sep-oct | 0,006 | 1,000 | 1,000 | 0,000 | 9,8 / 9,8 | 0 / 0 | 0 % |

**Resultado:** ningún mes mejora y junio empeora un poco. Según el criterio, no correspondía adoptarlo (ver la decisión al final). El peso del desglose mide cuánto lo usa el modelo al entrenarse, no que ayude: en abril y mayo se usa y la AP sigue en el nivel del azar.

Detalle: `experimento_desglose.json`. Reproducir (desde `backend`): `python -m predictivo.experimento_desglose`.

**Decisión del autor (23/11/2026):** se adopta igualmente como `seguimiento-mensual-v2` (23 variables), por diseño y para atender la observación de desglosar las notas, no porque mejore. El criterio estadístico fijado antes NO se cumplió y así debe informarse. La versión v1 se conserva en `artifacts/seguimiento_mensual_v1`; los casos abiertos con ella se siguen explicando con ella.
