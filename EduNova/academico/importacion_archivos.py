"""Lectura estricta de CSV/XLSX para el importador privado de EduNova.

Sin dependencias adicionales ni ejecución de macros/fórmulas. Los PDF de malla
con texto dibujado se conservan como referencia, nunca se adivinan asignaturas.
"""
from collections import Counter, defaultdict
import csv
from datetime import time
from io import BytesIO, StringIO
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

MAX_FILAS = 25000
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def normalizar(valor):
    s = unicodedata.normalize('NFKD', str(valor or ''))
    return re.sub(r'\s+', ' ', ''.join(c for c in s if not unicodedata.combining(c)).upper()).strip()


def columna_normalizada(s):
    return re.sub(r'[^A-Z0-9]', '', normalizar(s))


def _cell_value(cell, strings):
    typ = cell.attrib.get('t')
    if typ == 'inlineStr':
        return ''.join(t.text or '' for t in cell.findall('.//x:t', NS))
    value = cell.find('x:v', NS)
    if value is None:
        return ''
    raw = value.text or ''
    if typ == 's':
        try:
            return strings[int(raw)]
        except (IndexError, ValueError):
            return ''
    if typ == 'b':
        return raw == '1'
    return raw


def leer_xlsx(datos, nombre_hoja='BASE'):
    if len(datos) > 12 * 1024 * 1024:
        raise ValueError('El archivo Excel supera el máximo de 12 MB.')
    try:
        with ZipFile(BytesIO(datos)) as zipf:
            # Evita ZIP bombs y archivos XLSX excesivamente inflados.
            if sum(i.file_size for i in zipf.infolist()) > 90 * 1024 * 1024:
                raise ValueError('El Excel descomprimido supera el máximo permitido.')
            archivos = set(zipf.namelist())
            if 'xl/workbook.xml' not in archivos:
                raise ValueError('El archivo no es un Excel .xlsx válido.')
            libro = ET.fromstring(zipf.read('xl/workbook.xml'))
            relaciones = ET.fromstring(zipf.read('xl/_rels/workbook.xml.rels'))
            targets = {r.attrib['Id']: r.attrib['Target'] for r in relaciones}
            hojas = []
            for hoja in libro.findall('x:sheets/x:sheet', NS):
                rid = hoja.attrib.get('{%s}id' % NS['r'])
                target = targets.get(rid, '')
                if target.startswith('/'):
                    path = target.lstrip('/')
                elif target.startswith('xl/'):
                    path = target
                else:
                    path = 'xl/' + target
                hojas.append((hoja.attrib['name'], path))
            hoja = next((p for n, p in hojas if normalizar(n) == normalizar(nombre_hoja)), None)
            if hoja is None:
                hoja = hojas[0][1] if hojas else None
            if not hoja or hoja not in archivos:
                raise ValueError('No hay una hoja válida para importar.')
            strings = []
            if 'xl/sharedStrings.xml' in archivos:
                root = ET.fromstring(zipf.read('xl/sharedStrings.xml'))
                strings = [''.join(t.text or '' for t in s.findall('.//x:t', NS)) for s in root.findall('x:si', NS)]
            # ET.iterparse evita construir el XML completo de la oferta (casi 10.000 filas).
            stream = BytesIO(zipf.read(hoja))
            filas = []
            for _, elem in ET.iterparse(stream, events=('end',)):
                if elem.tag != '{%s}row' % NS['x']:
                    continue
                cells = {}
                for cell in elem.findall('x:c', NS):
                    ref = re.match(r'[A-Z]+', cell.attrib.get('r', ''))
                    if not ref:
                        continue
                    idx = 0
                    for letra in ref.group():
                        idx = idx * 26 + ord(letra) - 64
                    if idx <= 50:
                        cells[idx-1] = _cell_value(cell, strings)
                if cells:
                    fila = [cells.get(i, '') for i in range(max(cells) + 1)]
                    if any(str(v).strip() for v in fila):
                        filas.append(fila)
                        if len(filas) > MAX_FILAS + 2:
                            raise ValueError('La planilla supera el límite de 25.000 filas.')
                elem.clear()
            return filas
    except (BadZipFile, ET.ParseError, KeyError) as exc:
        raise ValueError('El Excel está dañado o no tiene una estructura compatible.') from exc


