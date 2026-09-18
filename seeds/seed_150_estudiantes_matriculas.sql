-- Datos ficticios para probar el sistema de primaria. No son datos de entrenamiento validado.
-- Conserva los 150 nombres y códigos del archivo original.
-- 25 estudiantes por grado, paralelo A, gestión 2026.
-- Reutiliza cursos existentes y crea solamente los que faltan.
-- No modifica estudiantes o matrículas existentes: un conflicto cancela toda la carga.
-- Requiere permiso CREATE ROUTINE. Ejecutar el archivo completo en MySQL Workbench.
-- La rutina se elimina al terminar. No cambia la estructura de las tablas del sistema.
USE alerta_temprana_v2;
SET NAMES utf8mb4;
SET @confirmar_carga = 1; -- 1: guardar; 0: comprobar y revertir los registros

DELIMITER $$
CREATE PROCEDURE seed_150_primaria_2026_corregido(IN confirmar BOOLEAN)
BEGIN
 DECLARE gestion_actual BIGINT UNSIGNED;
 DECLARE responsable BIGINT UNSIGNED;
 DECLARE inicio DATE;
 DECLARE fin DATE;
 DECLARE nuevos_cursos INT DEFAULT 0;
 DECLARE nuevos_estudiantes INT DEFAULT 0;
 DECLARE nuevas_matriculas INT DEFAULT 0;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION
 BEGIN
  ROLLBACK;
  DROP TEMPORARY TABLE IF EXISTS seed150_primaria;
  RESIGNAL;
 END;
 START TRANSACTION;
 SET gestion_actual=(SELECT id FROM gestiones WHERE anio=2026);
 IF gestion_actual IS NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Falta la gestion 2026. No se ha cargado ningun registro.';
 END IF;
 SELECT fecha_inicio,fecha_fin INTO inicio,fin FROM gestiones WHERE id=gestion_actual FOR UPDATE;
 IF inicio IS NULL OR fin IS NULL OR inicio>fin OR YEAR(inicio)<>2026 OR YEAR(fin)<>2026 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Completa correctamente el calendario de la gestion 2026.';
 END IF;
 SET responsable=(SELECT MIN(id) FROM usuarios WHERE activo=1 AND rol='Admin');
 IF responsable IS NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Se necesita un administrador activo para registrar la carga.';
 END IF;
 CREATE TEMPORARY TABLE seed150_primaria (
  codigo VARCHAR(40) PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  nacimiento DATE NOT NULL,
  grado TINYINT UNSIGNED NOT NULL
 ) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
 INSERT INTO seed150_primaria VALUES
