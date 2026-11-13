"""Crea archivos XLSX editables para los horarios personales de EduNova.

No requiere librerías adicionales y mantiene exactamente el formato de la
plantilla que valida academico.horario_personal.leer_horario.
"""
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .horario_personal import COLUMNAS, COLUMNAS_ESTUDIANTE

MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def _texto_xml(value):
    """Quita caracteres prohibidos por XML 1.0 y evita fórmulas de Excel."""
    return escape(''.join(ch for ch in str(value) if ch in '\t\n\r' or
                          0x20 <= ord(ch) <= 0xD7FF or
                          0xE000 <= ord(ch) <= 0xFFFD or
                          0x10000 <= ord(ch) <= 0x10FFFF))


def generar_horario_xlsx(bloques, *, incluir_docente=False):
    """Exporta 8 columnas para estudiantes o 7 para docentes.

    El rol se decide en la vista, a partir del usuario autenticado.
    """
    dias = ('', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')
    columnas = COLUMNAS_ESTUDIANTE if incluir_docente else COLUMNAS
    ultima = "H" if incluir_docente else "G"
    filas = [columnas]
    for b in bloques:
        filas.append((
            b.asignatura, dias[b.dia_semana],
            b.hora_inicio.strftime('%H:%M'), b.hora_fin.strftime('%H:%M'),
            b.fecha_inicio.isoformat(), b.fecha_fin.isoformat(),
            b.sala,
        ) + ((b.docente or '',) if incluir_docente else ()))
    rows = []
    for numero, fila in enumerate(filas, 1):
        cells = ''.join(
            f'<c r="{chr(65 + i)}{numero}" t="inlineStr"><is>'
            f'<t xml:space="preserve">{_texto_xml(value)}</t></is></c>'
            for i, value in enumerate(fila)
        )
        rows.append(f'<row r="{numero}">{cells}</row>')
    hoja = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{MAIN}"><dimension ref="A1:{ultima}{len(filas)}"/>'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" '
        'topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        '<cols><col min="1" max="1" width="34" customWidth="1"/>'
        '<col min="2" max="2" width="16" customWidth="1"/>'
        '<col min="3" max="4" width="16" customWidth="1"/>'
        '<col min="5" max="6" width="20" customWidth="1"/>'
        '<col min="7" max="7" width="18" customWidth="1"/>'
        + ('<col min="8" max="8" width="28" customWidth="1"/>' if incluir_docente else '')
        + '</cols>'
        '<sheetData>' + ''.join(rows) + '</sheetData>'
        f'<autoFilter ref="A1:{ultima}{len(filas)}"/></worksheet>'
    )
    contenido = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    wb = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<workbook xmlns="{MAIN}" xmlns:r="{DOC_REL}">'
        '<sheets><sheet name="Horario" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    rootrels = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    result = BytesIO()
    with ZipFile(result, 'w', ZIP_DEFLATED) as archive:
        for filename, xml in (
            ('[Content_Types].xml', contenido), ('_rels/.rels', rootrels),
            ('xl/workbook.xml', wb), ('xl/_rels/workbook.xml.rels', rels),
            ('xl/worksheets/sheet1.xml', hoja),
        ):
            archive.writestr(filename, xml.encode('utf-8'))
    return result.getvalue()