def leer_filas(datos, nombre):
    ext = nombre.lower().rsplit('.', 1)[-1] if '.' in nombre else ''
    if ext == 'xlsx':
        return leer_xlsx(datos)
    if ext == 'csv':
        if len(datos) > 12 * 1024 * 1024:
            raise ValueError('El CSV supera el máximo de 12 MB.')
        try:
            contenido = datos.decode('utf-8-sig')
        except UnicodeDecodeError:
            contenido = datos.decode('cp1252')
        muestra = contenido[:4096]
        try:
            dialect = csv.Sniffer().sniff(muestra, delimiters=',;\t')
            filas = list(csv.reader(StringIO(contenido), dialect))
        except csv.Error:
            filas = list(csv.reader(StringIO(contenido), delimiter=';'))
        if len(filas) > MAX_FILAS + 2:
            raise ValueError('El CSV supera el límite de 25.000 filas.')
        return filas
    raise ValueError('Solo se admiten archivos .xlsx y .csv para importar registros.')


def _en_tablas(filas):
    if not filas:
        raise ValueError('El documento no contiene filas.')
    cabeceras = [columna_normalizada(h) for h in filas[0]]
    if len(set(h for h in cabeceras if h)) != len([h for h in cabeceras if h]):
        raise ValueError('Existen encabezados duplicados en la primera fila.')
    for n, row in enumerate(filas[1:], start=2):
        yield n, {cabeceras[i]: str(row[i]).strip() if i < len(row) and row[i] is not None else ''
                  for i in range(len(cabeceras))}


def _campo(row, *aliases):
    for alias in aliases:
        value = row.get(columna_normalizada(alias), '')
        if value:
            return value.strip()
    return ''


def leer_malla(datos, nombre):
    """Planilla transcrita y revisada, NO OCR de la malla PDF."""
    salida, errores = [], []
    for n, row in _en_tablas(leer_filas(datos, nombre)):
        codigo = _campo(row, 'codigo', 'sigla', 'sigla asignatura', 'codigo asignatura')
        asignatura = _campo(row, 'asignatura', 'nombre asignatura', 'nombre')
        ano = _campo(row, 'anio curricular', 'año curricular', 'anio', 'año', 'nivel anual')
        sem = _campo(row, 'semestre curricular', 'semestre')
        if not codigo and not asignatura and not ano and not sem:
            continue
        codigo = codigo.upper()
        if not re.fullmatch(r'[A-Z0-9-]{2,24}', codigo):
            errores.append(f'Fila {n}: código de asignatura inválido.')
        if not asignatura or len(asignatura) > 180:
            errores.append(f'Fila {n}: falta el nombre de la asignatura o es demasiado largo.')
        if ano not in ('1','2','3','4'):
            errores.append(f'Fila {n}: año curricular debe estar entre 1 y 4.')
        if sem not in ('1','2'):
            errores.append(f'Fila {n}: semestre debe ser 1 o 2.')
        if re.fullmatch(r'[A-Z0-9-]{2,24}', codigo) and asignatura and len(asignatura) <= 180 and ano in ('1','2','3','4') and sem in ('1','2'):
            salida.append({'codigo': codigo, 'nombre': asignatura, 'anio': int(ano), 'semestre': int(sem)})
    if not salida:
        errores.append('No se encontraron asignaturas importables.')
    repetidas = Counter(item['codigo'] for item in salida)
    errores.extend(f'El código {cod} aparece más de una vez en la malla.' for cod, n in repetidas.items() if n > 1)
    return {'filas': salida, 'errores': errores[:80], 'total': len(salida)}


DIAS = {'LU': 1, 'MA': 2, 'MI': 3, 'JU': 4, 'VI': 5, 'SA': 6, 'DO': 7}
HORARIO = re.compile(r'^\s*(LU|MA|MI|JU|VI|SA|DO)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*$', re.I)


