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
        activas = reglas_alerta(db, row)
        alerta['reglas'] = [r['codigo'] for r in activas]
        alerta['reglas_info'] = {r['codigo']: r['nombre'] for r in activas}
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


INSTITUCION = 'Unidad Educativa «16 de Julio»'
UBICACION = 'Nivel Primario · La Paz – Bolivia'
SISTEMA = 'Sistema de Alerta Temprana de Abandono Escolar'
NIVELES = {'ALTO': ('Alta', '#fde2e2', '#9b1c1c'), 'MEDIO': ('Media', '#fdf0d5', '#8a5a00'), 'BAJO': ('Baja', '#dcf5e8', '#166534')}


def resumen_semaforo(db, gestion, curso_id):
    """Conteo real de predicciones por nivel (modelo vigente) en el alcance del reporte, y la fecha de corte."""
    from api.dashboard import base
    filas = db.execute(base(gestion)).all()
    if curso_id is not None:
        filas = [f for f in filas if f[2].id == curso_id]
    niveles = {k: sum(1 for f in filas if f[0].nivel == k) for k in NIVELES}
    cortes = sorted({f[1].fecha_corte for f in filas})
    return len(filas), niveles, cortes


INSTITUCION = 'Unidad Educativa «16 de Julio»'
UBICACION = 'Nivel Primario · La Paz – Bolivia'
SISTEMA = 'Sistema de Alerta Temprana de Abandono Escolar'
NIVELES = {'ALTO': ('Alta', '#fde2e2', '#9b1c1c'), 'MEDIO': ('Media', '#fdf0d5', '#8a5a00'), 'BAJO': ('Baja', '#dcf5e8', '#166534')}


def factores_claros(a):
    """Factores con nombres comprensibles para docentes (p. ej. 'Promedio del 1.er trimestre: 66')."""
    from predictivo.explicacion import ETIQUETAS
    valor = lambda v: f'{v:g}' if isinstance(v, (int, float)) else v
    return '; '.join(f"{ETIQUETAS.get(f['variable'], f['variable'])}: {valor(f['valor'])}" for f in a['factores']) or 'Sin factores positivos'


def resumen_semaforo(db, gestion, curso_id):
    """Conteo real de predicciones por nivel (modelo vigente) en el alcance del reporte, y la fecha de corte."""
    from api.dashboard import base
    filas = db.execute(base(gestion)).all()
    if curso_id is not None:
        filas = [f for f in filas if f[2].id == curso_id]
    niveles = {k: sum(1 for f in filas if f[0].nivel == k) for k in NIVELES}
    cortes = sorted({f[1].fecha_corte for f in filas})
    return len(filas), niveles, cortes


