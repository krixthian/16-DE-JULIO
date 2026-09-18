"""Modelos del esquema v2. No conectan ni modifican la base al importarse."""
from sqlalchemy import Column, String, Enum, Boolean, Date, DateTime, Numeric, JSON, Text, UniqueConstraint, ForeignKeyConstraint, CheckConstraint, Index, text
from sqlalchemy.dialects.mysql import BIGINT, SMALLINT, TINYINT, BINARY, CHAR
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=True)
    rol = Column(Enum('Admin','Director','Docente','Orientador'), nullable=False)
    activo = Column(Boolean, nullable=False, server_default=text('TRUE'))
    creado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class TokenAcceso(Base):
    __tablename__ = "tokens_acceso"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    usuario_id = Column(BIGINT(unsigned=True), nullable=False)
    token_hash = Column(BINARY(32), nullable=False, unique=True)
    proposito = Column(Enum('ACTIVACION','RECUPERACION'), nullable=False)
    vence_en = Column(DateTime, nullable=False)
    usado_en = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        CheckConstraint('vence_en > creado_en'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Gestion(Base):
    __tablename__ = "gestiones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    anio = Column(SMALLINT(unsigned=True), nullable=False, unique=True)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    __table_args__ = (
        CheckConstraint('fecha_fin >= fecha_inicio'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Periodo(Base):
    __tablename__ = "periodos"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    gestion_id = Column(BIGINT(unsigned=True), nullable=False)
    numero = Column(TINYINT(unsigned=True), nullable=False)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    __table_args__ = (
        UniqueConstraint('gestion_id','numero'),
        UniqueConstraint('id','gestion_id'),
        ForeignKeyConstraint(['gestion_id'], ['gestiones.id']),
        CheckConstraint('numero BETWEEN 1 AND 3'),
        CheckConstraint('fecha_fin >= fecha_inicio'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Curso(Base):
    __tablename__ = "cursos"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    gestion_id = Column(BIGINT(unsigned=True), nullable=False)
    nivel = Column(Enum('PRIMARIA'), nullable=False, server_default=text("'PRIMARIA'"))
    grado = Column(TINYINT(unsigned=True), nullable=False)
    paralelo = Column(String(5), nullable=False)
    docente_asesor_id = Column(BIGINT(unsigned=True), nullable=True)
    __table_args__ = (
        UniqueConstraint('gestion_id','nivel','grado','paralelo'),
        UniqueConstraint('id','gestion_id'),
        ForeignKeyConstraint(['gestion_id'], ['gestiones.id']),
        ForeignKeyConstraint(['docente_asesor_id'], ['usuarios.id']),
        CheckConstraint('grado BETWEEN 1 AND 6'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Estudiante(Base):
    __tablename__ = "estudiantes"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    codigo_anonimo = Column(String(40), nullable=False, unique=True)
    codigo_rude = Column(String(50), nullable=True, unique=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    creado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Apoderado(Base):
    __tablename__ = "apoderados"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    nombre_completo = Column(String(200), nullable=False)
    telefono = Column(String(30), nullable=True)
    email = Column(String(254), nullable=True)
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class EstudianteApoderado(Base):
    __tablename__ = "estudiante_apoderado"
    estudiante_id = Column(BIGINT(unsigned=True), primary_key=True, nullable=False)
    apoderado_id = Column(BIGINT(unsigned=True), primary_key=True, nullable=False)
    parentesco = Column(String(40), nullable=False)
    contacto_principal = Column(Boolean, nullable=False, server_default=text('FALSE'))
    vigente_desde = Column(Date, primary_key=True, nullable=False)
    vigente_hasta = Column(Date, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(['estudiante_id'], ['estudiantes.id']),
        ForeignKeyConstraint(['apoderado_id'], ['apoderados.id']),
        CheckConstraint('vigente_hasta IS NULL OR vigente_hasta >= vigente_desde'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Matricula(Base):
    __tablename__ = "matriculas"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    estudiante_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha_ingreso = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=True)
    origen = Column(Enum('REAL','SIMULADO'), nullable=False)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    creado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('estudiante_id','curso_id','fecha_ingreso'),
        UniqueConstraint('id','curso_id'),
        ForeignKeyConstraint(['estudiante_id'], ['estudiantes.id']),
        ForeignKeyConstraint(['curso_id'], ['cursos.id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        CheckConstraint('fecha_fin IS NULL OR fecha_fin >= fecha_ingreso'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class SituacionEscolar(Base):
    __tablename__ = "situaciones_escolares"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    tipo = Column(Enum('CONTINUIDAD_CONFIRMADA','ABANDONO_CONFIRMADO','TRASLADO','CAMBIO_CURSO','REINGRESO','OTRO'), nullable=False)
    fecha_efectiva = Column(Date, nullable=False)
    observado_hasta = Column(Date, nullable=False)
    fuente_verificacion = Column(String(255), nullable=False)
    observacion = Column(Text, nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['matricula_id'], ['matriculas.id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        Index('ix_situaciones_escolares_2','matricula_id','fecha_efectiva'),
        CheckConstraint('observado_hasta >= fecha_efectiva'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Materia(Base):
    __tablename__ = "materias"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    nombre = Column(String(120), nullable=False, unique=True)
    sigla = Column(String(20), nullable=True)
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class AsignacionDocente(Base):
    __tablename__ = "asignaciones_docentes"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    materia_id = Column(BIGINT(unsigned=True), nullable=False)
    docente_id = Column(BIGINT(unsigned=True), nullable=False)
    vigente_desde = Column(Date, nullable=False)
    vigente_hasta = Column(Date, nullable=True)
    __table_args__ = (
        UniqueConstraint('curso_id','materia_id','docente_id','vigente_desde'),
        UniqueConstraint('id','curso_id'),
        ForeignKeyConstraint(['curso_id'], ['cursos.id']),
        ForeignKeyConstraint(['materia_id'], ['materias.id']),
        ForeignKeyConstraint(['docente_id'], ['usuarios.id']),
        CheckConstraint('vigente_hasta IS NULL OR vigente_hasta >= vigente_desde'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class JornadaClase(Base):
    __tablename__ = "jornadas_clase"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha = Column(Date, nullable=False)
    es_lectiva = Column(Boolean, nullable=False, server_default=text('TRUE'))
    motivo_no_lectiva = Column(String(200), nullable=True)
    __table_args__ = (
        UniqueConstraint('curso_id','fecha'),
        UniqueConstraint('id','curso_id'),
        ForeignKeyConstraint(['curso_id'], ['cursos.id']),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Asistencia(Base):
    __tablename__ = "asistencias"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    jornada_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    estado = Column(Enum('PRESENTE','FALTA','ATRASO','LICENCIA'), nullable=False)
    justificada = Column(Boolean, nullable=True)
    observacion = Column(String(500), nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('matricula_id','jornada_id'),
        ForeignKeyConstraint(['matricula_id', 'curso_id'], ['matriculas.id', 'matriculas.curso_id']),
        ForeignKeyConstraint(['jornada_id', 'curso_id'], ['jornadas_clase.id', 'jornadas_clase.curso_id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Evaluacion(Base):
    __tablename__ = "evaluaciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    asignacion_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    gestion_id = Column(BIGINT(unsigned=True), nullable=False)
    periodo_id = Column(BIGINT(unsigned=True), nullable=False)
    titulo = Column(String(160), nullable=False)
    tipo = Column(Enum('PRUEBA','TRABAJO','PROYECTO','ORAL','OTRA'), nullable=False)
    dimension = Column(String(60), nullable=True)
    fecha_aplicacion = Column(Date, nullable=False)
    puntaje_maximo = Column(Numeric(8,2), nullable=False)
    ponderacion = Column(Numeric(8,4), nullable=True)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('id','curso_id'),
        ForeignKeyConstraint(['asignacion_id', 'curso_id'], ['asignaciones_docentes.id', 'asignaciones_docentes.curso_id']),
        ForeignKeyConstraint(['curso_id', 'gestion_id'], ['cursos.id', 'cursos.gestion_id']),
        ForeignKeyConstraint(['periodo_id', 'gestion_id'], ['periodos.id', 'periodos.gestion_id']),
        CheckConstraint('puntaje_maximo > 0'),
        CheckConstraint('ponderacion IS NULL OR ponderacion > 0'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Calificacion(Base):
    __tablename__ = "calificaciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    evaluacion_id = Column(BIGINT(unsigned=True), nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    estado = Column(Enum('CALIFICADA','PENDIENTE','NO_PRESENTADA','EXENTA'), nullable=False)
    puntaje = Column(Numeric(8,2), nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('evaluacion_id','matricula_id'),
        ForeignKeyConstraint(['evaluacion_id', 'curso_id'], ['evaluaciones.id', 'evaluaciones.curso_id']),
        ForeignKeyConstraint(['matricula_id', 'curso_id'], ['matriculas.id', 'matriculas.curso_id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        CheckConstraint("(estado = 'CALIFICADA' AND puntaje IS NOT NULL AND puntaje >= 0) OR (estado <> 'CALIFICADA' AND puntaje IS NULL)"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Tarea(Base):
    __tablename__ = "tareas"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    asignacion_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    evaluacion_id = Column(BIGINT(unsigned=True), nullable=True)
    titulo = Column(String(160), nullable=False)
    fecha_asignacion = Column(DateTime, nullable=False)
    fecha_limite = Column(DateTime, nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('id','curso_id'),
        ForeignKeyConstraint(['asignacion_id', 'curso_id'], ['asignaciones_docentes.id', 'asignaciones_docentes.curso_id']),
        ForeignKeyConstraint(['evaluacion_id', 'curso_id'], ['evaluaciones.id', 'evaluaciones.curso_id']),
        CheckConstraint('fecha_limite >= fecha_asignacion'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class EntregaTarea(Base):
    __tablename__ = "entregas_tareas"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    tarea_id = Column(BIGINT(unsigned=True), nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    curso_id = Column(BIGINT(unsigned=True), nullable=False)
    estado = Column(Enum('PENDIENTE','ENTREGADA','NO_ENTREGADA','EXENTA'), nullable=False)
    fecha_entrega = Column(DateTime, nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('tarea_id','matricula_id'),
        ForeignKeyConstraint(['tarea_id', 'curso_id'], ['tareas.id', 'tareas.curso_id']),
        ForeignKeyConstraint(['matricula_id', 'curso_id'], ['matriculas.id', 'matriculas.curso_id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        CheckConstraint("(estado = 'ENTREGADA' AND fecha_entrega IS NOT NULL) OR (estado <> 'ENTREGADA' AND fecha_entrega IS NULL)"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class RegistroConvivencia(Base):
    __tablename__ = "registros_convivencia"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha_hecho = Column(Date, nullable=False)
    categoria = Column(String(80), nullable=False)
    descripcion_objetiva = Column(Text, nullable=False)
    accion_inmediata = Column(Text, nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['matricula_id'], ['matriculas.id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        Index('ix_registros_convivencia_2','matricula_id','fecha_hecho'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class ModeloPredictivo(Base):
    __tablename__ = "modelos_predictivos"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    version = Column(String(80), nullable=False, unique=True)
    algoritmo = Column(String(40), nullable=False, server_default=text("'XGBoost'"))
    objetivo = Column(Text, nullable=False)
    version_variables = Column(String(80), nullable=False)
    origen_datos = Column(Enum('REAL','SIMULADO'), nullable=False)
    entrenado_en = Column(DateTime, nullable=False)
    datos_hasta = Column(Date, nullable=False)
    artefacto_uri = Column(String(500), nullable=False)
    artefacto_sha256 = Column(CHAR(64), nullable=False)
    umbral_medio = Column(Numeric(7,6), nullable=False)
    umbral_alto = Column(Numeric(7,6), nullable=False)
    protocolo_validacion = Column(Text, nullable=False)
    metricas = Column(JSON, nullable=True)
    __table_args__ = (
        CheckConstraint('umbral_medio > 0 AND umbral_alto > umbral_medio AND umbral_alto < 1'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class CortePredictivo(Base):
    __tablename__ = "cortes_predictivos"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha_corte = Column(Date, nullable=False)
    disponible_hasta = Column(DateTime, nullable=False)
    version_variables = Column(String(80), nullable=False)
    variables = Column(JSON, nullable=False)
    cobertura_asistencia = Column(Numeric(7,6), nullable=True)
    estado = Column(Enum('ELEGIBLE','DATOS_INSUFICIENTES','FUERA_SEGUIMIENTO'), nullable=False)
    motivo = Column(String(500), nullable=True)
    generado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['matricula_id'], ['matriculas.id']),
        Index('ix_cortes_predictivos_1','matricula_id','fecha_corte'),
        CheckConstraint('cobertura_asistencia IS NULL OR cobertura_asistencia BETWEEN 0 AND 1'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Prediccion(Base):
    __tablename__ = "predicciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    corte_id = Column(BIGINT(unsigned=True), nullable=False)
    modelo_id = Column(BIGINT(unsigned=True), nullable=False)
    probabilidad = Column(Numeric(7,6), nullable=False)
    nivel = Column(Enum('BAJO','MEDIO','ALTO'), nullable=False)
    factores = Column(JSON, nullable=True)
    generada_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        UniqueConstraint('corte_id','modelo_id'),
        ForeignKeyConstraint(['corte_id'], ['cortes_predictivos.id']),
        ForeignKeyConstraint(['modelo_id'], ['modelos_predictivos.id']),
        CheckConstraint('probabilidad BETWEEN 0 AND 1'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Alerta(Base):
    __tablename__ = "alertas"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    prediccion_id = Column(BIGINT(unsigned=True), nullable=False, unique=True)
    responsable_id = Column(BIGINT(unsigned=True), nullable=False)
    estado = Column(Enum('NUEVA','EN_REVISION','EN_SEGUIMIENTO','CERRADA'), nullable=False, server_default=text("'NUEVA'"))
    creada_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    cerrada_en = Column(DateTime, nullable=True)
    motivo_cierre = Column(Text, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(['prediccion_id'], ['predicciones.id']),
        ForeignKeyConstraint(['responsable_id'], ['usuarios.id']),
        CheckConstraint("(estado = 'CERRADA' AND cerrada_en IS NOT NULL AND motivo_cierre IS NOT NULL) OR (estado <> 'CERRADA' AND cerrada_en IS NULL)"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Intervencion(Base):
    __tablename__ = "intervenciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    alerta_id = Column(BIGINT(unsigned=True), nullable=False)
    recomendacion = Column(Text, nullable=False)
    regla_version = Column(String(80), nullable=True)
    responsable_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha_planificada = Column(Date, nullable=True)
    estado = Column(Enum('PROPUESTA','APROBADA','EN_CURSO','REALIZADA','CANCELADA'), nullable=False, server_default=text("'PROPUESTA'"))
    aprobada_por = Column(BIGINT(unsigned=True), nullable=True)
    aprobada_en = Column(DateTime, nullable=True)
    accion_realizada = Column(Text, nullable=True)
    resultado = Column(Text, nullable=True)
    realizada_en = Column(DateTime, nullable=True)
    creada_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['alerta_id'], ['alertas.id']),
        ForeignKeyConstraint(['responsable_id'], ['usuarios.id']),
        ForeignKeyConstraint(['aprobada_por'], ['usuarios.id']),
        CheckConstraint("estado <> 'REALIZADA' OR (realizada_en IS NOT NULL AND accion_realizada IS NOT NULL)"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Citacion(Base):
    __tablename__ = "citaciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    apoderado_id = Column(BIGINT(unsigned=True), nullable=False)
    intervencion_id = Column(BIGINT(unsigned=True), nullable=True)
    fecha_programada = Column(DateTime, nullable=False)
    motivo = Column(Text, nullable=False)
    estado = Column(Enum('PROGRAMADA','ASISTIO','NO_ASISTIO','CANCELADA'), nullable=False, server_default=text("'PROGRAMADA'"))
    acuerdos = Column(Text, nullable=True)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['matricula_id'], ['matriculas.id']),
        ForeignKeyConstraint(['apoderado_id'], ['apoderados.id']),
        ForeignKeyConstraint(['intervencion_id'], ['intervenciones.id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class Notificacion(Base):
    __tablename__ = "notificaciones"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    citacion_id = Column(BIGINT(unsigned=True), nullable=False)
    canal = Column(Enum('CORREO','BOLETA'), nullable=False)
    destino = Column(String(254), nullable=False)
    estado = Column(Enum('PENDIENTE','ENVIADA','FALLIDA','ENTREGADA'), nullable=False, server_default=text("'PENDIENTE'"))
    intentos = Column(SMALLINT(unsigned=True), nullable=False, server_default=text('0'))
    referencia_externa = Column(String(255), nullable=True)
    ultimo_error = Column(String(500), nullable=True)
    creada_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    enviada_en = Column(DateTime, nullable=True)
    entregada_en = Column(DateTime, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(['citacion_id'], ['citaciones.id']),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

class AuditoriaCambio(Base):
    __tablename__ = "auditoria_cambios"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    usuario_id = Column(BIGINT(unsigned=True), nullable=False)
    tabla_afectada = Column(String(64), nullable=False)
    registro_id = Column(BIGINT(unsigned=True), nullable=False)
    operacion = Column(Enum('ALTA','CORRECCION','ANULACION'), nullable=False)
    motivo = Column(String(500), nullable=True)
    antes = Column(JSON, nullable=True)
    despues = Column(JSON, nullable=True)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    __table_args__ = (
        ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        Index('ix_auditoria_cambios_1','tabla_afectada','registro_id','registrado_en'),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )


class ContextoPermanencia(Base):
    """Observaciones fechadas; NULL significa no recabado, nunca ausencia de riesgo.

    Cada fila es una ficha completa de observación, no un parche de la anterior.
    No contiene diagnósticos psicológicos ni una puntuación de riesgo inventada.
    """
    __tablename__ = 'contextos_permanencia'
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    matricula_id = Column(BIGINT(unsigned=True), nullable=False)
    fecha_observacion = Column(Date, nullable=False)
    ventana_desde = Column(Date, nullable=False)
    fuente = Column(Enum('APODERADO','ESTUDIANTE','DOCENTE','ORIENTADOR','DOCUMENTO_ESCOLAR'), nullable=False)
    instrumento_version = Column(String(80), nullable=False)
    origen = Column(Enum('REAL','SIMULADO'), nullable=False)
    registrado_por = Column(BIGINT(unsigned=True), nullable=False)
    registrado_en = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    actividades_propuestas = Column(SMALLINT(unsigned=True), nullable=True)
    actividades_iniciadas = Column(SMALLINT(unsigned=True), nullable=True)
    actividades_completadas = Column(SMALLINT(unsigned=True), nullable=True)
    clases_observadas = Column(SMALLINT(unsigned=True), nullable=True)
    clases_con_participacion = Column(SMALLINT(unsigned=True), nullable=True)
    reuniones_convocadas = Column(SMALLINT(unsigned=True), nullable=True)
    reuniones_atendidas = Column(SMALLINT(unsigned=True), nullable=True)
    contactos_realizados = Column(SMALLINT(unsigned=True), nullable=True)
    contactos_respondidos = Column(SMALLINT(unsigned=True), nullable=True)
    acuerdos_evaluables = Column(SMALLINT(unsigned=True), nullable=True)
    acuerdos_cumplidos = Column(SMALLINT(unsigned=True), nullable=True)
    dificultad_lectura_observada = Column(Boolean, nullable=True)
    dificultad_escritura_observada = Column(Boolean, nullable=True)
    dificultad_calculo_observada = Column(Boolean, nullable=True)
    necesita_apoyo_actividades = Column(Boolean, nullable=True)
    dias_apoyo_estudio_semana = Column(TINYINT(unsigned=True), nullable=True)
    espacio_estudio = Column(Boolean, nullable=True)
    internet_estudio = Column(Boolean, nullable=True)
    dispositivo_estudio = Column(Boolean, nullable=True)
    adulto_referente_disponible = Column(Boolean, nullable=True)
    repitencias_previas = Column(TINYINT(unsigned=True), nullable=True)
    interrupciones_previas = Column(TINYINT(unsigned=True), nullable=True)
    cambios_escuela_previos = Column(TINYINT(unsigned=True), nullable=True)
    dificultades_integracion_reportadas = Column(Boolean, nullable=True)
    acoso_reportado = Column(Boolean, nullable=True)
    desmotivacion_reportada = Column(Boolean, nullable=True)
    necesidad_apoyo_emocional_reportada = Column(Boolean, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(['matricula_id'], ['matriculas.id']),
        ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
        Index('ix_contexto_corte', 'matricula_id', 'fecha_observacion', 'registrado_en'),
        CheckConstraint('ventana_desde <= fecha_observacion', name='ck_contexto_ventana'),
        CheckConstraint('fecha_observacion <= DATE(registrado_en)', name='ck_contexto_fecha'),
        CheckConstraint('actividades_iniciadas <= actividades_propuestas', name='ck_cp_actividades_iniciadas'),
        CheckConstraint('actividades_completadas <= actividades_iniciadas', name='ck_cp_actividades_completadas'),
        CheckConstraint('clases_con_participacion <= clases_observadas', name='ck_cp_clases_con_participacion'),
        CheckConstraint('reuniones_atendidas <= reuniones_convocadas', name='ck_cp_reuniones_atendidas'),
        CheckConstraint('contactos_respondidos <= contactos_realizados', name='ck_cp_contactos_respondidos'),
        CheckConstraint('acuerdos_cumplidos <= acuerdos_evaluables', name='ck_cp_acuerdos_cumplidos'),
        CheckConstraint('dias_apoyo_estudio_semana BETWEEN 0 AND 7', name='ck_contexto_apoyo'),
        *[CheckConstraint(f'{campo} IN (0,1)', name=f'ck_cp_bool_{i}') for i, campo in enumerate((
            'dificultad_lectura_observada', 'dificultad_escritura_observada',
            'dificultad_calculo_observada', 'necesita_apoyo_actividades', 'espacio_estudio', 'internet_estudio', 'dispositivo_estudio',
            'adulto_referente_disponible', 'dificultades_integracion_reportadas', 'acoso_reportado',
            'desmotivacion_reportada', 'necesidad_apoyo_emocional_reportada'))],
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_0900_ai_ci'},
    )

