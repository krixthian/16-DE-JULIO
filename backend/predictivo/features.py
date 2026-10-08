"""Transformaciones sin acceso a la base; fechas escolares locales sin zona horaria."""
from collections import defaultdict
from datetime import date, datetime, time
from statistics import mean

VERSION = 'primaria-marzo-v1'
CONTEXT_FIELDS = (
    'actividades_propuestas actividades_iniciadas actividades_completadas '
    'clases_observadas clases_con_participacion reuniones_convocadas reuniones_atendidas '
    'contactos_realizados contactos_respondidos acuerdos_evaluables acuerdos_cumplidos '
    'dificultad_lectura_observada dificultad_escritura_observada dificultad_calculo_observada '
    'necesita_apoyo_actividades dias_apoyo_estudio_semana espacio_estudio internet_estudio '
    'dispositivo_estudio adulto_referente_disponible repitencias_previas interrupciones_previas '
    'cambios_escuela_previos dificultades_integracion_reportadas acoso_reportado '
    'desmotivacion_reportada necesidad_apoyo_emocional_reportada'
).split()
DESCRIPTIONS = {
    'grado': 'Grado de primaria (1 a 6).',
    'jornadas_registradas': 'Jornadas lectivas configuradas durante la matrícula hasta el corte; no equivale al calendario oficial completo.',
    'asistencias_observadas': 'Jornadas con asistencia registrada y disponible al corte.',
    'cobertura_asistencia': 'Asistencias observadas / jornadas lectivas configuradas (0 a 1).',
    'proporcion_faltas': 'FALTAS / asistencias observadas, sin convertir vacíos en faltas.',
    'proporcion_faltas_injustificadas': 'FALTAS con justificada=false / asistencias observadas. NULL no se presume injustificada.',
    'proporcion_atrasos': 'ATRASOS / asistencias observadas.',
    'racha_faltas': 'Máxima racha de FALTAS sobre jornadas configuradas; un registro desconocido interrumpe la racha.',
    'notas_observadas': 'Evaluaciones CALIFICADAS con puntaje disponible.',
    'promedio_notas': 'Media simple de puntaje / máximo * 100; no es la nota oficial ponderada.',
    'proporcion_notas_bajas': 'Proporción de notas normalizadas menores a 51; umbral técnico de esta versión.',
    'cambio_notas': 'Media de cambios última-primera nota por materia, solo con fechas diferentes. No comparar materias diferentes.',
    'tareas_vencidas': 'Tareas con plazo anterior al corte, dentro de la matrícula, excluidas las exentas.',
    'cobertura_tareas': 'Tareas vencidas confirmadas como entregadas/no entregadas / tareas vencidas.',
    'proporcion_entregas': 'Entregadas / tareas vencidas confirmadas, excluye pendientes y sin registro.',
    'proporcion_no_entregadas': 'NO_ENTREGADA confirmada / tareas vencidas confirmadas.',
    'proporcion_entregas_tardias': 'Entregadas después del plazo / entregadas vencidas.',
    'tareas_por_revisar': 'Vencidas pendientes o sin registro; no representan incumplimiento confirmado.',
    'incidentes_registrados': 'Número de registros de convivencia disponibles; cero significa ninguno registrado, no ausencia probada de incidentes.',
    'contexto_disponible': '1 si hay una ficha de contexto disponible y del mismo origen, 0 si no.',
    'antiguedad_contexto_dias': 'Días desde la observación de la última ficha completa.',
}
DESCRIPTIONS.update({f'contexto_{k}': f'Última ficha completa: {k}. Vacío = no recabado; booleanos 0/1.' for k in CONTEXT_FIELDS})
FEATURE_NAMES = list(DESCRIPTIONS)


