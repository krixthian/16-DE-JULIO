"""Manual de uso en PDF: cada captura a la izquierda, con marcas numeradas, y los pasos en un marco a la derecha.

Uso: python docs/manual/generar_manual.py   (las capturas están en docs/manual/capturas)
"""
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

D = Path(__file__).resolve().parent
CAP, LIMPIAS, SALIDA = D / 'capturas', D / 'capturas_limpias', D / 'MANUAL_SISTEMA_ALERTA_TEMPRANA.pdf'
pdfmetrics.registerFont(TTFont('S', 'C:/Windows/Fonts/segoeui.ttf'))
pdfmetrics.registerFont(TTFont('SB', 'C:/Windows/Fonts/segoeuib.ttf'))
pdfmetrics.registerFontFamily('S', normal='S', bold='SB', italic='S', boldItalic='SB')
W, H = landscape(A4)
AZUL, TINTA, GRIS, NARANJA = HexColor('#1e3a8a'), HexColor('#0f172a'), HexColor('#475569'), HexColor('#ea580c')

# Zonas con nombres de personas que se tapan (docentes, estudiantes, correos).
TAPAR = {'03_usuarios': [(200, 130, 420, 584), (425, 130, 620, 584)], '05_cursos': [(474, 240, 670, 584)], '06_matriculas': [(202, 240, 324, 584)],
    '07_asignaciones': [(470, 240, 618, 584)], '08_asistencia': [(208, 418, 355, 584)], '09_asistencia_materia': [(195, 448, 352, 584)], '10_calificaciones': [(249, 280, 420, 296)]}

