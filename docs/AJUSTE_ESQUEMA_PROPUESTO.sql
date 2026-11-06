-- PROPUESTA de ajuste del esquema alerta_temprana_v2 (actividad 19), 2026-11-06.
-- NO se ha aplicado. Revisar antes de ejecutar; solo contiene cambios NO destructivos.
-- No incluye DELETE, TRUNCATE, DROP ni cambios de tipo. No toca datos.
--
-- Diagnóstico (ver docs/REVISION_ESQUEMA_BD.md):
--   * La base real, models.py y database_schema_actual.sql coinciden: 28 tablas, 47 FK, 40 CHECK.
--   * Con el volumen actual (790 predicciones, 13 alertas) todas las consultas de /alertas,
--     /dashboard y /reportes usan índices, salvo un recorrido completo de `alertas` (13 filas).
--   * Los índices siguientes son opcionales: solo aportan cuando crezcan las alertas
--     (varias gestiones con cohorte actual). Se pueden dejar para después de la defensa.

USE alerta_temprana_v2;

-- 1) Filtro y orden de /alertas por estado (hoy: type=ALL sobre alertas).
--    Beneficio esperado: bajo ahora; útil con cientos de alertas.
CREATE INDEX ix_alertas_estado_creada ON alertas (estado, creada_en);

-- 2) Panel y ranking: predicciones del modelo vigente agrupadas por nivel y ordenadas por puntaje.
--    Hoy se resuelve con el índice de la FK modelo_id + el único (corte_id, modelo_id).
--    Beneficio esperado: bajo ahora; útil si se registran varios modelos.
CREATE INDEX ix_predicciones_modelo_nivel_prob ON predicciones (modelo_id, nivel, probabilidad);

-- 3) Conteo de intervenciones por estado dentro de cada alerta (tarjetas y reportes).
--    Beneficio esperado: bajo ahora (0 intervenciones); útil cuando se registren seguimientos.
--
-- Si se aplican, añadir los mismos Index(...) en backend/models.py y regenerar
-- database_schema_actual.sql para que los tres sigan coincidiendo.
CREATE INDEX ix_intervenciones_alerta_estado ON intervenciones (alerta_id, estado);

-- Verificación después de aplicar (solo lectura):
-- SHOW INDEX FROM alertas; SHOW INDEX FROM predicciones; SHOW INDEX FROM intervenciones;
-- EXPLAIN SELECT * FROM alertas WHERE estado = 'NUEVA' ORDER BY creada_en;

-- Reversión, si hiciera falta (quita SOLO los índices creados arriba, no datos):
-- DROP INDEX ix_alertas_estado_creada ON alertas;
-- DROP INDEX ix_predicciones_modelo_nivel_prob ON predicciones;
-- DROP INDEX ix_intervenciones_alerta_estado ON intervenciones;

-- Tablas y columnas SIN USO en el código actual: NO se proponen cambios.
-- Se mantienen porque forman parte del diseño de la tesis (28 tablas) y de módulos futuros:
--   apoderados (2 filas), estudiante_apoderado, citaciones, notificaciones, tokens_acceso.
-- Columnas sin referencia en el código: evaluaciones.ponderacion, predicciones.generada_en (tiene DEFAULT),
--   contextos_permanencia.ventana_desde / instrumento_version, registros_convivencia.categoria.
-- Eliminar cualquiera de ellas sería destructivo y rompería la correspondencia con la tesis.