def _hora(s):
    h, m, *sec = map(int, s.split(':'))
    if h > 23 or m > 59 or (sec and sec[0] > 59):
        raise ValueError('hora inválida')
    return time(h, m, sec[0] if sec else 0)


def convertir_horario(txt):
    coincidencia = HORARIO.fullmatch(txt or '')
    if not coincidencia:
        return None
    dia, i, f = coincidencia.groups()
    try:
        ini, fin = _hora(i), _hora(f)
    except (ValueError, TypeError):
        return None
    if not ini < fin or (ini == time(0,0) and fin == time(0,0)):
        return None
    return DIAS[dia.upper()], ini, fin


def leer_oferta(datos, nombre):
    """Lee BASE de la oferta real (una fila por bloque horario, no por sección)."""
    grupos, errores, advertencias, carreras = {}, [], [], Counter()
    datos_filas = leer_filas(datos, nombre)
    encabezado = {columna_normalizada(c) for c in datos_filas[0]} if datos_filas else set()
    requeridos = {'SEDE', 'CARRERA', 'SIGLAASIGNATURA', 'NOMBREASIGNATURA', 'SECCION'}
    if not requeridos.issubset(encabezado):
        raise ValueError('La oferta debe incluir Sede, Carrera, Sigla Asignatura, Nombre Asignatura y Sección.')
    total, fuera = 0, 0
    for n, row in _en_tablas(datos_filas):
        sede = _campo(row, 'sede')
        if not sede:
            continue
        if normalizar(sede) != 'ANTONIO VARAS':
            fuera += 1
            continue
        carrera = _campo(row, 'carrera')
        codigo = _campo(row, 'sigla asignatura', 'sigla', 'codigo') .upper()
        nombre_asignatura = _campo(row, 'nombre asignatura', 'asignatura')
        codigo_sec = _campo(row, 'seccion').upper().replace(' ', '')
        docente = _campo(row, 'docente')
        turno = codigo_sec[-1] if codigo_sec.endswith(('D', 'V')) else ('V' if normalizar(_campo(row, 'jornada')).startswith('VESPERT') else 'D')
        if not carrera or not re.fullmatch(r'[A-Z0-9-]{2,24}', codigo) or not re.fullmatch(r'[A-Z0-9-]{3,45}', codigo_sec) or not nombre_asignatura:
            errores.append(f'Fila {n}: datos obligatorios inválidos (carrera, código, asignatura o sección).')
            continue
        if len(nombre_asignatura) > 180:
            errores.append(f'Fila {n}: nombre de asignatura demasiado largo.')
            continue
        total += 1
        carreras[carrera] += 1
        clave = (codigo, codigo_sec)
        if clave not in grupos:
            grupos[clave] = {'codigo': codigo, 'nombre': nombre_asignatura, 'seccion': codigo_sec,
                             'turno': turno, 'carreras': set(), 'docentes': set(), 'horarios': set()}
        grupo = grupos[clave]
        if normalizar(grupo['nombre']) != normalizar(nombre_asignatura) or grupo['turno'] != turno:
            errores.append(f'Fila {n}: la sección {codigo_sec} tiene datos contradictorios.')
            continue
        grupo['carreras'].add(carrera)
        if docente and normalizar(docente) not in ('POR DEFINIR', 'SIN DOCENTE', 'NO ASIGNADO', '-'):
            grupo['docentes'].add(docente)
        texto_horario = _campo(row, 'horario')
        if texto_horario:
            horario = convertir_horario(texto_horario)
            if horario:
                grupo['horarios'].add(horario)
            elif len(advertencias) < 30:
                advertencias.append(f'Fila {n}: horario «{texto_horario}» no interpretado; requiere revisión manual.')
    if not grupos:
        errores.append('No se encontraron secciones de Antonio Varas para importar.')
    if fuera:
        advertencias.append(f'{fuera} filas de otras sedes se omitieron.')
    return {'grupos': grupos, 'carreras': carreras, 'total': total,
            'errores': errores[:80], 'advertencias': advertencias[:40]}