# (archivo, sección, título, para qué sirve, [(paso, (x, y) de la marca o None)], qué mirar)
P = [
 ('01_login', 'Entrar', 'Iniciar sesión', 'Cada persona entra con su propia cuenta y ve solo lo que le corresponde a su rol.',
  [('Escribe tu <b>correo</b>.', (255, 310)), ('Escribe tu <b>contraseña</b>.', (255, 378)), ('Pulsa <b>Iniciar Sesión</b>.', (255, 428))],
  'La sesión vence a las 2 horas: si el sistema vuelve a esta pantalla, entra de nuevo.'),
 ('02_inicio', 'Entrar', 'Panel de control', 'Es la entrada al sistema: muestra cuántos registros hay y lleva a cada módulo.',
  [('El <b>menú</b> de la izquierda tiene todos los módulos.', (12, 223)), ('Cada <b>tarjeta</b> muestra un total.', (195, 170)), ('Pulsa <b>Abrir módulo</b> para entrar.', (195, 226))],
  'El menú cambia según el rol: el docente no ve la administración ni la gestión de alertas.'),
 ('03_usuarios', '1. Preparar la escuela', 'Gestión de usuarios', 'El administrador crea las cuentas y asigna el rol de cada una.',
  [('Abre <b>Gestión Usuarios</b>.', (12, 268)), ('Pulsa <b>Nuevo Usuario</b> y completa sus datos.', (632, 45)), ('Elige el <b>rol</b>: Admin, Director, Orientador o Docente.', (640, 150))],
  'Solo el administrador ve esta pantalla. Los nombres y correos están tapados por privacidad.'),
 ('04_gestiones', '1. Preparar la escuela', 'Gestiones escolares', 'Define el año escolar y sus fechas. Todo lo demás depende de esto.',
  [('Abre <b>Gestiones</b>.', (12, 339)), ('Pulsa <b>Registrar gestión</b>.', (660, 53)), ('Indica el año, el <b>inicio</b> y el <b>fin</b>.', (290, 221)), ('Para corregir, pulsa <b>Editar</b>.', (660, 255))],
  'Las gestiones 2021-2025 vienen de los archivos recibidos. La 2026 es <b>simulada</b>.'),
 ('05_cursos', '1. Preparar la escuela', 'Cursos', 'Crea los grados y paralelos de cada gestión, con su docente asesor.',
  [('Abre <b>Cursos</b>.', (12, 378)), ('Pulsa <b>Registrar curso</b>.', (658, 53)), ('Indica gestión, <b>grado</b> y <b>paralelo</b>.', (288, 221)), ('Filtra por gestión si hace falta.', (572, 179))],
  'Primero la gestión, después el curso. Los nombres de docentes están tapados.'),
 ('06_matriculas', '1. Preparar la escuela', 'Matrículas', 'Une a cada estudiante con su curso y guarda desde cuándo pertenece a él.',
  [('Abre <b>Matrículas</b>.', (12, 456)), ('Pulsa <b>Registrar matrícula</b>.', (642, 53)), ('Elige estudiante, curso y <b>fecha de ingreso</b>.', (435, 221)), ('Indica el <b>origen</b> de los datos.', (612, 221))],
  'La columna <b>Datos</b> distingue los simulados. Lo anterior al ingreso no cuenta para el estudiante.'),
 ('07_asignaciones', '1. Preparar la escuela', 'Asignaciones docentes', 'Dice qué docente enseña cada materia en cada curso.',
  [('Abre <b>Asignaciones</b>.', (12, 534)), ('Pulsa <b>Registrar asignación</b>.', (636, 53)), ('Elige curso, <b>materia</b> y docente.', (302, 221)), ('Indica <b>desde</b> y hasta cuándo.', (630, 221))],
  'De aquí salen los permisos: cada docente solo registra y consulta sus propias asignaciones.'),
 ('08_asistencia', '2. Registrar cada día', 'Asistencia diaria', 'El docente registra quién vino. Es el dato que más usa el sistema para alertar.',
  [('Elige el <b>curso</b>.', (208, 150)), ('Elige la <b>fecha</b>.', (552, 150)), ('Pulsa <b>Consultar lista</b>.', (652, 151)), ('Marca el <b>estado</b>: presente, falta, atraso o licencia.', (364, 437)), ('Guarda al final de la lista.', None)],
  'Quien queda sin registro no cuenta como falta. Los nombres están tapados por privacidad.'),
 ('09_asistencia_materia', '2. Registrar cada día', 'Asistencia por materia', 'Registra la asistencia hora por hora: sirve si un estudiante se va antes o llega tarde.',
  [('Elige curso y fecha y pulsa <b>Consultar</b>.', (678, 169)), ('Elige la <b>hora</b> de clase.', (200, 266)), ('Elige la <b>materia</b> y confirma que la clase se dictó.', (190, 382)), ('Marca el estado de cada estudiante.', (362, 468)), ('En <b>Desglose por estudiante</b> se ve el resumen.', (302, 91))],
  'Un día cuenta como falta solo si el estudiante faltó a todas las horas registradas.'),
 ('10_calificaciones', '2. Registrar cada día', 'Calificaciones', 'El docente crea evaluaciones y registra las notas de su materia.',
  [('Elige <b>curso y materia</b>.', (196, 213)), ('Pulsa <b>Consultar evaluaciones</b>.', (616, 213)), ('Pulsa <b>Crear evaluación</b> y elige tipo, fecha, puntaje y <b>dimensión</b>.', (648, 277)), ('Pulsa <b>Registrar notas</b>.', (622, 353))],
  'La dimensión se elige de una lista: Ser, Saber, Hacer, Decidir o Autoevaluación. Un cero es una nota válida.'),
 ('11_tareas', '2. Registrar cada día', 'Seguimiento de tareas', 'Registra las tareas, su plazo y quién las entregó.',
  [('Elige curso y materia y pulsa <b>Consultar tareas</b>.', (656, 150)), ('Pulsa <b>Crear tarea</b> e indica el plazo.', (694, 226)), ('Pulsa <b>Ver entregas</b> para marcar quién entregó.', (594, 344))],
  'Una entrega pendiente no se cuenta como incumplida hasta que el docente la revise.'),
 ('12_notas', '3. Ver las notas desglosadas', 'Notas desglosadas', 'Muestra la nota de cada dimensión por estudiante, comparada con su curso.',
  [('Abre <b>Notas desglosadas</b> en el menú.', None), ('Elige <b>gestión, curso y materia</b>.', (190, 151)), ('Compara con el <b>promedio del curso</b>.', (190, 358)), ('En rojo, lo que está por debajo de 51.', (460, 529)), ('Pulsa un <b>estudiante</b> para ver su detalle.', (190, 386))],
  'Ser, Saber, Hacer, Decidir y Autoevaluación están sobre 100. Una casilla sin nota no cuenta como cero.'),
 ('13_actividades', '3. Ver las notas desglosadas', 'Actividades de cada dimensión', 'Abre una dimensión y muestra las actividades que la forman.',
  [('Dentro del estudiante, pulsa <b>Ver actividades</b>.', (364, 40)), ('Lee cada <b>actividad</b> y su fecha.', (210, 95)), ('Compara su <b>nota</b> con la del curso.', (640, 113)), ('Pulsa <b>Ocultar actividades</b> para cerrar.', (490, 57))],
  'En 2026 (simulado) cada actividad tiene fecha. En 2021-2025 dice «sin fecha propia»: los archivos no la traen.'),
 ('14_alertas', '4. Atender las alertas', 'Alertas de riesgo', 'Resume a quién hay que revisar primero en la gestión en curso.',
  [('Abre <b>Alertas de riesgo</b>.', (12, 575)), ('Mira la <b>alerta inmediata</b>: 5 o más faltas seguidas.', (384, 238)), ('Mira los colores: <b>rojo, amarillo y verde</b> ordenan la prioridad.', (190, 335)), ('Las <b>pestañas</b> separan cada tipo de aviso.', (190, 412))],
  'El color ordena a quién revisar. No es la probabilidad de que abandone.'),
 ('15_alertas_lista', '4. Atender las alertas', 'Seguimiento a la fecha', 'Lista a los estudiantes con alerta y explica por qué aparecen.',
  [('Elige <b>gestión</b> y <b>fecha</b>: el riesgo se recalcula con lo registrado hasta ese día.', (190, 47)), ('En <b>Mostrar</b>, elige solo alertas o todos.', (388, 47)), ('Revisa la <b>prioridad</b> y las faltas seguidas.', (466, 199)), ('Lee el <b>por qué</b>.', (696, 199)), ('Desliza a la derecha y pulsa <b>Ver caso</b>.', (680, 446))],
  'Son dos capas: la regla de 5 faltas avisa; el modelo XGBoost ordena a quién revisar primero.'),
 ('16_todas', '4. Atender las alertas', 'Todas las gestiones', 'Muestra las alertas inmediatas de cada año y, en los pasados, cuántas coincidieron con abandonos.',
  [('Pulsa <b>Todas las gestiones</b>.', (270, 158)), ('Compara <b>alertas</b> con <b>abandonos</b> por año.', (440, 213)), ('Lee el <b>total</b>.', (190, 441))],
  'Es una revisión de datos pasados, con archivos de origen no verificado y el abandono definido por la asistencia. No es una garantía.'),
 ('17_casos', '4. Atender las alertas', 'Casos en seguimiento', 'Cada alerta inmediata abre un caso para que alguien lo atienda.',
  [('Abre la pestaña <b>Casos en seguimiento</b>.', (336, 140)), ('Filtra por estado, gestión, curso o nivel.', (190, 211)), ('Pulsa un <b>caso</b>.', (190, 286)), ('A la derecha aparece su <b>detalle</b>.', (584, 260))],
  'Asigna un <b>responsable</b> y cambia el <b>estado</b> (Nueva, En revisión, En seguimiento) conforme se atiende.'),
 ('18_recomendaciones', '4. Atender las alertas', 'Recomendaciones e intervenciones', 'Propone qué hacer y deja registrado lo que se hizo.',
  [('Cambia el <b>estado</b> del caso.', (586, 29)), ('Lee la <b>recomendación</b> y por qué se activa.', (594, 164)), ('Pulsa <b>Registrar como intervención</b>.', (594, 333)), ('Para terminar, escribe el motivo y pulsa <b>Cerrar</b>.', (586, 58))],
  'Todo cambio queda en el historial con fecha y usuario. Las recomendaciones están por validar con Dirección.'),
 ('19_caso_explicacion', '4. Atender las alertas', 'Por qué tiene esa prioridad', 'Explica el caso en palabras y con un gráfico.',
  [('Baja hasta <b>1. Por qué está en este nivel</b>.', (206, 8)), ('Mira el <b>día en que llegó a 5 faltas</b>.', (206, 90)), ('Lee el resumen <b>en palabras</b>.', (206, 203)), ('En el gráfico, la barra más larga es lo que <b>más pesó</b>.', (392, 56))],
  'En este caso simulado pesan las faltas: el estudiante ya dejó de venir.'),
 ('20_caso_variables', '4. Atender las alertas', 'Las 23 variables del modelo', 'Muestra cada variable del estudiante junto al promedio de su curso.',
  [('Pulsa <b>Ver las 23 variables</b>.', None), ('Compara <b>estudiante</b> y <b>curso</b>.', (404, 101)), ('Busca las <b>notas por dimensión</b>.', (192, 286)), ('Mira el <b>efecto</b> y el aporte.', (560, 286))],
  '«Sin efecto» significa que el modelo la consideró, pero no cambió el puntaje. Las 8 de dimensión se agregaron por diseño; no mejoraron la detección.'),
 ('21_academico', '4. Atender las alertas', 'Riesgo académico por reglas', 'Señala a quienes tienen alguna área por debajo de 51 en el primer trimestre.',
  [('Abre <b>Riesgo académico por reglas</b>.', (472, 140)), ('Elige la <b>gestión</b>.', (190, 318)), ('Revisa las <b>áreas</b> con nota baja.', (350, 405)), ('La columna <b>Reglas</b> dice qué criterio se cumplió.', (708, 405))],
  'No es una predicción: sirve para dar reforzamiento.'),
 ('22_inasistencia', '4. Atender las alertas', 'Inasistencia continua', 'Lista a quienes acumulan faltas seguidas en este momento.',
  [('Abre <b>Inasistencia continua</b>.', (190, 291)), ('Elige <b>3, 5 o 10</b> faltas.', (190, 451)), ('Mira <b>desde</b> cuándo falta y su última asistencia.', (552, 519))],
  'Es una regla propuesta, no una predicción. Las faltas salteadas no la activan.'),
 ('23_docente', '5. Lo que ve el docente', 'Mis estudiantes con alerta', 'Devuelve al docente las alertas de sus propios cursos.',
  [('Abre <b>Mis estudiantes con alerta</b>.', None), ('Elige <b>gestión</b> y <b>fecha</b>.', (190, 151)), ('Lee cuántas <b>faltas seguidas</b> tiene y por qué.', (362, 322)), ('<b>Avisa</b> a Dirección u Orientación.', (204, 478)), ('O <b>cita a la familia</b> por tu materia.', (334, 550))],
  'El docente no ve puntajes ni otros cursos. Esta captura es la vista previa del administrador.'),
 ('24_panel', '6. Informes y resultados', 'Panel analítico', 'Resume cuántas alertas hay y qué se hizo con ellas.',
  [('Abre <b>Panel analítico</b> en el menú.', None), ('Elige la <b>gestión</b>.', (630, 53)), ('Mira cuántas alertas hay por <b>prioridad</b>.', (200, 282)), ('Mira cuántas están <b>sin intervención</b>.', (492, 425))],
  'Más abajo están los gráficos y el reporte. Las dos alertas son de 2026 (simulado).'),
 ('25_resultados', '6. Informes y resultados', 'Resultados del modelo', 'Muestra cómo se evaluó el modelo, mes a mes.',
  [('Abre <b>Resultados del modelo</b> en el menú.', None), ('Lee primero el <b>aviso</b> sobre el origen de los datos.', (190, 146)), ('Revisa las tres <b>tarjetas</b>.', (204, 368)), ('En el <b>gráfico</b>, compara el modelo con el azar.', (470, 500))],
  'De febrero a mayo el modelo no se distingue del azar. Desde junio detecta que el estudiante dejó de venir; no lo predice antes.'),
]


