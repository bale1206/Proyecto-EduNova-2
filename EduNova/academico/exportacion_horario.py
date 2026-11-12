"""Exporta horarios personales a XLSX usando solo la biblioteca estándar.

La hoja «Horario» usa exactamente los ocho encabezados que exige
`leer_horario`; el libro puede editarse y volver a importarse en EduNova.
"""
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .horario_personal import COLUMNAS

MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
OFFICE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PACKAGE_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def _celda(columna, fila, valor, *, cabecera=False):
    # XML 1.0 no permite caracteres de control ni sustitutos aislados.
    valor = ''.join(c for c in str(valor) if c in '\t\n\r' or
                    0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or
                    0x10000 <= ord(c) <= 0x10FFFF)
    estilo = ' s="1"' if cabecera else ''
    return (f'<c r="{columna}{fila}" t="inlineStr"{estilo}>'
            f'<is><t xml:space="preserve">{escape(valor)}</t></is></c>')


def generar_horario_xlsx(bloques):
    """Genera un libro XLSX válido para Excel y para el importador propio.

    No incluye datos de otros usuarios ni relaciones con mallas o carreras.
    Cada bloque semanal se representa como una fila; las fechas se escriben
    como texto ISO para evitar cambios de interpretación regional en Excel.
    """
    filas = [list(COLUMNAS)]
    dias = ('', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')
    for bloque in bloques:
        filas.append([
            bloque.asignatura, dias[bloque.dia_semana],
            bloque.hora_inicio.strftime('%H:%M'), bloque.hora_fin.strftime('%H:%M'),
            bloque.fecha_inicio.isoformat(), bloque.fecha_fin.isoformat(),
            bloque.sala, bloque.docente,
        ])
    filas_xml = []
    for numero, valores in enumerate(filas, 1):
        celdas = ''.join(_celda(chr(65 + i), numero, valor, cabecera=numero == 1)
                         for i, valor in enumerate(valores))
        filas_xml.append(f'<row r="{numero}">{celdas}</row>')
    ultima = len(filas)
    hoja = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<worksheet xmlns="{MAIN}"><dimension ref="A1:H{ultima}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/><cols>'
        '<col min="1" max="1" width="34" customWidth="1"/>'
        '<col min="2" max="2" width="17" customWidth="1"/>'
        '<col min="3" max="4" width="17" customWidth="1"/>'
        '<col min="5" max="6" width="20" customWidth="1"/>'
        '<col min="7" max="7" width="20" customWidth="1"/>'
        '<col min="8" max="8" width="30" customWidth="1"/>'
        '</cols><sheetData>' + ''.join(filas_xml) + '</sheetData>'
        f'<autoFilter ref="A1:H{ultima}"/></worksheet>'
    )
    estilos = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<styleSheet xmlns="{MAIN}">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/>'
        '<name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF295878"/>'
        '<bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" '
        'applyFont="1" applyFill="1"/></cellXfs>'
        '</styleSheet>'
    )
    tipos = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    documento = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<workbook xmlns="{MAIN}" xmlns:r="{OFFICE_REL}">'
        '<sheets><sheet name="Horario" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relaciones = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<Relationships xmlns="{PACKAGE_REL}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )
    raiz = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    memoria = BytesIO()
    with ZipFile(memoria, 'w', ZIP_DEFLATED) as libro:
        for nombre, dato in (
            ('[Content_Types].xml', tipos), ('_rels/.rels', raiz),
            ('xl/workbook.xml', documento), ('xl/_rels/workbook.xml.rels', relaciones),
            ('xl/worksheets/sheet1.xml', hoja), ('xl/styles.xml', estilos),
        ):
            libro.writestr(nombre, dato.encode('utf-8'))
    return memoria.getvalue()