def day(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def instant(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, time.min)
    else:
        result = datetime.fromisoformat(str(value))
    if result.tzinfo is not None:
        raise ValueError('Usar fechas escolares locales sin zona horaria, igual que MySQL.')
    return result


def ratio(a, b):
    return a / b if b else None


def known(row, cutoff, timestamp='registrado_en'):
    return row.get(timestamp) is not None and instant(row[timestamp]) <= cutoff


def indexed(rows):
    result = {}
    for row in rows:
        key = row['id']
        if key in result:
            raise ValueError(f'Identificador duplicado: {key}')
        result[key] = row
    return result


def grouped(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[row[key]].append(row)
    return result


def validate_tables(tables):
    """Validar los vínculos utilizados también para fuentes JSON fuera de MySQL."""
    maps = {name: indexed(rows) for name, rows in tables.items() if name != 'auditoria_cambios'}
    references = {
        'cursos': [('gestion_id', 'gestiones')],
        'matriculas': [('curso_id', 'cursos')],
        'jornadas_clase': [('curso_id', 'cursos')],
        'evaluaciones': [('curso_id', 'cursos'), ('asignacion_id', 'asignaciones_docentes')],
        'calificaciones': [('matricula_id', 'matriculas'), ('evaluacion_id', 'evaluaciones')],
        'asistencias': [('matricula_id', 'matriculas'), ('jornada_id', 'jornadas_clase')],
        'tareas': [('curso_id', 'cursos')],
        'entregas_tareas': [('matricula_id', 'matriculas'), ('tarea_id', 'tareas')],
        'contextos_permanencia': [('matricula_id', 'matriculas')],
        'registros_convivencia': [('matricula_id', 'matriculas')],
        'situaciones_escolares': [('matricula_id', 'matriculas')],
    }
    for name, refs in references.items():
        for row in tables.get(name, []):
            for key, target in refs:
                parent = maps.get(target, {}).get(row[key])
                if parent is None:
                    raise ValueError(f'Relación inexistente: {name}.{key}.')
                if 'curso_id' in row and 'curso_id' in parent and row['curso_id'] != parent['curso_id']:
                    raise ValueError(f'Relación entre cursos diferentes: {name}.{key}.')
    states = {'asistencias': {'PRESENTE', 'FALTA', 'ATRASO', 'LICENCIA'},
        'calificaciones': {'CALIFICADA', 'PENDIENTE', 'NO_PRESENTADA', 'EXENTA'},
        'entregas_tareas': {'PENDIENTE', 'ENTREGADA', 'NO_ENTREGADA', 'EXENTA'}}
    unique_keys = {'asistencias': ('matricula_id', 'jornada_id'), 'calificaciones': ('matricula_id', 'evaluacion_id'),
        'entregas_tareas': ('matricula_id', 'tarea_id'), 'jornadas_clase': ('curso_id', 'fecha')}
    for name, allowed in states.items():
        if any(r['estado'] not in allowed for r in tables.get(name, [])):
            raise ValueError(f'Estado desconocido en {name}.')
    for name, columns in unique_keys.items():
        keys = [tuple(str(r[c]) for c in columns) for r in tables.get(name, [])]
        if len(keys) != len(set(keys)):
            raise ValueError(f'Registros duplicados en {name}.')
    for row in tables.get('situaciones_escolares', []):
        if day(row['observado_hasta']) < day(row['fecha_efectiva']):
            raise ValueError('Situación escolar observada antes de su fecha efectiva.')
    for row in tables.get('contextos_permanencia', []):
        for numerator, denominator in [('actividades_iniciadas', 'actividades_propuestas'),
            ('actividades_completadas', 'actividades_iniciadas'), ('clases_con_participacion', 'clases_observadas'),
            ('reuniones_atendidas', 'reuniones_convocadas'), ('contactos_respondidos', 'contactos_realizados'),
            ('acuerdos_cumplidos', 'acuerdos_evaluables')]:
            if row.get(numerator) is not None and row.get(denominator) is not None and not 0 <= row[numerator] <= row[denominator]:
                raise ValueError(f'Conteos de contexto incoherentes: {numerator}.')


def snapshot(tables, cutoff):
    """Revertir cambios auditados posteriores. No inventa versiones sin auditoría.

    El timestamp se comprueba además al usar cada hecho. Los registros importados
    sin auditoría requieren fechas históricas verificables y procedencia declarada.
    """
    result = {name: indexed(rows).copy() for name, rows in tables.items() if name != 'auditoria_cambios'}
    changes = sorted(tables.get('auditoria_cambios', []), key=lambda x: (instant(x['registrado_en']), x['id']), reverse=True)
    for change in changes:
        if instant(change['registrado_en']) <= cutoff:
            continue
        target = result.get(change['tabla_afectada'])
        if target is None:
            continue
        if change.get('antes') is None:
            target.pop(change['registro_id'], None)
        else:
            target[change['registro_id']] = change['antes']
    return {k: list(v.values()) for k, v in result.items()}


def build_features(tables, cutoff, origin, gestion_id=None):
    if origin not in ('REAL', 'SIMULADO'):
        raise ValueError('Debe declarar origen REAL o SIMULADO.')
    cutoff = day(cutoff)
    validate_tables(tables)
    # MySQL DATETIME del esquema conserva segundos, no fracciones de segundo.
    available = datetime.combine(cutoff, time(23, 59, 59))
    data = snapshot(tables, available)
    courses = indexed(data.get('cursos', []))
    years = indexed(data.get('gestiones', []))
    evaluations = indexed(data.get('evaluaciones', []))
    assignments = indexed(data.get('asignaciones_docentes', []))
    days = grouped(data.get('jornadas_clase', []), 'curso_id')
    attendance = grouped(data.get('asistencias', []), 'matricula_id')
    grades = grouped(data.get('calificaciones', []), 'matricula_id')
    tasks = grouped(data.get('tareas', []), 'curso_id')
    deliveries = grouped(data.get('entregas_tareas', []), 'matricula_id')
    contexts = grouped(data.get('contextos_permanencia', []), 'matricula_id')
    incidents = grouped(data.get('registros_convivencia', []), 'matricula_id')
    rows = []
    for enrollment in data.get('matriculas', []):
        if not known(enrollment, available, 'creado_en') or day(enrollment['fecha_ingreso']) > cutoff:
            continue
        course = courses[enrollment['curso_id']]
        year = years[course['gestion_id']]
        if (gestion_id is not None and year['id'] != gestion_id) or year['anio'] != cutoff.year or enrollment['origen'] != origin:
            continue
        if not year.get('fecha_inicio') or not year.get('fecha_fin'):
            raise ValueError('No hay fechas de gestión verificables en el estado reconstruido al corte. Revisar calendario y auditoría histórica.')
        if not day(year['fecha_inicio']) <= cutoff < day(year['fecha_fin']):
            raise ValueError('El corte debe estar dentro de la gestión y antes de su final.')
        start = max(day(enrollment['fecha_ingreso']), day(year['fecha_inicio']))
        active = enrollment.get('fecha_fin') is None or day(enrollment['fecha_fin']) >= cutoff
        end = min(cutoff, day(enrollment['fecha_fin'])) if enrollment.get('fecha_fin') else cutoff
        schooldays = sorted([j for j in days[course['id']] if j['es_lectiva'] and start <= day(j['fecha']) <= end], key=lambda j: day(j['fecha']))
        day_ids = {j['id'] for j in schooldays}
        observations = {a['jornada_id']: a for a in attendance[enrollment['id']] if a['jornada_id'] in day_ids and a['curso_id'] == course['id'] and known(a, available)}
        if len(observations) != sum(a['jornada_id'] in day_ids and a['curso_id'] == course['id'] and known(a, available) for a in attendance[enrollment['id']]):
            raise ValueError('Asistencia duplicada para una jornada/matrícula.')
        n = len(observations)
        values = {name: None for name in FEATURE_NAMES}
        values.update(grado=course['grado'], jornadas_registradas=len(schooldays), asistencias_observadas=n,
            cobertura_asistencia=ratio(n, len(schooldays)),
            proporcion_faltas=ratio(sum(a['estado'] == 'FALTA' for a in observations.values()), n),
            proporcion_faltas_injustificadas=ratio(sum(a['estado'] == 'FALTA' and a.get('justificada') == False for a in observations.values()), n),
            proporcion_atrasos=ratio(sum(a['estado'] == 'ATRASO' for a in observations.values()), n))
        streak = longest = 0
        for j in schooldays:
            streak = streak + 1 if observations.get(j['id'], {}).get('estado') == 'FALTA' else 0
            longest = max(longest, streak)
        values['racha_faltas'] = longest if n else None
        scores = []
        by_subject = defaultdict(list)
        for g in grades[enrollment['id']]:
            e = evaluations[g['evaluacion_id']]
            if e['curso_id'] != course['id'] or g['curso_id'] != course['id']:
                raise ValueError('Calificación de otro curso.')
            if not (start <= day(e['fecha_aplicacion']) <= end and known(e, available) and known(g, available)) or g['estado'] != 'CALIFICADA':
                continue
            if g['puntaje'] is None or not 0 <= float(g['puntaje']) <= float(e['puntaje_maximo']) or float(e['puntaje_maximo']) <= 0:
                raise ValueError('Puntaje fuera de escala.')
            score = float(g['puntaje']) / float(e['puntaje_maximo']) * 100
            scores.append(score)
            by_subject[assignments[e['asignacion_id']]['materia_id']].append((day(e['fecha_aplicacion']), score))
        changes = []
        for subject in by_subject.values():
            by_date = defaultdict(list)
            for d, score in subject:
                by_date[d].append(score)
            dates = sorted(by_date)
            if len(dates) >= 2:
                changes.append(mean(by_date[dates[-1]]) - mean(by_date[dates[0]]))
        values.update(notas_observadas=len(scores), promedio_notas=mean(scores) if scores else None,
            proporcion_notas_bajas=ratio(sum(s < 51 for s in scores), len(scores)), cambio_notas=mean(changes) if changes else None)
        delivered = {d['tarea_id']: d for d in deliveries[enrollment['id']] if known(d, available)}
        if len(delivered) != sum(known(d, available) for d in deliveries[enrollment['id']]):
            raise ValueError('Entrega duplicada para una tarea/matrícula.')
        due = confirmed = received = missing = late = review = 0
        for t in tasks[course['id']]:
            if not (start <= day(t['fecha_asignacion']) <= end and instant(t['fecha_limite']) <= available and known(t, available)):
                continue
            d = delivered.get(t['id'])
            if d and d['curso_id'] != course['id']:
                raise ValueError('Entrega de otro curso.')
            if d and d['estado'] == 'EXENTA':
                continue
            due += 1
            if d and d['estado'] == 'ENTREGADA' and d.get('fecha_entrega') and instant(d['fecha_entrega']) <= available:
                if instant(d['fecha_entrega']) < instant(t['fecha_asignacion']):
                    raise ValueError('Entrega anterior a la asignación.')
                confirmed += 1
                received += 1
                late += instant(d['fecha_entrega']) > instant(t['fecha_limite'])
            elif d and d['estado'] == 'NO_ENTREGADA':
                confirmed += 1
                missing += 1
            else:
                review += 1
        values.update(tareas_vencidas=due, cobertura_tareas=ratio(confirmed, due), proporcion_entregas=ratio(received, confirmed),
            proporcion_no_entregadas=ratio(missing, confirmed), proporcion_entregas_tardias=ratio(late, received), tareas_por_revisar=review,
            incidentes_registrados=sum(start <= day(i['fecha_hecho']) <= end and known(i, available) for i in incidents[enrollment['id']]))
        forms = [c for c in contexts[enrollment['id']] if c['origen'] == origin and start <= day(c['fecha_observacion']) <= end and known(c, available)]
        form = max(forms, key=lambda c: (day(c['fecha_observacion']), instant(c['registrado_en']), c['id'])) if forms else None
        values['contexto_disponible'] = int(form is not None)
        if form:
            values['antiguedad_contexto_dias'] = (cutoff - day(form['fecha_observacion'])).days
            values.update({f'contexto_{k}': float(form[k]) if form.get(k) is not None else None for k in CONTEXT_FIELDS})
        # Criterio técnico inicial de suficiencia, no umbral validado de riesgo.
        enough = n >= 5 and values['cobertura_asistencia'] >= .8 and len(scores) >= 1 and confirmed >= 1
        status = 'FUERA_SEGUIMIENTO' if not active else 'ELEGIBLE' if enough else 'DATOS_INSUFICIENTES'
        rows.append(dict(matricula_id=enrollment['id'], estudiante_id=enrollment['estudiante_id'], gestion_id=year['id'],
            gestion=year['anio'], origen=origin, fecha_corte=cutoff.isoformat(), disponible_hasta=available.isoformat(),
            horizonte=day(year['fecha_fin']).isoformat(), version_variables=VERSION, estado=status,
            motivo=None if status == 'ELEGIBLE' else 'Matrícula finalizada.' if not active else 'Se requieren 5 asistencias, cobertura >= 0.8, 1 nota y 1 tarea confirmada.',
            variables=values))
    return rows


def outcome(tables, row, observed_until):
    """Etiqueta separada de predictores, con seguimiento suficiente y sin traslados."""
    end, cutoff, observed = day(row['horizonte']), day(row['fecha_corte']), day(observed_until)
    if observed < end:
        return None, 'SEGUIMIENTO_INCOMPLETO'
    events = [s for s in tables.get('situaciones_escolares', []) if s['matricula_id'] == row['matricula_id']
        and s.get('fuente_verificacion') and day(s['fecha_efectiva']) <= end and day(s['observado_hasta']) <= observed
        and day(s['registrado_en']) <= observed]
    if any(s['tipo'] in ('TRASLADO', 'CAMBIO_CURSO', 'REINGRESO', 'OTRO') for s in events):
        return None, 'SITUACION_NO_COMPARABLE'
    if any(s['tipo'] == 'ABANDONO_CONFIRMADO' and day(s['fecha_efectiva']) <= cutoff for s in events):
        return None, 'ABANDONO_PREVIO_AL_CORTE'
    positives = [s for s in events if s['tipo'] == 'ABANDONO_CONFIRMADO' and cutoff < day(s['fecha_efectiva']) <= end]
    negatives = [s for s in events if s['tipo'] == 'CONTINUIDAD_CONFIRMADA' and day(s['observado_hasta']) >= end]
    if positives and negatives:
        return None, 'RESULTADOS_CONTRADICTORIOS'
    if positives:
        return 1, 'ABANDONO_CONFIRMADO'
    if negatives:
        return 0, 'CONTINUIDAD_CONFIRMADA'
    return None, 'SIN_RESULTADO_CONFIRMADO'
