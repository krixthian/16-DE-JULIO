-- Rediseño v2: alerta temprana escolar. Propuesta para MySQL 8.4.
-- Ejecutar sobre un esquema NUEVO y vacío, seleccionado previamente en Workbench.
-- No contiene DROP, datos simulados ni cambios sobre el esquema original.
-- Las reglas entre fechas, autorizaciones e inmutabilidad se detallan en la guía.
SET NAMES utf8mb4;

-- Acceso del personal. El usuario establece su contraseña al activar la cuenta. Un rol por usuario en esta primera versión.
CREATE TABLE usuarios (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NULL,
  rol ENUM('Admin','Director','Docente','Orientador') NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tokens de un solo uso. Se almacena el hash, nunca el enlace secreto ni una contraseña en texto plano.
CREATE TABLE tokens_acceso (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT UNSIGNED NOT NULL,
  token_hash BINARY(32) NOT NULL UNIQUE,
  proposito ENUM('ACTIVACION','RECUPERACION') NOT NULL,
  vence_en DATETIME NOT NULL,
  usado_en DATETIME NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
  CHECK (vence_en > creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Calendario anual definido por el colegio.
CREATE TABLE gestiones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  anio SMALLINT UNSIGNED NOT NULL UNIQUE,
  fecha_inicio DATE NULL,
  fecha_fin DATE NULL,
  CHECK (fecha_fin >= fecha_inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Trimestres con fechas reales. La aplicación controla que pertenezcan a la gestión y no se solapen.
CREATE TABLE periodos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  gestion_id BIGINT UNSIGNED NOT NULL,
  numero TINYINT UNSIGNED NOT NULL,
  fecha_inicio DATE NULL,
  fecha_fin DATE NULL,
  UNIQUE (gestion_id, numero),
  UNIQUE (id, gestion_id),
  FOREIGN KEY (gestion_id) REFERENCES gestiones(id),
  CHECK (numero BETWEEN 1 AND 3),
  CHECK (fecha_fin >= fecha_inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Sección de un grado en una gestión. Se crea otra fila para la siguiente gestión.
CREATE TABLE cursos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  gestion_id BIGINT UNSIGNED NOT NULL,
  nivel ENUM('PRIMARIA') NOT NULL DEFAULT 'PRIMARIA',
  grado TINYINT UNSIGNED NOT NULL,
  paralelo VARCHAR(5) NOT NULL,
  docente_asesor_id BIGINT UNSIGNED NULL,
  UNIQUE (gestion_id, nivel, grado, paralelo),
  UNIQUE (id, gestion_id),
  FOREIGN KEY (gestion_id) REFERENCES gestiones(id),
  FOREIGN KEY (docente_asesor_id) REFERENCES usuarios(id),
  CHECK (grado BETWEEN 1 AND 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Identidad estable. Curso e historial académico se registran en matrículas, no en esta tabla.
CREATE TABLE estudiantes (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  codigo_anonimo VARCHAR(40) NOT NULL UNIQUE,
  codigo_rude VARCHAR(50) NULL UNIQUE,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  fecha_nacimiento DATE NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Contactos familiares. Un apoderado puede estar relacionado con varios estudiantes.
CREATE TABLE apoderados (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre_completo VARCHAR(200) NOT NULL,
  telefono VARCHAR(30) NULL,
  email VARCHAR(254) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Relación familiar con vigencia para conservar contactos históricos.
CREATE TABLE estudiante_apoderado (
  estudiante_id BIGINT UNSIGNED NOT NULL,
  apoderado_id BIGINT UNSIGNED NOT NULL,
  parentesco VARCHAR(40) NOT NULL,
  contacto_principal BOOLEAN NOT NULL DEFAULT FALSE,
  vigente_desde DATE NOT NULL,
  vigente_hasta DATE NULL,
  PRIMARY KEY (estudiante_id, apoderado_id, vigente_desde),
  FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
  FOREIGN KEY (apoderado_id) REFERENCES apoderados(id),
  CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Permanencia en un curso. Un cambio de paralelo cierra el segmento y crea otro, sin sobrescribir el historial.
CREATE TABLE matriculas (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  estudiante_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  fecha_ingreso DATE NOT NULL,
  fecha_fin DATE NULL,
  origen ENUM('REAL','SIMULADO') NOT NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (estudiante_id, curso_id, fecha_ingreso),
  UNIQUE (id, curso_id),
  FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
  FOREIGN KEY (curso_id) REFERENCES cursos(id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id),
  CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_ingreso)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Evidencia del resultado escolar y alcance del seguimiento. No se utiliza como predictor de su propio resultado.
CREATE TABLE situaciones_escolares (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  matricula_id BIGINT UNSIGNED NOT NULL,
  tipo ENUM('CONTINUIDAD_CONFIRMADA','ABANDONO_CONFIRMADO','TRASLADO','CAMBIO_CURSO','REINGRESO','OTRO') NOT NULL,
  fecha_efectiva DATE NOT NULL,
  observado_hasta DATE NOT NULL,
  fuente_verificacion VARCHAR(255) NOT NULL,
  observacion TEXT NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id),
  INDEX (matricula_id, fecha_efectiva),
  CHECK (observado_hasta >= fecha_efectiva)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Catálogo de materias.
CREATE TABLE materias (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL UNIQUE,
  sigla VARCHAR(20) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Permite verificar qué docente registra en un curso y materia, incluyendo reemplazos con vigencia.
CREATE TABLE asignaciones_docentes (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  curso_id BIGINT UNSIGNED NOT NULL,
  materia_id BIGINT UNSIGNED NOT NULL,
  docente_id BIGINT UNSIGNED NOT NULL,
  vigente_desde DATE NOT NULL,
  vigente_hasta DATE NULL,
  UNIQUE (curso_id, materia_id, docente_id, vigente_desde),
  UNIQUE (id, curso_id),
  FOREIGN KEY (curso_id) REFERENCES cursos(id),
  FOREIGN KEY (materia_id) REFERENCES materias(id),
  FOREIGN KEY (docente_id) REFERENCES usuarios(id),
  CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Calendario diario por curso para distinguir días de clase, suspensiones y falta de registro. Una asistencia diaria, no por materia.
CREATE TABLE jornadas_clase (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  curso_id BIGINT UNSIGNED NOT NULL,
  fecha DATE NOT NULL,
  es_lectiva BOOLEAN NOT NULL DEFAULT TRUE,
  motivo_no_lectiva VARCHAR(200) NULL,
  UNIQUE (curso_id, fecha),
  UNIQUE (id, curso_id),
  FOREIGN KEY (curso_id) REFERENCES cursos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Estado diario. La falta de una fila significa sin registro; nunca se convierte automáticamente en falta o presencia.
CREATE TABLE asistencias (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  matricula_id BIGINT UNSIGNED NOT NULL,
  jornada_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  estado ENUM('PRESENTE','FALTA','ATRASO','LICENCIA') NOT NULL,
  justificada BOOLEAN NULL,
  observacion VARCHAR(500) NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (matricula_id, jornada_id),
  FOREIGN KEY (matricula_id, curso_id) REFERENCES matriculas(id, curso_id),
  FOREIGN KEY (jornada_id, curso_id) REFERENCES jornadas_clase(id, curso_id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Actividad parcial fechada. Dimensiones y ponderaciones quedan pendientes de la planilla oficial del colegio.
CREATE TABLE evaluaciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  asignacion_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  gestion_id BIGINT UNSIGNED NOT NULL,
  periodo_id BIGINT UNSIGNED NOT NULL,
  titulo VARCHAR(160) NOT NULL,
  tipo ENUM('PRUEBA','TRABAJO','PROYECTO','ORAL','OTRA') NOT NULL,
  dimension VARCHAR(60) NULL,
  fecha_aplicacion DATE NOT NULL,
  puntaje_maximo DECIMAL(8,2) NOT NULL,
  ponderacion DECIMAL(8,4) NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (id, curso_id),
  FOREIGN KEY (asignacion_id, curso_id) REFERENCES asignaciones_docentes(id, curso_id),
  FOREIGN KEY (curso_id, gestion_id) REFERENCES cursos(id, gestion_id),
  FOREIGN KEY (periodo_id, gestion_id) REFERENCES periodos(id, gestion_id),
  CHECK (puntaje_maximo > 0),
  CHECK (ponderacion IS NULL OR ponderacion > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Nota de un estudiante en una evaluación. Cero es una nota real; pendiente y no presentada mantienen puntaje NULL.
CREATE TABLE calificaciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  evaluacion_id BIGINT UNSIGNED NOT NULL,
  matricula_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  estado ENUM('CALIFICADA','PENDIENTE','NO_PRESENTADA','EXENTA') NOT NULL,
  puntaje DECIMAL(8,2) NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (evaluacion_id, matricula_id),
  FOREIGN KEY (evaluacion_id, curso_id) REFERENCES evaluaciones(id, curso_id),
  FOREIGN KEY (matricula_id, curso_id) REFERENCES matriculas(id, curso_id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id),
  CHECK ((estado = 'CALIFICADA' AND puntaje IS NOT NULL AND puntaje >= 0) OR (estado <> 'CALIFICADA' AND puntaje IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Actividad con plazo. Si se califica, se vincula con evaluaciones, sin duplicar la nota.
CREATE TABLE tareas (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  asignacion_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  evaluacion_id BIGINT UNSIGNED NULL,
  titulo VARCHAR(160) NOT NULL,
  fecha_asignacion DATETIME NOT NULL,
  fecha_limite DATETIME NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (id, curso_id),
  FOREIGN KEY (asignacion_id, curso_id) REFERENCES asignaciones_docentes(id, curso_id),
  FOREIGN KEY (evaluacion_id, curso_id) REFERENCES evaluaciones(id, curso_id),
  CHECK (fecha_limite >= fecha_asignacion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Una fila por estudiante destinatario de la tarea. La tardanza se calcula comparando entrega con vencimiento.
CREATE TABLE entregas_tareas (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tarea_id BIGINT UNSIGNED NOT NULL,
  matricula_id BIGINT UNSIGNED NOT NULL,
  curso_id BIGINT UNSIGNED NOT NULL,
  estado ENUM('PENDIENTE','ENTREGADA','NO_ENTREGADA','EXENTA') NOT NULL,
  fecha_entrega DATETIME NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tarea_id, matricula_id),
  FOREIGN KEY (tarea_id, curso_id) REFERENCES tareas(id, curso_id),
  FOREIGN KEY (matricula_id, curso_id) REFERENCES matriculas(id, curso_id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id),
  CHECK ((estado = 'ENTREGADA' AND fecha_entrega IS NOT NULL) OR (estado <> 'ENTREGADA' AND fecha_entrega IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Observaciones con criterios acordados. No contiene diagnósticos psicológicos ni una puntuación inventada de conducta.
CREATE TABLE registros_convivencia (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  matricula_id BIGINT UNSIGNED NOT NULL,
  fecha_hecho DATE NOT NULL,
  categoria VARCHAR(80) NOT NULL,
  descripcion_objetiva TEXT NOT NULL,
  accion_inmediata TEXT NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id),
  INDEX (matricula_id, fecha_hecho)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Versiones inmutables del modelo y sus umbrales. No se insertan métricas ni umbrales ficticios por defecto.
CREATE TABLE modelos_predictivos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  version VARCHAR(80) NOT NULL UNIQUE,
  algoritmo VARCHAR(40) NOT NULL DEFAULT 'XGBoost',
  objetivo TEXT NOT NULL,
  version_variables VARCHAR(80) NOT NULL,
  origen_datos ENUM('REAL','SIMULADO') NOT NULL,
  entrenado_en DATETIME NOT NULL,
  datos_hasta DATE NOT NULL,
  artefacto_uri VARCHAR(500) NOT NULL,
  artefacto_sha256 CHAR(64) NOT NULL,
  umbral_medio DECIMAL(7,6) NOT NULL,
  umbral_alto DECIMAL(7,6) NOT NULL,
  protocolo_validacion TEXT NOT NULL,
  metricas JSON NULL,
  CHECK (umbral_medio > 0 AND umbral_alto > umbral_medio AND umbral_alto < 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Fotografía inmutable de variables conocidas al corte. JSON tiene contrato versionado; no sustituye a los registros escolares.
CREATE TABLE cortes_predictivos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  matricula_id BIGINT UNSIGNED NOT NULL,
  fecha_corte DATE NOT NULL,
  disponible_hasta DATETIME NOT NULL,
  version_variables VARCHAR(80) NOT NULL,
  variables JSON NOT NULL,
  cobertura_asistencia DECIMAL(7,6) NULL,
  estado ENUM('ELEGIBLE','DATOS_INSUFICIENTES','FUERA_SEGUIMIENTO') NOT NULL,
  motivo VARCHAR(500) NULL,
  generado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id),
  INDEX (matricula_id, fecha_corte),
  CHECK (cobertura_asistencia IS NULL OR cobertura_asistencia BETWEEN 0 AND 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Resultado del modelo. Factores explicativos no se presentan como causas de abandono.
CREATE TABLE predicciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  corte_id BIGINT UNSIGNED NOT NULL,
  modelo_id BIGINT UNSIGNED NOT NULL,
  probabilidad DECIMAL(7,6) NOT NULL,
  nivel ENUM('BAJO','MEDIO','ALTO') NOT NULL,
  factores JSON NULL,
  generada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (corte_id, modelo_id),
  FOREIGN KEY (corte_id) REFERENCES cortes_predictivos(id),
  FOREIGN KEY (modelo_id) REFERENCES modelos_predictivos(id),
  CHECK (probabilidad BETWEEN 0 AND 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Caso de atención generado desde una predicción; una predicción de riesgo bajo no necesita abrir un caso.
CREATE TABLE alertas (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  prediccion_id BIGINT UNSIGNED NOT NULL UNIQUE,
  responsable_id BIGINT UNSIGNED NOT NULL,
  estado ENUM('NUEVA','EN_REVISION','EN_SEGUIMIENTO','CERRADA') NOT NULL DEFAULT 'NUEVA',
  creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cerrada_en DATETIME NULL,
  motivo_cierre TEXT NULL,
  FOREIGN KEY (prediccion_id) REFERENCES predicciones(id),
  FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
  CHECK ((estado = 'CERRADA' AND cerrada_en IS NOT NULL AND motivo_cierre IS NOT NULL) OR (estado <> 'CERRADA' AND cerrada_en IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Varias actuaciones por alerta. Conserva propuesta, aprobación humana, ejecución y resultado.
CREATE TABLE intervenciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  alerta_id BIGINT UNSIGNED NOT NULL,
  recomendacion TEXT NOT NULL,
  regla_version VARCHAR(80) NULL,
  responsable_id BIGINT UNSIGNED NOT NULL,
  fecha_planificada DATE NULL,
  estado ENUM('PROPUESTA','APROBADA','EN_CURSO','REALIZADA','CANCELADA') NOT NULL DEFAULT 'PROPUESTA',
  aprobada_por BIGINT UNSIGNED NULL,
  aprobada_en DATETIME NULL,
  accion_realizada TEXT NULL,
  resultado TEXT NULL,
  realizada_en DATETIME NULL,
  creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (alerta_id) REFERENCES alertas(id),
  FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
  FOREIGN KEY (aprobada_por) REFERENCES usuarios(id),
  CHECK (estado <> 'REALIZADA' OR (realizada_en IS NOT NULL AND accion_realizada IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Reuniones con la familia, con o sin alerta, y acuerdos de seguimiento.
CREATE TABLE citaciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  matricula_id BIGINT UNSIGNED NOT NULL,
  apoderado_id BIGINT UNSIGNED NOT NULL,
  intervencion_id BIGINT UNSIGNED NULL,
  fecha_programada DATETIME NOT NULL,
  motivo TEXT NOT NULL,
  estado ENUM('PROGRAMADA','ASISTIO','NO_ASISTIO','CANCELADA') NOT NULL DEFAULT 'PROGRAMADA',
  acuerdos TEXT NULL,
  registrado_por BIGINT UNSIGNED NOT NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id),
  FOREIGN KEY (apoderado_id) REFERENCES apoderados(id),
  FOREIGN KEY (intervencion_id) REFERENCES intervenciones(id),
  FOREIGN KEY (registrado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Seguimiento de correo o boleta. Enviado no significa leído; una boleta impresa no equivale a entregada.
CREATE TABLE notificaciones (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  citacion_id BIGINT UNSIGNED NOT NULL,
  canal ENUM('CORREO','BOLETA') NOT NULL,
  destino VARCHAR(254) NOT NULL,
  estado ENUM('PENDIENTE','ENVIADA','FALLIDA','ENTREGADA') NOT NULL DEFAULT 'PENDIENTE',
  intentos SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  referencia_externa VARCHAR(255) NULL,
  ultimo_error VARCHAR(500) NULL,
  creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  enviada_en DATETIME NULL,
  entregada_en DATETIME NULL,
  FOREIGN KEY (citacion_id) REFERENCES citaciones(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Historial de correcciones escrito por la aplicación en la misma transacción. Excluir contraseñas, tokens y contenido clínico.
CREATE TABLE auditoria_cambios (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT UNSIGNED NOT NULL,
  tabla_afectada VARCHAR(64) NOT NULL,
  registro_id BIGINT UNSIGNED NOT NULL,
  operacion ENUM('ALTA','CORRECCION','ANULACION') NOT NULL,
  motivo VARCHAR(500) NULL,
  antes JSON NULL,
  despues JSON NULL,
  registrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
  INDEX (tabla_afectada, registro_id, registrado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- Contexto adicional de permanencia escolar.
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
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE INDEX ix_contexto_corte ON contextos_permanencia (matricula_id, fecha_observacion, registrado_en);
