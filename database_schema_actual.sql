-- Estructura actual completa. Solo ejecutar en una base NUEVA y VACIA.

-- No incluye usuarios, contraseñas ni datos escolares.

CREATE DATABASE IF NOT EXISTS alerta_temprana_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE alerta_temprana_v2;


CREATE TABLE apoderados (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	nombre_completo VARCHAR(200) NOT NULL, 
	telefono VARCHAR(30), 
	email VARCHAR(254), 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE estudiantes (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	codigo_anonimo VARCHAR(40) NOT NULL, 
	codigo_rude VARCHAR(50), 
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	fecha_nacimiento DATE, 
	creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (codigo_anonimo), 
	UNIQUE (codigo_rude)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE gestiones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	anio SMALLINT UNSIGNED NOT NULL, 
	fecha_inicio DATE, 
	fecha_fin DATE, 
	PRIMARY KEY (id), 
	CHECK (fecha_fin >= fecha_inicio), 
	UNIQUE (anio)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE materias (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(120) NOT NULL, 
	sigla VARCHAR(20), 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE modelos_predictivos (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	version VARCHAR(80) NOT NULL, 
	algoritmo VARCHAR(40) NOT NULL DEFAULT 'XGBoost', 
	objetivo TEXT NOT NULL, 
	version_variables VARCHAR(80) NOT NULL, 
	origen_datos ENUM('REAL','SIMULADO') NOT NULL, 
	entrenado_en DATETIME NOT NULL, 
	datos_hasta DATE NOT NULL, 
	artefacto_uri VARCHAR(500) NOT NULL, 
	artefacto_sha256 CHAR(64) NOT NULL, 
	umbral_medio NUMERIC(7, 6) NOT NULL, 
	umbral_alto NUMERIC(7, 6) NOT NULL, 
	protocolo_validacion TEXT NOT NULL, 
	metricas JSON, 
	PRIMARY KEY (id), 
	CHECK (umbral_medio > 0 AND umbral_alto > umbral_medio AND umbral_alto < 1), 
	UNIQUE (version)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE usuarios (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255), 
	rol ENUM('Admin','Director','Docente','Orientador') NOT NULL, 
	activo BOOL NOT NULL DEFAULT TRUE, 
	creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE auditoria_cambios (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	usuario_id BIGINT UNSIGNED NOT NULL, 
	tabla_afectada VARCHAR(64) NOT NULL, 
	registro_id BIGINT UNSIGNED NOT NULL, 
	operacion ENUM('ALTA','CORRECCION','ANULACION') NOT NULL, 
	motivo VARCHAR(500), 
	antes JSON, 
	despues JSON, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;

CREATE INDEX ix_auditoria_cambios_1 ON auditoria_cambios (tabla_afectada, registro_id, registrado_en);


CREATE TABLE cursos (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	gestion_id BIGINT UNSIGNED NOT NULL, 
	nivel ENUM('PRIMARIA') NOT NULL DEFAULT 'PRIMARIA', 
	grado TINYINT UNSIGNED NOT NULL, 
	paralelo VARCHAR(5) NOT NULL, 
	docente_asesor_id BIGINT UNSIGNED, 
	PRIMARY KEY (id), 
	UNIQUE (gestion_id, nivel, grado, paralelo), 
	UNIQUE (id, gestion_id), 
	FOREIGN KEY(gestion_id) REFERENCES gestiones (id), 
	FOREIGN KEY(docente_asesor_id) REFERENCES usuarios (id), 
	CHECK (grado BETWEEN 1 AND 6)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE estudiante_apoderado (
	estudiante_id BIGINT UNSIGNED NOT NULL, 
	apoderado_id BIGINT UNSIGNED NOT NULL, 
	parentesco VARCHAR(40) NOT NULL, 
	contacto_principal BOOL NOT NULL DEFAULT FALSE, 
	vigente_desde DATE NOT NULL, 
	vigente_hasta DATE, 
	PRIMARY KEY (estudiante_id, apoderado_id, vigente_desde), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(apoderado_id) REFERENCES apoderados (id), 
	CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE periodos (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	gestion_id BIGINT UNSIGNED NOT NULL, 
	numero TINYINT UNSIGNED NOT NULL, 
	fecha_inicio DATE, 
	fecha_fin DATE, 
	PRIMARY KEY (id), 
	UNIQUE (gestion_id, numero), 
	UNIQUE (id, gestion_id), 
	FOREIGN KEY(gestion_id) REFERENCES gestiones (id), 
	CHECK (numero BETWEEN 1 AND 3), 
	CHECK (fecha_fin >= fecha_inicio)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE tokens_acceso (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	usuario_id BIGINT UNSIGNED NOT NULL, 
	token_hash BINARY(32) NOT NULL, 
	proposito ENUM('ACTIVACION','RECUPERACION') NOT NULL, 
	vence_en DATETIME NOT NULL, 
	usado_en DATETIME, 
	creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	CHECK (vence_en > creado_en), 
	UNIQUE (token_hash)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE asignaciones_docentes (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	materia_id BIGINT UNSIGNED NOT NULL, 
	docente_id BIGINT UNSIGNED NOT NULL, 
	vigente_desde DATE NOT NULL, 
	vigente_hasta DATE, 
	PRIMARY KEY (id), 
	UNIQUE (curso_id, materia_id, docente_id, vigente_desde), 
	UNIQUE (id, curso_id), 
	FOREIGN KEY(curso_id) REFERENCES cursos (id), 
	FOREIGN KEY(materia_id) REFERENCES materias (id), 
	FOREIGN KEY(docente_id) REFERENCES usuarios (id), 
	CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE jornadas_clase (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	fecha DATE NOT NULL, 
	es_lectiva BOOL NOT NULL DEFAULT TRUE, 
	motivo_no_lectiva VARCHAR(200), 
	PRIMARY KEY (id), 
	UNIQUE (curso_id, fecha), 
	UNIQUE (id, curso_id), 
	FOREIGN KEY(curso_id) REFERENCES cursos (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE matriculas (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	estudiante_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	fecha_ingreso DATE NOT NULL, 
	fecha_fin DATE, 
	origen ENUM('REAL','SIMULADO') NOT NULL, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (estudiante_id, curso_id, fecha_ingreso), 
	UNIQUE (id, curso_id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(curso_id) REFERENCES cursos (id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id), 
	CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_ingreso)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE asistencias (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	jornada_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	estado ENUM('PRESENTE','FALTA','ATRASO','LICENCIA') NOT NULL, 
	justificada BOOL, 
	observacion VARCHAR(500), 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (matricula_id, jornada_id), 
	FOREIGN KEY(matricula_id, curso_id) REFERENCES matriculas (id, curso_id), 
	FOREIGN KEY(jornada_id, curso_id) REFERENCES jornadas_clase (id, curso_id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE contextos_permanencia (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	fecha_observacion DATE NOT NULL, 
	ventana_desde DATE NOT NULL, 
	fuente ENUM('APODERADO','ESTUDIANTE','DOCENTE','ORIENTADOR','DOCUMENTO_ESCOLAR') NOT NULL, 
	instrumento_version VARCHAR(80) NOT NULL, 
	origen ENUM('REAL','SIMULADO') NOT NULL, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	actividades_propuestas SMALLINT UNSIGNED, 
	actividades_iniciadas SMALLINT UNSIGNED, 
	actividades_completadas SMALLINT UNSIGNED, 
	clases_observadas SMALLINT UNSIGNED, 
	clases_con_participacion SMALLINT UNSIGNED, 
	reuniones_convocadas SMALLINT UNSIGNED, 
	reuniones_atendidas SMALLINT UNSIGNED, 
	contactos_realizados SMALLINT UNSIGNED, 
	contactos_respondidos SMALLINT UNSIGNED, 
	acuerdos_evaluables SMALLINT UNSIGNED, 
	acuerdos_cumplidos SMALLINT UNSIGNED, 
	dificultad_lectura_observada BOOL, 
	dificultad_escritura_observada BOOL, 
	dificultad_calculo_observada BOOL, 
	necesita_apoyo_actividades BOOL, 
	dias_apoyo_estudio_semana TINYINT UNSIGNED, 
	espacio_estudio BOOL, 
	internet_estudio BOOL, 
	dispositivo_estudio BOOL, 
	adulto_referente_disponible BOOL, 
	repitencias_previas TINYINT UNSIGNED, 
	interrupciones_previas TINYINT UNSIGNED, 
	cambios_escuela_previos TINYINT UNSIGNED, 
	dificultades_integracion_reportadas BOOL, 
	acoso_reportado BOOL, 
	desmotivacion_reportada BOOL, 
	necesidad_apoyo_emocional_reportada BOOL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id), 
	CONSTRAINT ck_contexto_ventana CHECK (ventana_desde <= fecha_observacion), 
	CONSTRAINT ck_contexto_fecha CHECK (fecha_observacion <= DATE(registrado_en)), 
	CONSTRAINT ck_cp_actividades_iniciadas CHECK (actividades_iniciadas <= actividades_propuestas), 
	CONSTRAINT ck_cp_actividades_completadas CHECK (actividades_completadas <= actividades_iniciadas), 
	CONSTRAINT ck_cp_clases_con_participacion CHECK (clases_con_participacion <= clases_observadas), 
	CONSTRAINT ck_cp_reuniones_atendidas CHECK (reuniones_atendidas <= reuniones_convocadas), 
	CONSTRAINT ck_cp_contactos_respondidos CHECK (contactos_respondidos <= contactos_realizados), 
	CONSTRAINT ck_cp_acuerdos_cumplidos CHECK (acuerdos_cumplidos <= acuerdos_evaluables), 
	CONSTRAINT ck_contexto_apoyo CHECK (dias_apoyo_estudio_semana BETWEEN 0 AND 7), 
	CONSTRAINT ck_cp_bool_0 CHECK (dificultad_lectura_observada IN (0,1)), 
	CONSTRAINT ck_cp_bool_1 CHECK (dificultad_escritura_observada IN (0,1)), 
	CONSTRAINT ck_cp_bool_2 CHECK (dificultad_calculo_observada IN (0,1)), 
	CONSTRAINT ck_cp_bool_3 CHECK (necesita_apoyo_actividades IN (0,1)), 
	CONSTRAINT ck_cp_bool_4 CHECK (espacio_estudio IN (0,1)), 
	CONSTRAINT ck_cp_bool_5 CHECK (internet_estudio IN (0,1)), 
	CONSTRAINT ck_cp_bool_6 CHECK (dispositivo_estudio IN (0,1)), 
	CONSTRAINT ck_cp_bool_7 CHECK (adulto_referente_disponible IN (0,1)), 
	CONSTRAINT ck_cp_bool_8 CHECK (dificultades_integracion_reportadas IN (0,1)), 
	CONSTRAINT ck_cp_bool_9 CHECK (acoso_reportado IN (0,1)), 
	CONSTRAINT ck_cp_bool_10 CHECK (desmotivacion_reportada IN (0,1)), 
	CONSTRAINT ck_cp_bool_11 CHECK (necesidad_apoyo_emocional_reportada IN (0,1))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;

CREATE INDEX ix_contexto_corte ON contextos_permanencia (matricula_id, fecha_observacion, registrado_en);


CREATE TABLE cortes_predictivos (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	fecha_corte DATE NOT NULL, 
	disponible_hasta DATETIME NOT NULL, 
	version_variables VARCHAR(80) NOT NULL, 
	variables JSON NOT NULL, 
	cobertura_asistencia NUMERIC(7, 6), 
	estado ENUM('ELEGIBLE','DATOS_INSUFICIENTES','FUERA_SEGUIMIENTO') NOT NULL, 
	motivo VARCHAR(500), 
	generado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	CHECK (cobertura_asistencia IS NULL OR cobertura_asistencia BETWEEN 0 AND 1)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;

CREATE INDEX ix_cortes_predictivos_1 ON cortes_predictivos (matricula_id, fecha_corte);


CREATE TABLE evaluaciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	asignacion_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	gestion_id BIGINT UNSIGNED NOT NULL, 
	periodo_id BIGINT UNSIGNED NOT NULL, 
	titulo VARCHAR(160) NOT NULL, 
	tipo ENUM('PRUEBA','TRABAJO','PROYECTO','ORAL','OTRA') NOT NULL, 
	dimension VARCHAR(60), 
	fecha_aplicacion DATE NOT NULL, 
	puntaje_maximo NUMERIC(8, 2) NOT NULL, 
	ponderacion NUMERIC(8, 4), 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (id, curso_id), 
	FOREIGN KEY(asignacion_id, curso_id) REFERENCES asignaciones_docentes (id, curso_id), 
	FOREIGN KEY(curso_id, gestion_id) REFERENCES cursos (id, gestion_id), 
	FOREIGN KEY(periodo_id, gestion_id) REFERENCES periodos (id, gestion_id), 
	CHECK (puntaje_maximo > 0), 
	CHECK (ponderacion IS NULL OR ponderacion > 0)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE registros_convivencia (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	fecha_hecho DATE NOT NULL, 
	categoria VARCHAR(80) NOT NULL, 
	descripcion_objetiva TEXT NOT NULL, 
	accion_inmediata TEXT, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;

CREATE INDEX ix_registros_convivencia_2 ON registros_convivencia (matricula_id, fecha_hecho);


CREATE TABLE situaciones_escolares (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	tipo ENUM('CONTINUIDAD_CONFIRMADA','ABANDONO_CONFIRMADO','TRASLADO','CAMBIO_CURSO','REINGRESO','OTRO') NOT NULL, 
	fecha_efectiva DATE NOT NULL, 
	observado_hasta DATE NOT NULL, 
	fuente_verificacion VARCHAR(255) NOT NULL, 
	observacion TEXT, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id), 
	CHECK (observado_hasta >= fecha_efectiva)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;

CREATE INDEX ix_situaciones_escolares_2 ON situaciones_escolares (matricula_id, fecha_efectiva);


CREATE TABLE calificaciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	evaluacion_id BIGINT UNSIGNED NOT NULL, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	estado ENUM('CALIFICADA','PENDIENTE','NO_PRESENTADA','EXENTA') NOT NULL, 
	puntaje NUMERIC(8, 2), 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (evaluacion_id, matricula_id), 
	FOREIGN KEY(evaluacion_id, curso_id) REFERENCES evaluaciones (id, curso_id), 
	FOREIGN KEY(matricula_id, curso_id) REFERENCES matriculas (id, curso_id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id), 
	CHECK ((estado = 'CALIFICADA' AND puntaje IS NOT NULL AND puntaje >= 0) OR (estado <> 'CALIFICADA' AND puntaje IS NULL))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE predicciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	corte_id BIGINT UNSIGNED NOT NULL, 
	modelo_id BIGINT UNSIGNED NOT NULL, 
	probabilidad NUMERIC(7, 6) NOT NULL, 
	nivel ENUM('BAJO','MEDIO','ALTO') NOT NULL, 
	factores JSON, 
	generada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (corte_id, modelo_id), 
	FOREIGN KEY(corte_id) REFERENCES cortes_predictivos (id), 
	FOREIGN KEY(modelo_id) REFERENCES modelos_predictivos (id), 
	CHECK (probabilidad BETWEEN 0 AND 1)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE tareas (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	asignacion_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	evaluacion_id BIGINT UNSIGNED, 
	titulo VARCHAR(160) NOT NULL, 
	fecha_asignacion DATETIME NOT NULL, 
	fecha_limite DATETIME NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (id, curso_id), 
	FOREIGN KEY(asignacion_id, curso_id) REFERENCES asignaciones_docentes (id, curso_id), 
	FOREIGN KEY(evaluacion_id, curso_id) REFERENCES evaluaciones (id, curso_id), 
	CHECK (fecha_limite >= fecha_asignacion)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE alertas (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	prediccion_id BIGINT UNSIGNED NOT NULL, 
	responsable_id BIGINT UNSIGNED NOT NULL, 
	estado ENUM('NUEVA','EN_REVISION','EN_SEGUIMIENTO','CERRADA') NOT NULL DEFAULT 'NUEVA', 
	creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	cerrada_en DATETIME, 
	motivo_cierre TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(prediccion_id) REFERENCES predicciones (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	CHECK ((estado = 'CERRADA' AND cerrada_en IS NOT NULL AND motivo_cierre IS NOT NULL) OR (estado <> 'CERRADA' AND cerrada_en IS NULL)), 
	UNIQUE (prediccion_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE entregas_tareas (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	tarea_id BIGINT UNSIGNED NOT NULL, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	curso_id BIGINT UNSIGNED NOT NULL, 
	estado ENUM('PENDIENTE','ENTREGADA','NO_ENTREGADA','EXENTA') NOT NULL, 
	fecha_entrega DATETIME, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (tarea_id, matricula_id), 
	FOREIGN KEY(tarea_id, curso_id) REFERENCES tareas (id, curso_id), 
	FOREIGN KEY(matricula_id, curso_id) REFERENCES matriculas (id, curso_id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id), 
	CHECK ((estado = 'ENTREGADA' AND fecha_entrega IS NOT NULL) OR (estado <> 'ENTREGADA' AND fecha_entrega IS NULL))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE intervenciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	alerta_id BIGINT UNSIGNED NOT NULL, 
	recomendacion TEXT NOT NULL, 
	regla_version VARCHAR(80), 
	responsable_id BIGINT UNSIGNED NOT NULL, 
	fecha_planificada DATE, 
	estado ENUM('PROPUESTA','APROBADA','EN_CURSO','REALIZADA','CANCELADA') NOT NULL DEFAULT 'PROPUESTA', 
	aprobada_por BIGINT UNSIGNED, 
	aprobada_en DATETIME, 
	accion_realizada TEXT, 
	resultado TEXT, 
	realizada_en DATETIME, 
	creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alerta_id) REFERENCES alertas (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(aprobada_por) REFERENCES usuarios (id), 
	CHECK (estado <> 'REALIZADA' OR (realizada_en IS NOT NULL AND accion_realizada IS NOT NULL))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE citaciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	matricula_id BIGINT UNSIGNED NOT NULL, 
	apoderado_id BIGINT UNSIGNED NOT NULL, 
	intervencion_id BIGINT UNSIGNED, 
	fecha_programada DATETIME NOT NULL, 
	motivo TEXT NOT NULL, 
	estado ENUM('PROGRAMADA','ASISTIO','NO_ASISTIO','CANCELADA') NOT NULL DEFAULT 'PROGRAMADA', 
	acuerdos TEXT, 
	registrado_por BIGINT UNSIGNED NOT NULL, 
	registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matricula_id) REFERENCES matriculas (id), 
	FOREIGN KEY(apoderado_id) REFERENCES apoderados (id), 
	FOREIGN KEY(intervencion_id) REFERENCES intervenciones (id), 
	FOREIGN KEY(registrado_por) REFERENCES usuarios (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;


CREATE TABLE notificaciones (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	citacion_id BIGINT UNSIGNED NOT NULL, 
	canal ENUM('CORREO','BOLETA') NOT NULL, 
	destino VARCHAR(254) NOT NULL, 
	estado ENUM('PENDIENTE','ENVIADA','FALLIDA','ENTREGADA') NOT NULL DEFAULT 'PENDIENTE', 
	intentos SMALLINT UNSIGNED NOT NULL DEFAULT 0, 
	referencia_externa VARCHAR(255), 
	ultimo_error VARCHAR(500), 
	creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	enviada_en DATETIME, 
	entregada_en DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(citacion_id) REFERENCES citaciones (id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci

;