@router.get('/alertas.pdf')
def reporte_pdf(gestion: int, curso_id: int | None = None, db: Session = Depends(get_db), user=Depends(seguimiento)):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from xml.sax.saxutils import escape

    alcance, alertas = datos(db, gestion, curso_id)
    evaluados, niveles, cortes = resumen_semaforo(db, gestion, curso_id)
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    curso = db.get(m.Curso, curso_id) if curso_id is not None else None
    emitido = datetime.now()
    codigo = f'REP-ALE-{gestion}' + (f'-{curso.grado}{curso.paralelo}' if curso else '') + f'-{emitido:%Y%m%d%H%M}'
    navy, gold, ink, gray = colors.HexColor('#1f3a5f'), colors.HexColor('#b8892d'), colors.HexColor('#1e293b'), colors.HexColor('#64748b')
    ancho, alto = landscape(A4)

    styles = getSampleStyleSheet()
    base_txt = ParagraphStyle('base', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=ink)
    small = ParagraphStyle('small', parent=base_txt, fontSize=7.5, leading=9.5)
    head = ParagraphStyle('head', parent=small, fontName='Helvetica-Bold', textColor=colors.white)
    titulo = ParagraphStyle('titulo', parent=base_txt, fontName='Helvetica-Bold', fontSize=15, leading=19, alignment=TA_CENTER, textColor=navy)
    subtitulo = ParagraphStyle('subtitulo', parent=base_txt, fontSize=10, leading=13, alignment=TA_CENTER, textColor=gray)
    seccion = ParagraphStyle('seccion', parent=base_txt, fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=navy,
        spaceBefore=8, spaceAfter=4)
    p = lambda text, style=small: Paragraph(escape(str(text)), style)
    b = lambda text, style=small: Paragraph(f'<b>{escape(str(text))}</b>', style)
    pct = lambda n: f'{100 * n / evaluados:.1f} %'.replace('.', ',') if evaluados else '—'

    umbrales = (f'MEDIO ≥ {float(modelo.umbral_medio):g} · ALTO ≥ {float(modelo.umbral_alto):g} (propuesta)'.replace('.', ',')
        if modelo else '—')
    story = [Paragraph('REPORTE DE ALERTAS DE RIESGO DE ABANDONO ESCOLAR', titulo), Paragraph(escape(alcance), subtitulo),
        Spacer(1, .35 * cm)]

    story.append(Paragraph('1. Datos del reporte', seccion))
    ficha = [[b('Gestión'), p(gestion), b('Curso'), p(f'{curso.grado}° {curso.paralelo}' if curso else 'Todos los cursos')],
        [b('Fecha de corte'), p(', '.join(f'{c:%d/%m/%Y}' for c in cortes) or '—'), b('Fecha de emisión'), p(f'{emitido:%d/%m/%Y %H:%M}')],
        [b('Modelo'), p(f'XGBoost · {modelo.version}' if modelo else '—'), b('Umbrales de prioridad'), p(umbrales)],
        [b('Emitido por'), p(f'{user.nombre} {user.apellido} ({user.rol})'), b('Código del documento'), p(codigo)]]
    t = Table(ficha, colWidths=[3.4 * cm, 9.4 * cm, 3.8 * cm, 9.4 * cm])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eef2f7')), ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#eef2f7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story.append(t)

    story.append(Paragraph('2. Resumen del semáforo de prioridad', seccion))
    con_intervencion = sum(1 for a in alertas if a['pasos'])
    sem = [[p(h, head) for h in ('Estudiantes evaluados', 'Rojo · prioridad alta', 'Amarillo · prioridad media',
            'Verde · prioridad baja (sin alerta)', 'Alertas generadas', 'Alertas con intervención')],
        [b(evaluados), b(f"{niveles['ALTO']}  ({pct(niveles['ALTO'])})"), b(f"{niveles['MEDIO']}  ({pct(niveles['MEDIO'])})"),
            b(f"{niveles['BAJO']}  ({pct(niveles['BAJO'])})"), b(len(alertas)), b(f'{con_intervencion} de {len(alertas)}')]]
    t = Table(sem, colWidths=[4.2 * cm, 4.4 * cm, 4.4 * cm, 5.4 * cm, 3.6 * cm, 4.0 * cm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), navy), ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor(NIVELES['ALTO'][1])),
        ('BACKGROUND', (2, 1), (2, 1), colors.HexColor(NIVELES['MEDIO'][1])),
        ('BACKGROUND', (3, 1), (3, 1), colors.HexColor(NIVELES['BAJO'][1])),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story.append(t)

    story.append(Paragraph('3. Detalle de alertas', seccion))
    header = ['N.º', 'Estudiante', 'Curso', 'Prioridad', 'Estado', 'Factores que elevan la prioridad', 'Reglas', 'Intervenciones registradas']
    filas, estilos = [], []
    for i, a in enumerate(alertas, start=1):
        nombre, fondo, texto = NIVELES.get(a['nivel'], (a['nivel'], '#ffffff', '#1e293b'))
        filas.append([p(i), b(a['etiqueta']), p(f"{a['curso']} · {a['gestion']}"),
            Paragraph(f"<b><font color='{texto}'>{escape(nombre)}</font></b><br/>Puesto {a['prioridad']['puesto']} de {a['prioridad']['de']}",
                small),
            p(ESTADOS[a['estado']]), p(factores_claros(a)), p(' '.join(a['reglas']) or '—'),
            [p(paso_texto(x)) for x in a['pasos']] or p('Sin intervenciones')])
        estilos.append(('BACKGROUND', (3, i), (3, i), colors.HexColor(fondo)))
    if filas:
        t = Table([[p(h, head) for h in header]] + filas, repeatRows=1,
            colWidths=[0.9 * cm, 2.9 * cm, 2.3 * cm, 2.5 * cm, 2.1 * cm, 6.3 * cm, 1.8 * cm, 7.2 * cm])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), navy), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]), *estilos]))
        story.append(t)
    else:
        story.append(p('No hay alertas para este alcance.', base_txt))

    story.append(Paragraph('4. Consideraciones', seccion))
    reglas = {}
    for a in alertas:
        reglas.update(a.get('reglas_info') or {})
    notas = [NOTA_PRIORIDAD, APOYO]
    if reglas:
        notas.append('Reglas de recomendación: ' + '; '.join(f'{k} = {v}' for k, v in sorted(reglas.items()))
            + f'. Versión {rp.VERSION} ({rp.VALIDACION}).')
    notas.append('Los estudiantes se identifican con un código anónimo; el documento no contiene nombres ni datos personales.')
    for nota in notas:
        story.append(Paragraph(f'•&nbsp;&nbsp;{escape(nota)}', base_txt))

    centro = ParagraphStyle('centro', parent=base_txt, alignment=TA_CENTER)
    firmas = Table([[p('_' * 42, centro), p(''), p('_' * 42, centro)],
        [b('Elaborado por', centro), p(''), b('Revisado por', centro)],
        [p(f'{user.nombre} {user.apellido} · {user.rol}', centro), p(''), p('Director(a) de la Unidad Educativa', centro)]],
        colWidths=[8 * cm, 6 * cm, 8 * cm])
    firmas.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    story.append(KeepTogether([Spacer(1, 1.1 * cm), firmas]))

    def encabezado(c, pagina, total):
        c.saveState()
        top = alto - 1.2 * cm
        c.setFillColor(navy)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(1.5 * cm, top, INSTITUCION.upper())
        c.setFillColor(gray)
        c.setFont('Helvetica', 8.5)
        c.drawString(1.5 * cm, top - .45 * cm, UBICACION)
        c.setFillColor(navy)
        c.setFont('Helvetica-Bold', 9)
        c.drawRightString(ancho - 1.5 * cm, top, SISTEMA)
        c.setFillColor(gray)
        c.setFont('Helvetica', 8)
        c.drawRightString(ancho - 1.5 * cm, top - .45 * cm, f'Documento {codigo} · Emitido el {emitido:%d/%m/%Y}')
        c.setStrokeColor(navy)
        c.setLineWidth(1.6)
        c.line(1.5 * cm, top - .75 * cm, ancho - 1.5 * cm, top - .75 * cm)
        c.setStrokeColor(gold)
        c.setLineWidth(.8)
        c.line(1.5 * cm, top - .88 * cm, ancho - 1.5 * cm, top - .88 * cm)
        c.setStrokeColor(colors.HexColor('#cbd5e1'))
        c.setLineWidth(.4)
        c.line(1.5 * cm, 1.35 * cm, ancho - 1.5 * cm, 1.35 * cm)
        c.setFillColor(gray)
        c.setFont('Helvetica', 7)
        c.drawString(1.5 * cm, .95 * cm, f'{SISTEMA} · Documento de uso interno y confidencial · Estudiantes anonimizados. {APOYO}')
        c.drawRightString(ancho - 1.5 * cm, .95 * cm, f'Página {pagina} de {total}')
        c.restoreState()

    class Paginado(pdfcanvas.Canvas):
        """Dibuja encabezado y pie al final, cuando ya se conoce el total de páginas."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for numero, estado in enumerate(self._paginas, start=1):
                self.__dict__.update(estado)
                encabezado(self, numero, total)
                super().showPage()
            super().save()

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=2.6 * cm, bottomMargin=1.8 * cm,
        title=f'Reporte de alertas · {alcance}', author=INSTITUCION, subject=SISTEMA).build(story, canvasmaker=Paginado)
    return Response(buffer.getvalue(), media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{nombre_archivo(gestion, curso_id, "pdf")}"'})


@router.get('/alertas.xlsx')
def reporte_xlsx(gestion: int, curso_id: int | None = None, db: Session = Depends(get_db), user=Depends(seguimiento)):
    """Excel con el mismo formato institucional del PDF (hoja Reporte) y una tabla limpia para análisis (hoja Datos)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table as TablaExcel, TableStyleInfo

    alcance, alertas = datos(db, gestion, curso_id)
    evaluados, niveles, cortes = resumen_semaforo(db, gestion, curso_id)
    modelo = db.scalar(select(m.ModeloPredictivo).order_by(m.ModeloPredictivo.id.desc()))
    curso = db.get(m.Curso, curso_id) if curso_id is not None else None
    emitido = datetime.now()
    codigo = f'REP-ALE-{gestion}' + (f'-{curso.grado}{curso.paralelo}' if curso else '') + f'-{emitido:%Y%m%d%H%M}'
    NAVY, GOLD, GRAY, INK = '1F3A5F', 'B8892D', '64748B', '1E293B'
    fill = lambda c: PatternFill('solid', start_color=c, end_color=c)
    fino = Side(style='thin', color='CBD5E1')
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    envolver = Alignment(wrap_text=True, vertical='top')
    centro = Alignment(horizontal='center', vertical='center', wrap_text=True)
    pct = lambda n: (n / evaluados) if evaluados else 0
    columnas = ['N.º', 'Estudiante', 'Curso', 'Gestión', 'Prioridad', 'Puesto', 'Estado', 'Factores que elevan la prioridad', 'Reglas',
        'Intervenciones registradas']
    ultima = get_column_letter(len(columnas))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Reporte'
    ws.sheet_view.showGridLines = False
    for i, ancho in enumerate((8, 20, 11, 10, 11, 12, 15, 46, 12, 46), start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    def fila_unida(r, texto, font, align=None, alto=None):
        ws.merge_cells(f'A{r}:{ultima}{r}')
        c = ws[f'A{r}']
        c.value, c.font = texto, font
        c.alignment = align or Alignment(vertical='center')
        if alto:
            ws.row_dimensions[r].height = alto

    fila_unida(1, INSTITUCION.upper(), Font(bold=True, size=14, color=NAVY), alto=22)
    fila_unida(2, f'{UBICACION} · {SISTEMA}', Font(size=9, color=GRAY))
    fila_unida(3, f'Documento {codigo} · Emitido el {emitido:%d/%m/%Y %H:%M}', Font(size=9, color=GRAY))
    for col in range(1, len(columnas) + 1):
        ws.cell(row=3, column=col).border = Border(bottom=Side(style='thick', color=NAVY))
        ws.cell(row=4, column=col).border = Border(top=Side(style='thin', color=GOLD))
    fila_unida(5, 'REPORTE DE ALERTAS DE RIESGO DE ABANDONO ESCOLAR', Font(bold=True, size=15, color=NAVY), centro, 26)
    fila_unida(6, alcance, Font(size=10, color=GRAY), centro)

    r = 8
    fila_unida(r, '1. Datos del reporte', Font(bold=True, size=11, color=NAVY))
    umbrales = (f'MEDIO ≥ {float(modelo.umbral_medio):g} · ALTO ≥ {float(modelo.umbral_alto):g} (propuesta)'.replace('.', ',')
        if modelo else '—')
    ficha = [('Gestión', gestion, 'Curso', f'{curso.grado}° {curso.paralelo}' if curso else 'Todos los cursos'),
        ('Fecha de corte', ', '.join(f'{c:%d/%m/%Y}' for c in cortes) or '—', 'Fecha de emisión', f'{emitido:%d/%m/%Y %H:%M}'),
        ('Modelo', f'XGBoost · {modelo.version}' if modelo else '—', 'Umbrales de prioridad', umbrales),
        ('Emitido por', f'{user.nombre} {user.apellido} ({user.rol})', 'Código del documento', codigo)]
    for k1, v1, k2, v2 in ficha:
        r += 1
        ws.merge_cells(f'A{r}:B{r}')
        ws.merge_cells(f'C{r}:G{r}')
        ws.merge_cells(f'I{r}:J{r}')
        for ref, valor, negrita in ((f'A{r}', k1, True), (f'C{r}', v1, False), (f'H{r}', k2, True), (f'I{r}', v2, False)):
            c = ws[ref]
            c.value, c.font = valor, Font(bold=negrita, size=9, color=INK)
            c.alignment = Alignment(horizontal='left', vertical='center')
            if negrita:
                c.fill = fill('EEF2F7')
        for col in range(1, len(columnas) + 1):
            ws.cell(row=r, column=col).border = borde

    r += 2
    fila_unida(r, '2. Resumen del semáforo de prioridad', Font(bold=True, size=11, color=NAVY))
    con_intervencion = sum(1 for a in alertas if a['pasos'])
    bloques = [('A', 'B', 'Estudiantes evaluados', evaluados, None), ('C', 'D', 'Rojo · prioridad alta', niveles['ALTO'], 'ALTO'),
        ('E', 'F', 'Amarillo · prioridad media', niveles['MEDIO'], 'MEDIO'), ('G', 'H', 'Verde · prioridad baja (sin alerta)', niveles['BAJO'], 'BAJO'),
        ('I', 'I', 'Alertas generadas', len(alertas), None), ('J', 'J', 'Alertas con intervención', f'{con_intervencion} de {len(alertas)}', None)]
    for desde, hasta, titulo_b, valor, nivel in bloques:
        for fila_b, contenido, es_titulo in ((r + 1, titulo_b, True), (r + 2, valor, False)):
            if desde != hasta:
                ws.merge_cells(f'{desde}{fila_b}:{hasta}{fila_b}')
            c = ws[f'{desde}{fila_b}']
            if es_titulo:
                c.value, c.font, c.fill = contenido, Font(bold=True, size=9, color='FFFFFF'), fill(NAVY)
            else:
                c.value = contenido if nivel is None else f'{contenido} ({pct(contenido):.1%})'.replace('.', ',')
                c.font = Font(bold=True, size=11, color=INK)
                if nivel:
                    c.fill = fill(NIVELES[nivel][1].lstrip('#').upper())
            c.alignment = centro
            for col in range(ws[f'{desde}1'].column, ws[f'{hasta}1'].column + 1):
                ws.cell(row=fila_b, column=col).border = borde
    ws.row_dimensions[r + 1].height = 28
    r += 4

    fila_unida(r, '3. Detalle de alertas', Font(bold=True, size=11, color=NAVY))
    r += 1
    inicio = r
    for col, nombre in enumerate(columnas, start=1):
        c = ws.cell(row=r, column=col, value=nombre)
        c.font, c.fill, c.alignment, c.border = Font(bold=True, size=9, color='FFFFFF'), fill(NAVY), centro, borde
    ws.row_dimensions[r].height = 30
    for i, a in enumerate(alertas, start=1):
        r += 1
        nombre_nivel, fondo, texto = NIVELES.get(a['nivel'], (a['nivel'], '#FFFFFF', '#1E293B'))
        valores = [i, a['etiqueta'], a['curso'], a['gestion'], nombre_nivel, f"{a['prioridad']['puesto']} de {a['prioridad']['de']}",
            ESTADOS[a['estado']], factores_claros(a), ' '.join(a['reglas']) or '—',
            '\n'.join(paso_texto(x) for x in a['pasos']) or 'Sin intervenciones']
        for col, valor in enumerate(valores, start=1):
            c = ws.cell(row=r, column=col, value=valor)
            c.font, c.alignment, c.border = Font(size=9, color=INK, bold=col == 2), envolver, borde
            if i % 2 == 0:
                c.fill = fill('F5F7FA')
        prioridad = ws.cell(row=r, column=5)
        prioridad.fill = fill(fondo.lstrip('#').upper())
        prioridad.font = Font(size=9, bold=True, color=texto.lstrip('#').upper())
    if alertas:
        ws.auto_filter.ref = f'A{inicio}:{ultima}{r}'
    else:
        r += 1
        fila_unida(r, 'No hay alertas para este alcance.', Font(size=9, color=GRAY))

    r += 2
    fila_unida(r, '4. Consideraciones', Font(bold=True, size=11, color=NAVY))
    reglas = {}
    for a in alertas:
        reglas.update(a.get('reglas_info') or {})
    notas = [NOTA_PRIORIDAD, APOYO]
    if reglas:
        notas.append('Reglas de recomendación: ' + '; '.join(f'{k} = {v}' for k, v in sorted(reglas.items()))
            + f'. Versión {rp.VERSION} ({rp.VALIDACION}).')
    notas.append('Los estudiantes se identifican con un código anónimo; el documento no contiene nombres ni datos personales.')
    for nota in notas:
        r += 1
        fila_unida(r, f'•  {nota}', Font(size=9, color=INK), Alignment(wrap_text=True, vertical='top'), 26)

    r += 3
    for desde, hasta, rol, quien in (('B', 'D', 'Elaborado por', f'{user.nombre} {user.apellido} · {user.rol}'),
            ('G', 'H', 'Revisado por', 'Director(a) de la Unidad Educativa')):
        for k, (valor, negrita) in enumerate((('', False), (rol, True), (quien, False))):
            ws.merge_cells(f'{desde}{r + k}:{hasta}{r + k}')
            c = ws[f'{desde}{r + k}']
            c.value, c.font, c.alignment = valor, Font(size=9, bold=negrita, color=INK), Alignment(horizontal='center')
            if k == 0:
                for col in range(ws[f'{desde}1'].column, ws[f'{hasta}1'].column + 1):
                    ws.cell(row=r, column=col).border = Border(bottom=Side(style='thin', color=INK))

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.oddFooter.left.text = f'{SISTEMA} · Uso interno y confidencial · Estudiantes anonimizados'
    ws.oddFooter.left.size = 7
    ws.oddFooter.right.text = 'Página &P de &N'
    ws.oddFooter.right.size = 7

    hoja = wb.create_sheet('Datos')
    encabezado = ['Estudiante', 'Gestión', 'Curso', 'Prioridad', 'Puesto', 'De', 'Estado', 'Responsable (rol)', 'Factores', 'Reglas',
        'Intervenciones', 'Modelo', 'Fecha de corte']
    hoja.append(encabezado)
    for a in alertas:
        hoja.append([a['etiqueta'], a['gestion'], a['curso'], NIVELES.get(a['nivel'], (a['nivel'],))[0], a['prioridad']['puesto'],
            a['prioridad']['de'], ESTADOS[a['estado']], a['responsable']['rol'], factores_claros(a), ' '.join(a['reglas']),
            ' || '.join(paso_texto(x) for x in a['pasos']), a['modelo'], a['fecha_corte']])
    for (celda,) in hoja.iter_rows(min_row=2, min_col=13, max_col=13):
        celda.number_format = 'DD/MM/YYYY'
    for i, ancho in enumerate((18, 9, 9, 10, 8, 6, 14, 16, 60, 14, 60, 32, 14), start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    if alertas:
        tabla = TablaExcel(displayName='Alertas', ref=f'A1:{get_column_letter(len(encabezado))}{len(alertas) + 1}')
        tabla.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
        hoja.add_table(tabla)
    hoja.freeze_panes = 'A2'

    buffer = io.BytesIO()
    wb.save(buffer)
    return Response(buffer.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{nombre_archivo(gestion, curso_id, "xlsx")}"'})
