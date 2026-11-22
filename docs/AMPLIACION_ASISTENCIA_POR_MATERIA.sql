-- Ampliación del esquema: asistencia por materia (por hora), licencia parcial y citaciones con origen.
-- Respuesta a las observaciones del docente revisor (22/11/2026).
--
-- NO DESTRUCTIVO: solo crea 2 tablas nuevas y agrega 2 columnas a `citaciones` (hoy vacía).
-- No borra ni modifica registros existentes. La asistencia diaria (`asistencias`) sigue igual.
--
-- Resultado: 30 tablas, 54 claves foráneas, 43 CHECK (antes 28, 47 y 40).

USE alerta_temprana_v2;

-- 1) Cada clase dictada de una materia en un día (una "hora" del horario).
--    El porcentaje de asistencia por materia usa como denominador las clases dictadas de ESA materia,
--    así Religión (1 vez por semana) y Lenguaje (varios días) se comparan en la misma escala.
CREATE TABLE sesiones_clase (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
	jornada_id BIGINT UNSIGNED NOT NULL,
	curso_id BIGINT UNSIGNED NOT NULL,
	materia_id BIGINT UNSIGNED NOT NULL,
	periodo TINYINT UNSIGNED NOT NULL,
	dictada BOOL NOT NULL DEFAULT TRUE,
	registrado_por BIGINT UNSIGNED NOT NULL,
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	UNIQUE (jornada_id, periodo),
	UNIQUE (id, curso_id),
	FOREIGN KEY(jornada_id, curso_id) REFERENCES jornadas_clase (id, curso_id),
	FOREIGN KEY(materia_id) REFERENCES materias (id),
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id),
	CHECK (periodo BETWEEN 1 AND 8)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 2) Asistencia de cada estudiante en cada clase (hora) de una materia.
--    Licencia parcial = en un mismo día, PRESENTE/ATRASO en unas horas y LICENCIA en las siguientes.
CREATE TABLE asistencias_materia (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
	sesion_id BIGINT UNSIGNED NOT NULL,
	curso_id BIGINT UNSIGNED NOT NULL,
	matricula_id BIGINT UNSIGNED NOT NULL,
	estado ENUM('PRESENTE','FALTA','ATRASO','LICENCIA') NOT NULL,
	justificada BOOL,
	observacion VARCHAR(500),
	registrado_por BIGINT UNSIGNED NOT NULL,
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	UNIQUE (sesion_id, matricula_id),
	FOREIGN KEY(sesion_id, curso_id) REFERENCES sesiones_clase (id, curso_id),
	FOREIGN KEY(matricula_id, curso_id) REFERENCES matriculas (id, curso_id),
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id),
	CHECK (estado <> 'PRESENTE' OR justificada IS NULL)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 3) Citaciones con origen: de un docente por su materia, de dirección o de orientación.
--    Permite distinguir "5 citaciones de una materia y 2 de otra" de "7 en total".
ALTER TABLE citaciones
	ADD COLUMN origen ENUM('DOCENTE_MATERIA','DIRECCION','ORIENTACION') NOT NULL DEFAULT 'DIRECCION' AFTER motivo,
	ADD COLUMN materia_id BIGINT UNSIGNED NULL AFTER origen,
	ADD FOREIGN KEY (materia_id) REFERENCES materias (id),
	ADD CHECK ((origen = 'DOCENTE_MATERIA' AND materia_id IS NOT NULL) OR (origen <> 'DOCENTE_MATERIA' AND materia_id IS NULL));
