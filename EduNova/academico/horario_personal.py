"""Horario privado, independiente del catálogo de carreras y asignaturas."""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from .importacion_archivos import leer_xlsx, normalizar, NS

COLUMNAS = ('Asignatura', 'Dia', 'Hora inicio', 'Hora fin', 'Fecha inicio', 'Fecha fin', 'Sala', 'Docente')
MAX_BYTES = 5 * 1024 * 1024
MAX_BLOQUES = 300
DIAS = {normalizar(n): i for i, n in enumerate(
    ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'), 1)}


def _fecha(valor, epoch):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(valor)):
        return date.fromisoformat(str(valor))
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?Z?', str(valor)):
        return datetime.fromisoformat(str(valor).replace('Z', '+00:00')).date()
    numero = Decimal(str(valor))
    if not numero.is_finite() or numero != int(numero) or not 1 <= numero <= 109574:
        raise ValueError('fecha inválida')
    return epoch + timedelta(days=int(numero))


def _hora(valor):
    if re.fullmatch(r'\d{1,2}:\d{2}(:00)?', str(valor)):
        horas, minutos, *_ = str(valor).split(':')
        return time(int(horas), int(minutos))
    numero = Decimal(str(valor))
    if not numero.is_finite() or not 0 <= numero < 1:
        raise ValueError('hora inválida')
    minutos = int((numero * 1440).quantize(Decimal('1')))
    if minutos >= 1440:
        raise ValueError('hora inválida')
    return time(minutos // 60, minutos % 60)


def _primera_fecha(bloque, inicio=None):
    fecha = max(date.fromisoformat(bloque['fecha_inicio']), inicio or date.min)
    return fecha + timedelta(days=(bloque['dia_semana'] - fecha.isoweekday()) % 7)


def leer_horario(datos, nombre):
    """Valida el libro completo antes de permitir cualquier escritura."""
    if not nombre.lower().endswith('.xlsx') or len(datos) > MAX_BYTES:
        raise ValueError('Utiliza un archivo .xlsx de hasta 5 MB.')
    try:
        with ZipFile(BytesIO(datos)) as libro:
            archivos = libro.namelist()
            if len(archivos) > 200 or sum(f.file_size for f in libro.infolist()) > 20 * 1024 * 1024:
                raise ValueError('El libro supera el tamaño permitido.')
            if any('vbaproject' in n.lower() or 'externallinks/' in n.lower() for n in archivos):
                raise ValueError('No se admiten macros ni vínculos a otros libros.')
            for n in archivos:
                if n.startswith('xl/worksheets/') and n.endswith('.xml'):
                    xml = ET.fromstring(libro.read(n))
                    if xml.find('.//x:f', NS) is not None:
                        raise ValueError('Utiliza valores, no fórmulas, en la planilla.')
            xml = ET.fromstring(libro.read('xl/workbook.xml'))
            if not any(s.attrib.get('name') == 'Horario' for s in xml.findall('x:sheets/x:sheet', NS)):
                raise ValueError('Falta la hoja Horario. Descarga la plantilla de EduNova.')
            propiedades = xml.find('x:workbookPr', NS)
            epoch = date(1904, 1, 1) if propiedades is not None and propiedades.get('date1904') in ('1', 'true') else date(1899, 12, 30)
        filas = leer_xlsx(datos, 'Horario')
    except (BadZipFile, ET.ParseError, KeyError, RuntimeError, NotImplementedError) as exc:
        raise ValueError('No se pudo leer el XLSX. Descarga y completa la plantilla.') from exc
    if not filas or tuple(normalizar(x) for x in filas[0]) != tuple(normalizar(x) for x in COLUMNAS):
        raise ValueError('Conserva los ocho encabezados originales de la hoja Horario.')
    if not 1 <= len(filas) - 1 <= MAX_BLOQUES:
        raise ValueError('Completa entre 1 y 300 bloques en la hoja Horario.')
    bloques, errores = [], []
    for numero, fila in enumerate(filas[1:], 2):
        try:
            if len(fila) > len(COLUMNAS) and any(str(x).strip() for x in fila[8:]):
                raise ValueError('no agregues columnas adicionales')
            valores = [str(x).strip() for x in fila[:8]]
            valores += [''] * (8 - len(valores))
            asignatura, dia, inicio, fin, desde, hasta, sala, docente = valores
            if not asignatura or len(asignatura) > 160 or len(sala) > 100 or len(docente) > 150:
                raise ValueError('completa la asignatura (máximo 160 letras), sala (100) y docente (150)')
            dia = int(dia) if dia in tuple(str(i) for i in range(1, 8)) else DIAS.get(normalizar(dia))
            if dia is None:
                raise ValueError('el día debe ser Lunes a Domingo, o un número de 1 a 7')
            inicio, fin = _hora(inicio), _hora(fin)
            desde, hasta = _fecha(desde, epoch), _fecha(hasta, epoch)
            if fin <= inicio:
                raise ValueError('la hora fin debe ser posterior a la hora inicio, en el mismo día')
            if not date(2000, 1, 1) <= desde <= hasta <= date(2199, 12, 31) or (hasta - desde).days > 370:
                raise ValueError('el período debe tener hasta 370 días y estar entre los años 2000 y 2199')
            bloque = dict(asignatura=asignatura, dia_semana=dia, hora_inicio=inicio.isoformat(),
                          hora_fin=fin.isoformat(), fecha_inicio=desde.isoformat(), fecha_fin=hasta.isoformat(),
                          sala=sala, docente=docente)
            if _primera_fecha(bloque) > hasta:
                raise ValueError('el período no contiene ninguna fecha del día elegido')
            for anterior in bloques:
                if (anterior['dia_semana'] == dia and anterior['hora_inicio'] < bloque['hora_fin']
                        and bloque['hora_inicio'] < anterior['hora_fin']
                        and _primera_fecha(bloque, date.fromisoformat(anterior['fecha_inicio']))
                        <= min(hasta, date.fromisoformat(anterior['fecha_fin']))):
                    raise ValueError('hay un bloque repetido o un cruce de horario con otra fila')
            bloques.append(bloque)
        except (ValueError, InvalidOperation, OverflowError) as exc:
            errores.append(f'Fila {numero}: {exc}.')
    if errores:
        raise ValueError('\n'.join(errores[:15]))
    return bloques


def clases_personales_por_dia(usuario, year, month):
    from .models import BloqueHorarioPersonal
    primero = date(year, month, 1)
    ultimo = date(year, month, calendar.monthrange(year, month)[1])
    bloques = BloqueHorarioPersonal.objects.filter(usuario=usuario, fecha_inicio__lte=ultimo, fecha_fin__gte=primero)
    resultado = {}
    for bloque in bloques:
        fecha = max(primero, bloque.fecha_inicio)
        fecha += timedelta(days=(bloque.dia_semana - fecha.isoweekday()) % 7)
        while fecha <= min(ultimo, bloque.fecha_fin):
            resultado.setdefault(fecha.day, []).append({
                'seccion_id': f'personal-{bloque.pk}', 'asignatura': bloque.asignatura,
                'codigo': bloque.sala or 'Horario personal', 'sala': bloque.sala, 'docente': bloque.docente,
                'inicio': bloque.hora_inicio, 'fin': bloque.hora_fin,
                'bloques': [{'inicio': bloque.hora_inicio, 'fin': bloque.hora_fin}],
            })
            fecha += timedelta(days=7)
    for clases in resultado.values():
        clases.sort(key=lambda b: (b['inicio'], b['asignatura']))
    return resultado