def limpiar():
    LIMPIAS.mkdir(exist_ok=True)
    for f, *_ in P:
        im = Image.open(CAP / f'{f}.jpg').convert('RGB')
        for x0, y0, x1, y1 in TAPAR.get(f, []):
            y = y0
            while y < y1:  # franjas por fila, con el color de fondo de la propia imagen
                fondo = im.getpixel((min(x1 + 1, im.width - 1), min(y, im.height - 1)))
                im.paste(fondo, (x0, y, x1, min(y + 1, y1)))
                y += 1
            paso = 37 if f not in ('03_usuarios', '08_asistencia', '09_asistencia_materia') else 50
            for yy in range(y0 + 14, y1 - 5, paso):
                im.paste((71, 85, 105), (x0 + 4, yy - 4, min(x0 + 110, x1 - 4), yy + 5))
        if f != '01_login':
            im = im.crop((0, 0, 778, im.height))
        im.save(LIMPIAS / f'{f}.png')


def est(size, color=TINTA, fuente='S', lead=None):
    return ParagraphStyle('x', fontName=fuente, fontSize=size, leading=lead or size * 1.32, textColor=color)


def parrafo(c, texto, x, y, ancho, estilo):
    p = Paragraph(texto, estilo)
    _, h = p.wrap(ancho, 1000)
    p.drawOn(c, x, y - h)
    return y - h


