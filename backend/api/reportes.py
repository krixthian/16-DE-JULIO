"""Reportes de alertas por gestión y curso (CSV y PDF). Estudiantes solo como "Estudiante 0042"."""
import csv
import io
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.alertas import seguimiento, consulta, responder, reglas_alerta, NOTA_PRIORIDAD
from database import get_db
from predictivo import recomendaciones as rp
import models as m

router = APIRouter(prefix='/reportes', tags=['Reportes'], dependencies=[Depends(seguimiento)])
APOYO = 'El modelo apoya, no sustituye, el criterio docente.'
ESTADOS = {'NUEVA': 'Nueva', 'EN_REVISION': 'En revisión', 'EN_SEGUIMIENTO': 'En seguimiento', 'CERRADA': 'Cerrada',
    'PROPUESTA': 'Propuesta', 'APROBADA': 'Aprobada', 'EN_CURSO': 'En curso', 'REALIZADA': 'Realizada', 'CANCELADA': 'Cancelada'}


def etiqueta(codigo):
    """Igual que frontend/src/utils/estudiante.js: EST-0042 → "Estudiante 0042"."""
    match = re.fullmatch(r'(EST|EXT)-(\w+)', codigo or '')
    if not match:
        return f'Estudiante {codigo}' if codigo else 'Estudiante'
    return f'Estudiante ext. {match[2]}' if match[1] == 'EXT' else f'Estudiante {match[2]}'


def datos(db, gestion, curso_id):
    query = consulta().where(m.Gestion.anio == gestion).order_by(m.Curso.grado, m.Curso.paralelo, m.Prediccion.probabilidad.desc())
    if curso_id is not None:
        query = query.where(m.Curso.id == curso_id)
    rows = db.execute(query).all()
    if not rows and db.scalar(select(m.Gestion.id).where(m.Gestion.anio == gestion)) is None:
        raise HTTPException(404, 'Gestión no encontrada.')
    curso = db.get(m.Curso, curso_id) if curso_id is not None else None
    if curso_id is not None and curso is None:
        raise HTTPException(404, 'Curso no encontrado.')
    alertas = responder(db, rows)
    ids = [a['id'] for a in alertas]
    pasos = {}
    for item in db.scalars(select(m.Intervencion).where(m.Intervencion.alerta_id.in_(ids)).order_by(m.Intervencion.id)) if ids else []:
        pasos.setdefault(item.alerta_id, []).append(item)
    for alerta, row in zip(alertas, rows):
        alerta['etiqueta'] = etiqueta(alerta['estudiante'])
        alerta['reglas'] = [r['codigo'] for r in reglas_alerta(db, row)]
        alerta['pasos'] = pasos.get(alerta['id'], [])
    alcance = f'Gestión {gestion}' + (f' · Curso {curso.grado}° {curso.paralelo}' if curso else ' · Todos los cursos')
    return alcance, alertas


def factores(a):
    valor = lambda v: f'{v:g}' if isinstance(v, (int, float)) else v
    return '; '.join(f"{f['variable']} = {valor(f['valor'])}" for f in a['factores']) or 'Sin factores positivos'


def paso_texto(p):
    texto = f"{ESTADOS[p.estado]}: {p.recomendacion}"
    if p.accion_realizada:
        texto += f" | Ejecutada {p.realizada_en:%Y-%m-%d}: {p.accion_realizada}"
    if p.resultado:
        texto += f' | Resultado: {p.resultado}'
    return texto


def nombre_archivo(gestion, curso_id, extension):
    return f'reporte_alertas_{gestion}' + (f'_curso{curso_id}' if curso_id else '') + f'.{extension}'


@router.get('/alertas.csv')
def reporte_csv(gestion: int, curso_id: int | None = None, db: Session = Depends(get_db)):
    alcance, alertas = datos(db, gestion, curso_id)
    out = io.StringIO()
    out.write(f'# Reporte de alertas de riesgo · {alcance} · generado {datetime.now():%Y-%m-%d %H:%M}\n')
    out.write(f'# {NOTA_PRIORIDAD}\n# {APOYO}\n')
    writer = csv.writer(out)
    writer.writerow(['estudiante', 'gestion', 'curso', 'nivel_prioridad', 'puesto_ranking', 'de', 'puntaje_no_calibrado', 'estado_alerta',
        'responsable_rol', 'factores', 'reglas_activas', 'intervenciones', 'modelo', 'fecha_corte'])
    for a in alertas:
        writer.writerow([a['etiqueta'], a['gestion'], a['curso'], a['nivel'], a['prioridad']['puesto'], a['prioridad']['de'],
            f"{a['probabilidad']:.3f}", ESTADOS[a['estado']], a['responsable']['rol'], factores(a), ' '.join(a['reglas']),
            ' || '.join(paso_texto(p) for p in a['pasos']), a['modelo'], a['fecha_corte']])
    # BOM para que Excel abra bien las tildes.
    return Response('﻿' + out.getvalue(), media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{nombre_archivo(gestion, curso_id, "csv")}"'})


@router.get('/alertas.pdf')
def reporte_pdf(gestion: int, curso_id: int | None = None, db: Session = Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    alcance, alertas = datos(db, gestion, curso_id)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=styles['BodyText'], fontSize=7.5, leading=9.5)
    note = ParagraphStyle('note', parent=styles['BodyText'], fontSize=8.5, leading=11, textColor=colors.HexColor('#334155'))
    p = lambda text, style=small: Paragraph(escape(str(text)), style)
    story = [Paragraph('Unidad Educativa 16 de Julio · Reporte de alertas de riesgo de abandono', styles['Title']),
        Paragraph(f'{escape(alcance)} · Generado el {datetime.now():%d/%m/%Y %H:%M} · {len(alertas)} alertas', styles['Heading3']),
        p(f'Nivel de confianza: {NOTA_PRIORIDAD}', note), p(APOYO, note),
        p(f'Recomendaciones: reglas {rp.VERSION} ({rp.VALIDACION}).', note), Spacer(1, .4 * cm)]
    header = ['Estudiante', 'Curso', 'Prioridad', 'Estado', 'Factores que elevan la prioridad', 'Reglas', 'Intervenciones']
    rows = [[p(a['etiqueta']), p(f"{a['curso']} · {a['gestion']}"),
        p(f"{a['nivel']} · puesto {a['prioridad']['puesto']} de {a['prioridad']['de']}"), p(ESTADOS[a['estado']]),
        p(factores(a)), p(' '.join(a['reglas'])), [p(paso_texto(x)) for x in a['pasos']] or p('Sin intervenciones')] for a in alertas]
    if rows:
        table = Table([[p(h) for h in header]] + rows, repeatRows=1,
            colWidths=[2.8 * cm, 2.4 * cm, 3.0 * cm, 2.3 * cm, 5.6 * cm, 1.8 * cm, 8.8 * cm])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#cbd5e1')), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])]))
        story.append(table)
    else:
        story.append(p('No hay alertas para este alcance.', note))
    buffer = io.BytesIO()

    def pie(canvas, doc):
        canvas.setFont('Helvetica', 7)
        canvas.drawString(1.5 * cm, 1 * cm, f'Estudiantes anonimizados. {APOYO}')
        canvas.drawRightString(landscape(A4)[0] - 1.5 * cm, 1 * cm, f'Página {doc.page}')

    SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.6 * cm,
        title=f'Reporte de alertas · {alcance}').build(story, onFirstPage=pie, onLaterPages=pie)
    return Response(buffer.getvalue(), media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{nombre_archivo(gestion, curso_id, "pdf")}"'})