('SIM-2026-0001','Mateo','Mamani Quispe','2019-01-01',1),
('SIM-2026-0002','Lucas','Rodríguez Martínez','2018-02-02',2),
('SIM-2026-0003','Andrés','Huanca Callisaya','2017-03-03',3),
('SIM-2026-0004','Camila','Alarcón Cárdenas','2016-04-04',4),
('SIM-2026-0005','Alejandra','Ortiz Cabrera','2015-05-05',5),
('SIM-2026-0006','Isabella','Vargas Rojas','2014-06-06',6),
('SIM-2026-0007','Sebastián','Chávez Mendoza','2019-07-07',1),
('SIM-2026-0008','Bruno','Laura Yujra','2018-08-08',2),
('SIM-2026-0009','Kevin','Valdez Miranda','2017-09-09',3),
('SIM-2026-0010','Mariana','Arias Barrientos','2016-10-10',4),
('SIM-2026-0011','Natalia','Pérez Rodríguez','2015-11-11',5),
('SIM-2026-0012','Noelia','Nina Huanca','2014-12-12',6),
('SIM-2026-0013','Gabriel','Limachi Alarcón','2019-01-13',1),
('SIM-2026-0014','Diego','Suárez Ortiz','2018-02-14',2),
('SIM-2026-0015','Miguel','Flores Vargas','2017-03-15',3),
('SIM-2026-0016','Sofía','Gutiérrez Chávez','2016-04-16',4),
('SIM-2026-0017','Andrea','Colque Laura','2015-05-17',5),
('SIM-2026-0018','Tatiana','Tapia Valdez','2014-06-18',6),
('SIM-2026-0019','Joaquín','Soliz Arias','2019-07-19',1),
('SIM-2026-0020','Adrián','García Pérez','2018-08-20',2),
('SIM-2026-0021','Valentina','Salazar Nina','2017-09-21',3),
('SIM-2026-0022','Fernanda','Villca Limachi','2016-10-22',4),
('SIM-2026-0023','Renata','Rivero Suárez','2015-11-23',5),
('SIM-2026-0024','Santiago','Condori Mamani','2014-12-24',6),
('SIM-2026-0025','Martín','Romero Gutiérrez','2019-01-25',1),
('SIM-2026-0026','Cristian','Ticona Colque','2018-02-26',2),
('SIM-2026-0027','Luciana','Arce Tapia','2017-03-27',3),
('SIM-2026-0028','Paola','Velasco Soliz','2016-04-01',4),
('SIM-2026-0029','Jimena','López García','2015-05-02',5),
('SIM-2026-0030','Nicolás','Paredes Salazar','2014-06-03',6),
('SIM-2026-0031','Daniel','Marca Villca','2019-07-04',1),
('SIM-2026-0032','Luis','Soria Rivero','2018-08-05',2),
('SIM-2026-0033','Daniela','Choque Condori','2017-09-06',3),
('SIM-2026-0034','Carla','Sánchez Romero','2016-10-07',4),
('SIM-2026-0035','Rocío','Apaza Ticona','2015-11-08',5),
('SIM-2026-0036','Thiago','Molina Arce','2014-12-09',6),
('SIM-2026-0037','Samuel','Méndez Velasco','2019-01-10',1),
('SIM-2026-0038','Álvaro','Fernández López','2018-02-11',2),
('SIM-2026-0039','Gabriela','Aguilar Paredes','2017-03-12',3),
('SIM-2026-0040','Micaela','Copa Marca','2016-04-13',4),
('SIM-2026-0041','Mateo','Soria Rivero','2015-05-14',5),
('SIM-2026-0042','Lucas','Choque Condori','2014-06-15',6),
('SIM-2026-0043','Andrés','Sánchez Romero','2019-07-16',1),
('SIM-2026-0044','Camila','Apaza Ticona','2018-08-17',2),
('SIM-2026-0045','Alejandra','Molina Arce','2017-09-18',3),
('SIM-2026-0046','Isabella','Méndez Velasco','2016-10-19',4),
('SIM-2026-0047','Sebastián','Fernández López','2015-11-20',5),
('SIM-2026-0048','Bruno','Aguilar Paredes','2014-12-21',6),
('SIM-2026-0049','Kevin','Copa Marca','2019-01-22',1),
('SIM-2026-0050','Mariana','Escobar Soria','2018-02-23',2),
('SIM-2026-0051','Natalia','Quispe Choque','2017-03-24',3),
('SIM-2026-0052','Noelia','Martínez Sánchez','2016-04-25',4),
('SIM-2026-0053','Gabriel','Callisaya Apaza','2015-05-26',5),
('SIM-2026-0054','Diego','Cárdenas Molina','2014-06-27',6),
('SIM-2026-0055','Miguel','Cabrera Méndez','2019-07-01',1),
('SIM-2026-0056','Sofía','Rojas Fernández','2018-08-02',2),
('SIM-2026-0057','Andrea','Mendoza Aguilar','2017-09-03',3),
('SIM-2026-0058','Tatiana','Yujra Copa','2016-10-04',4),
('SIM-2026-0059','Joaquín','Miranda Escobar','2015-11-05',5),
('SIM-2026-0060','Adrián','Mamani Quispe','2014-12-06',6),
('SIM-2026-0061','Valentina','Rodríguez Martínez','2019-01-07',1),
('SIM-2026-0062','Fernanda','Huanca Callisaya','2018-02-08',2),
('SIM-2026-0063','Renata','Alarcón Cárdenas','2017-03-09',3),
('SIM-2026-0064','Santiago','Ortiz Cabrera','2016-04-10',4),
('SIM-2026-0065','Martín','Vargas Rojas','2015-05-11',5),
('SIM-2026-0066','Cristian','Chávez Mendoza','2014-06-12',6),
('SIM-2026-0067','Luciana','Laura Yujra','2019-07-13',1),
('SIM-2026-0068','Paola','Valdez Miranda','2018-08-14',2),
('SIM-2026-0069','Jimena','Arias Barrientos','2017-09-15',3),
('SIM-2026-0070','Nicolás','Pérez Rodríguez','2016-10-16',4),
('SIM-2026-0071','Daniel','Nina Huanca','2015-11-17',5),
('SIM-2026-0072','Luis','Limachi Alarcón','2014-12-18',6),
('SIM-2026-0073','Daniela','Suárez Ortiz','2019-01-19',1),
('SIM-2026-0074','Carla','Flores Vargas','2018-02-20',2),
('SIM-2026-0075','Rocío','Gutiérrez Chávez','2017-03-21',3),
('SIM-2026-0076','Thiago','Colque Laura','2016-04-22',4),
('SIM-2026-0077','Samuel','Tapia Valdez','2015-05-23',5),
('SIM-2026-0078','Álvaro','Soliz Arias','2014-06-24',6),
('SIM-2026-0079','Gabriela','García Pérez','2019-07-25',1),
('SIM-2026-0080','Micaela','Salazar Nina','2018-08-26',2),
('SIM-2026-0081','Mateo','Limachi Alarcón','2017-09-27',3),
('SIM-2026-0082','Lucas','Suárez Ortiz','2016-10-01',4),
('SIM-2026-0083','Andrés','Flores Vargas','2015-11-02',5),
('SIM-2026-0084','Camila','Gutiérrez Chávez','2014-12-03',6),
('SIM-2026-0085','Alejandra','Colque Laura','2019-01-04',1),
('SIM-2026-0086','Isabella','Tapia Valdez','2018-02-05',2),
('SIM-2026-0087','Sebastián','Soliz Arias','2017-03-06',3),
('SIM-2026-0088','Bruno','García Pérez','2016-04-07',4),
('SIM-2026-0089','Kevin','Salazar Nina','2015-05-08',5),
('SIM-2026-0090','Mariana','Villca Limachi','2014-06-09',6),
('SIM-2026-0091','Natalia','Rivero Suárez','2019-07-10',1),
('SIM-2026-0092','Noelia','Condori Mamani','2018-08-11',2),
('SIM-2026-0093','Gabriel','Romero Gutiérrez','2017-09-12',3),
('SIM-2026-0094','Diego','Ticona Colque','2016-10-13',4),
('SIM-2026-0095','Miguel','Arce Tapia','2015-11-14',5),
('SIM-2026-0096','Sofía','Velasco Soliz','2014-12-15',6),
('SIM-2026-0097','Andrea','López García','2019-01-16',1),
('SIM-2026-0098','Tatiana','Paredes Salazar','2018-02-17',2),
('SIM-2026-0099','Joaquín','Marca Villca','2017-03-18',3),
('SIM-2026-0100','Adrián','Soria Rivero','2016-04-19',4),
('SIM-2026-0101','Valentina','Choque Condori','2015-05-20',5),
('SIM-2026-0102','Fernanda','Sánchez Romero','2014-06-21',6),
('SIM-2026-0103','Renata','Apaza Ticona','2019-07-22',1),
('SIM-2026-0104','Santiago','Molina Arce','2018-08-23',2),
('SIM-2026-0105','Martín','Méndez Velasco','2017-09-24',3),
('SIM-2026-0106','Cristian','Fernández López','2016-10-25',4),
('SIM-2026-0107','Luciana','Aguilar Paredes','2015-11-26',5),
('SIM-2026-0108','Paola','Copa Marca','2014-12-27',6),
('SIM-2026-0109','Jimena','Escobar Soria','2019-01-01',1),
('SIM-2026-0110','Nicolás','Quispe Choque','2018-02-02',2),
('SIM-2026-0111','Daniel','Martínez Sánchez','2017-03-03',3),
('SIM-2026-0112','Luis','Callisaya Apaza','2016-04-04',4),
('SIM-2026-0113','Daniela','Cárdenas Molina','2015-05-05',5),
('SIM-2026-0114','Carla','Cabrera Méndez','2014-06-06',6),
('SIM-2026-0115','Rocío','Rojas Fernández','2019-07-07',1),
('SIM-2026-0116','Thiago','Mendoza Aguilar','2018-08-08',2),
('SIM-2026-0117','Samuel','Yujra Copa','2017-09-09',3),
('SIM-2026-0118','Álvaro','Miranda Escobar','2016-10-10',4),
('SIM-2026-0119','Gabriela','Mamani Quispe','2015-11-11',5),
('SIM-2026-0120','Micaela','Rodríguez Martínez','2014-12-12',6),
('SIM-2026-0121','Mateo','Callisaya Apaza','2019-01-13',1),
('SIM-2026-0122','Lucas','Cárdenas Molina','2018-02-14',2),
('SIM-2026-0123','Andrés','Cabrera Méndez','2017-03-15',3),
('SIM-2026-0124','Camila','Rojas Fernández','2016-04-16',4),
('SIM-2026-0125','Alejandra','Mendoza Aguilar','2015-05-17',5),
('SIM-2026-0126','Isabella','Yujra Copa','2014-06-18',6),
('SIM-2026-0127','Sebastián','Miranda Escobar','2019-07-19',1),
('SIM-2026-0128','Bruno','Mamani Quispe','2018-08-20',2),
('SIM-2026-0129','Kevin','Rodríguez Martínez','2017-09-21',3),
('SIM-2026-0130','Mariana','Huanca Callisaya','2016-10-22',4),
('SIM-2026-0131','Natalia','Alarcón Cárdenas','2015-11-23',5),
('SIM-2026-0132','Noelia','Ortiz Cabrera','2014-12-24',6),
('SIM-2026-0133','Gabriel','Vargas Rojas','2019-01-25',1),
('SIM-2026-0134','Diego','Chávez Mendoza','2018-02-26',2),
('SIM-2026-0135','Miguel','Laura Yujra','2017-03-27',3),
('SIM-2026-0136','Sofía','Valdez Miranda','2016-04-01',4),
('SIM-2026-0137','Andrea','Arias Barrientos','2015-05-02',5),
('SIM-2026-0138','Tatiana','Pérez Rodríguez','2014-06-03',6),
('SIM-2026-0139','Joaquín','Nina Huanca','2019-07-04',1),
('SIM-2026-0140','Adrián','Limachi Alarcón','2018-08-05',2),
('SIM-2026-0141','Valentina','Suárez Ortiz','2017-09-06',3),
('SIM-2026-0142','Fernanda','Flores Vargas','2016-10-07',4),
('SIM-2026-0143','Renata','Gutiérrez Chávez','2015-11-08',5),
('SIM-2026-0144','Santiago','Colque Laura','2014-12-09',6),
('SIM-2026-0145','Martín','Tapia Valdez','2019-01-10',1),
('SIM-2026-0146','Cristian','Soliz Arias','2018-02-11',2),
('SIM-2026-0147','Luciana','García Pérez','2017-03-12',3),
('SIM-2026-0148','Paola','Salazar Nina','2016-04-13',4),
('SIM-2026-0149','Jimena','Villca Limachi','2015-05-14',5),
('SIM-2026-0150','Nicolás','Rivero Suárez','2014-06-15',6);
 IF EXISTS(SELECT 1 FROM seed150_primaria s WHERE TIMESTAMPDIFF(YEAR,s.nacimiento,inicio) NOT BETWEEN s.grado+5 AND s.grado+6) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Las edades simuladas no concuerdan con el calendario y grado.';
 END IF;
 IF EXISTS(SELECT 1 FROM seed150_primaria s JOIN estudiantes e ON e.codigo_anonimo=s.codigo
  WHERE BINARY e.nombre<>BINARY s.nombre OR BINARY e.apellido<>BINARY s.apellido
  OR NOT(e.fecha_nacimiento <=> s.nacimiento) OR e.codigo_rude IS NOT NULL) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Hay codigos SIM existentes con datos distintos. No se sobrescribieron.';
 END IF;
 IF EXISTS(SELECT 1 FROM seed150_primaria s JOIN estudiantes e ON e.codigo_anonimo=s.codigo
  JOIN matriculas m ON m.estudiante_id=e.id JOIN cursos c ON c.id=m.curso_id
  WHERE c.gestion_id<>gestion_actual OR c.grado<>s.grado OR c.paralelo<>'A'
   OR m.origen<>'SIMULADO' OR m.fecha_ingreso<>inicio OR m.fecha_fin IS NOT NULL) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Un estudiante SIM tiene otra matricula. Revisa el historial antes de cargar.';
 END IF;
 INSERT INTO cursos(gestion_id,nivel,grado,paralelo)
 SELECT gestion_actual,'PRIMARIA',s.grado,'A' FROM (SELECT DISTINCT grado FROM seed150_primaria) s
 WHERE NOT EXISTS(SELECT 1 FROM cursos c WHERE c.gestion_id=gestion_actual AND c.nivel='PRIMARIA' AND c.grado=s.grado AND c.paralelo='A');
 SET nuevos_cursos=ROW_COUNT();
 INSERT INTO estudiantes(codigo_anonimo,codigo_rude,nombre,apellido,fecha_nacimiento)
 SELECT s.codigo,NULL,s.nombre,s.apellido,s.nacimiento FROM seed150_primaria s
 WHERE NOT EXISTS(SELECT 1 FROM estudiantes e WHERE e.codigo_anonimo=s.codigo);
 SET nuevos_estudiantes=ROW_COUNT();
 INSERT INTO matriculas(estudiante_id,curso_id,fecha_ingreso,fecha_fin,origen,registrado_por)
 SELECT e.id,c.id,inicio,NULL,'SIMULADO',responsable FROM seed150_primaria s
 JOIN estudiantes e ON e.codigo_anonimo=s.codigo
 JOIN cursos c ON c.gestion_id=gestion_actual AND c.nivel='PRIMARIA' AND c.grado=s.grado AND c.paralelo='A'
 WHERE NOT EXISTS(SELECT 1 FROM matriculas m WHERE m.estudiante_id=e.id AND m.curso_id=c.id AND m.fecha_ingreso=inicio);
 SET nuevas_matriculas=ROW_COUNT();
 IF (SELECT COUNT(*) FROM seed150_primaria s JOIN estudiantes e ON e.codigo_anonimo=s.codigo
  JOIN matriculas m ON m.estudiante_id=e.id JOIN cursos c ON c.id=m.curso_id
  WHERE c.gestion_id=gestion_actual AND c.grado=s.grado AND c.paralelo='A' AND m.origen='SIMULADO')<>150 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La verificacion final no obtuvo exactamente 150 matriculas.';
 END IF;
 SELECT c.grado,c.paralelo,COUNT(*) AS estudiantes_simulados,MIN(m.fecha_ingreso) AS ingreso,
  MIN(TIMESTAMPDIFF(YEAR,e.fecha_nacimiento,inicio)) AS edad_minima,
  MAX(TIMESTAMPDIFF(YEAR,e.fecha_nacimiento,inicio)) AS edad_maxima
 FROM seed150_primaria s JOIN estudiantes e ON e.codigo_anonimo=s.codigo
 JOIN matriculas m ON m.estudiante_id=e.id JOIN cursos c ON c.id=m.curso_id
 WHERE c.gestion_id=gestion_actual GROUP BY c.grado,c.paralelo ORDER BY c.grado;
 IF confirmar=1 THEN
  IF nuevos_cursos+nuevos_estudiantes+nuevas_matriculas>0 THEN
   INSERT INTO auditoria_cambios(usuario_id,tabla_afectada,registro_id,operacion,motivo,despues)
   VALUES(responsable,'gestiones',gestion_actual,'CORRECCION','Carga de 150 estudiantes ficticios y matriculas de primaria',
    JSON_OBJECT('lote','SIM-2026-0001 a SIM-2026-0150','cursos_creados',nuevos_cursos,'estudiantes_creados',nuevos_estudiantes,'matriculas_creadas',nuevas_matriculas));
  END IF;
  COMMIT;
 ELSE
  ROLLBACK;
 END IF;
 DROP TEMPORARY TABLE seed150_primaria;
 SELECT IF(confirmar=1,'GUARDADO','PRUEBA REVERTIDA') AS resultado,nuevos_cursos,nuevos_estudiantes,nuevas_matriculas;
END$$
DELIMITER ;
CALL seed_150_primaria_2026_corregido(@confirmar_carga);
DROP PROCEDURE seed_150_primaria_2026_corregido;