def marca(c, x, y, n, r=8):
    c.setFillColor(NARANJA)
    c.setStrokeColor(white)
    c.setLineWidth(1.4)
    c.circle(x, y, r, fill=1, stroke=1)
    c.setFillColor(white)
    c.setFont('SB', r * 1.2)
    c.drawCentredString(x, y - r * .42, str(n))


def pie(c, n, total):
    c.setFillColor(GRIS)
    c.setFont('S', 8)
    c.drawString(1.3 * cm, .65 * cm, 'U.E. 16 de Julio · Sistema de alerta temprana · Manual de uso')
    c.drawRightString(W - 1.3 * cm, .65 * cm, f'{n} de {total}')


def main():
    limpiar()
    total = len(P) + 2
    c = canvas.Canvas(str(SALIDA), pagesize=(W, H))
    c.setTitle('Manual del sistema de alerta temprana')
    c.setAuthor('Cristhian Aguilar')
    # Portada
    c.setFillColor(AZUL)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('SB', 34)
    c.drawString(2.2 * cm, H - 6.2 * cm, 'Sistema de alerta temprana')
    c.setFont('S', 19)
    c.drawString(2.2 * cm, H - 7.5 * cm, 'Manual de uso, paso a paso')
    parrafo(c, 'Unidad Educativa 16 de Julio · La Paz<br/>Proyecto de grado de Cristhian Aguilar · noviembre de 2026', 2.2 * cm, H - 9 * cm, 20 * cm, est(13, white))
    parrafo(c, '<b>Sobre los datos de las capturas.</b> La gestión 2026 es simulada. Las gestiones 2021-2025 vienen de archivos recibidos cuyo origen no se contrastó con los registros '
        'físicos ni con el SIE: sus cifras muestran cómo funciona el sistema, no su capacidad de predicción en estudiantes reales. Los nombres de personas están tapados.',
        2.2 * cm, 4.6 * cm, W - 4.4 * cm, est(11.5, white, lead=16))
    c.showPage()
    # Recorrido
    c.setFillColor(AZUL)
    c.setFont('SB', 22)
    c.drawString(1.3 * cm, H - 1.8 * cm, 'Recorrido completo')
    parrafo(c, 'Sigue los bloques en orden. En cada página, los números naranjas de la captura corresponden a los pasos del marco de la derecha.', 1.3 * cm, H - 2.3 * cm, W - 2.6 * cm, est(11.5, GRIS))
    secciones = {}
    for i, (_, s, t, *_) in enumerate(P):
        secciones.setdefault(s, []).append((t, i + 3))
    quien = {'Entrar': 'Todos', '1. Preparar la escuela': 'Administrador y Dirección', '2. Registrar cada día': 'Docentes', '3. Ver las notas desglosadas': 'Docentes y Dirección',
        '4. Atender las alertas': 'Dirección y Orientación', '5. Lo que ve el docente': 'Docentes', '6. Informes y resultados': 'Dirección y Orientación'}
    cols, alto = 4, 6.9 * cm
    an = (W - 2.6 * cm - (cols - 1) * .5 * cm) / cols
    for k, (s, items) in enumerate(secciones.items()):
        x = 1.3 * cm + (k % cols) * (an + .5 * cm)
        top = H - 4 * cm - (k // cols) * (alto + .6 * cm)
        c.setFillColor(HexColor('#eff6ff'))
        c.setStrokeColor(HexColor('#93c5fd'))
        c.roundRect(x, top - alto, an, alto, 8, fill=1, stroke=1)
        y = parrafo(c, s, x + .35 * cm, top - .25 * cm, an - .7 * cm, est(12.5, AZUL, 'SB'))
        y = parrafo(c, quien[s], x + .35 * cm, y - 2, an - .7 * cm, est(9.5, GRIS))
        for t, n in items:
            y = parrafo(c, f'{t} <font color="#64748b">· pág. {n}</font>', x + .35 * cm, y - 2.5, an - .7 * cm, est(9.6))
        assert y > top - alto, s
    pie(c, 2, total)
    c.showPage()
    for i, (f, s, t, para, pasos, mirar) in enumerate(P):
        c.setFillColor(AZUL)
        c.rect(0, H - 1.75 * cm, W, 1.75 * cm, fill=1, stroke=0)
        c.setFillColor(HexColor('#bfdbfe'))
        c.setFont('S', 10)
        c.drawString(1.3 * cm, H - .7 * cm, s)
        c.setFillColor(white)
        c.setFont('SB', 17)
        c.drawString(1.3 * cm, H - 1.4 * cm, t)
        im = Image.open(LIMPIAS / f'{f}.png')
        iw = 19 * cm
        esc = iw / im.width
        ih = im.height * esc
        x0, y0 = 1.3 * cm, H - 2.35 * cm - ih
        c.drawImage(str(LIMPIAS / f'{f}.png'), x0, y0, iw, ih)
        c.setStrokeColor(HexColor('#94a3b8'))
        c.setLineWidth(.8)
        c.rect(x0, y0, iw, ih, fill=0, stroke=1)
        for n, (_, pos) in enumerate(pasos, 1):
            if pos:
                marca(c, x0 + max(8, (pos[0] - (0 if pos[0] < 20 else 8)) * esc - 2), y0 + ih - max(8, pos[1] * esc), n)
        # Marco de la derecha
        mx = x0 + iw + .6 * cm
        mw, mtop, mbot = W - 1.3 * cm - mx, H - 2.35 * cm, y0
        c.setFillColor(HexColor('#f8fafc'))
        c.setStrokeColor(AZUL)
        c.setLineWidth(1.3)
        c.roundRect(mx, mbot, mw, mtop - mbot, 8, fill=1, stroke=1)
        tx, tw = mx + .4 * cm, mw - .8 * cm
        y = parrafo(c, 'Para qué sirve', tx, mtop - .35 * cm, tw, est(11.5, AZUL, 'SB'))
        y = parrafo(c, para, tx, y - 2, tw, est(11.3))
        y = parrafo(c, 'Pasos', tx, y - 10, tw, est(11.5, AZUL, 'SB'))
        for n, (paso, _) in enumerate(pasos, 1):
            y -= 6
            marca(c, tx + 8, y - 8, n, 7.5)
            y = min(parrafo(c, paso, tx + 22, y - 1, tw - 22, est(11.3)), y - 16)
        y = parrafo(c, 'Ten en cuenta', tx, y - 12, tw, est(11.5, AZUL, 'SB'))
        y = parrafo(c, mirar, tx, y - 2, tw, est(10.8, GRIS))
        assert y > mbot + 4, (f, 'el texto no entra en el marco')
        pie(c, i + 3, total)
        c.showPage()
    c.save()
    print(SALIDA, total, 'páginas')


if __name__ == '__main__':
    main()
