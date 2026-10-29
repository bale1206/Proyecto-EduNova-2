"""Panel privado; una URL oculta NUNCA sustituye los permisos del servidor."""
import csv
import hashlib
from io import StringIO
import os
from pathlib import Path
import re
import secrets
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .importacion_archivos import leer_malla, leer_oferta, normalizar
from .importacion_servicio import aplicar_malla, aplicar_oferta, resolver_mapeo
from .models import Carrera, MencionCarrera, ImportacionAcademica

MAX_MB = 12
PENDIENTE_SEGUNDOS = 60 * 60


def _root():
    raiz = Path(settings.BASE_DIR) / 'private_imports'
    raiz.mkdir(mode=0o700, parents=True, exist_ok=True)
    return raiz


def _administrador(u):
    return u.is_authenticated and u.is_active and u.is_staff and u.is_superuser


def _leer_archivo_post(archivo):
    if archivo.size > MAX_MB * 1024 * 1024:
        raise ValueError('El archivo supera el máximo de 12 MB.')
    extension = Path(archivo.name.replace('\\','/')).suffix.lower()
    if extension not in ('.csv', '.xlsx', '.pdf'):
        raise ValueError('Formato no permitido. Utiliza CSV, XLSX o PDF para mallas.')
    datos = archivo.read()
    if not datos:
        raise ValueError('El archivo está vacío.')
    if extension == '.pdf' and not datos.startswith(b'%PDF-'):
        raise ValueError('El documento no parece un PDF válido.')
    if extension == '.xlsx' and not datos.startswith(b'PK'):
        raise ValueError('El archivo no parece un Excel .xlsx válido.')
    return extension, datos


def _guardar_temporal(datos, ext):
    # Limpieza oportunista de vistas previas vencidas, exclusivamente archivos temporales.
    for pendiente in _root().glob('pendiente_*'):
        try:
            if pendiente.is_file() and time.time() - pendiente.stat().st_mtime > 2*PENDIENTE_SEGUNDOS:
                pendiente.unlink()
        except OSError:
            pass
    token = secrets.token_hex(16)
    nombre = 'pendiente_' + token + ext
    ruta = _root() / nombre
    descriptor = os.open(str(ruta), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as archivo:
        archivo.write(datos)
    return token


def _obtener_pendiente(request):
    info = request.session.get('edunova_importacion_academica')
    if not info or not isinstance(info, dict):
        raise ValidationError('No hay una importación pendiente. Selecciona un archivo nuevamente.')
    token = info.get('token', '')
    extension = info.get('ext', '')
    if not re.fullmatch('[0-9a-f]{32}', token) or extension not in ('.pdf','.csv','.xlsx'):
        raise ValidationError('El identificador de importación no es válido.')
    if time.time() - info.get('creado', 0) > PENDIENTE_SEGUNDOS:
        raise ValidationError('La vista previa expiró. Sube el documento nuevamente.')
    ruta = _root() / ('pendiente_'+token+extension)
    try:
        datos = ruta.read_bytes()
    except OSError as exc:
        raise ValidationError('El archivo temporal ya no está disponible.') from exc
    if hashlib.sha256(datos).hexdigest() != info.get('sha256'):
        raise ValidationError('El archivo temporal cambió. Debes cargarlo nuevamente.')
    return info, datos, ruta


def _menciones_por_carrera(carrera_id):
    return list(MencionCarrera.objects.filter(carrera_id=carrera_id, activa=True).order_by('nombre'))


def _previsualizar(datos, nombre, tipo):
    if tipo == 'malla' and nombre.lower().endswith('.pdf'):
        return {'pdf': True, 'errores': [], 'total': 0}
    if tipo == 'malla':
        return leer_malla(datos, nombre)
    if tipo == 'oferta' and nombre.lower().endswith('.pdf'):
        raise ValueError('Para la oferta académica utiliza el Excel o CSV oficial, no PDF.')
    if tipo == 'oferta':
        return leer_oferta(datos, nombre)
    raise ValueError('Tipo de importación desconocido.')


def _contexto(request, preview=None, info=None):
    carreras = list(Carrera.objects.filter(activa=True).order_by('escuela', 'nombre'))
    ctx = {
        'carreras': carreras,
        'escuelas': sorted({c.escuela for c in carreras if c.escuela}),
        'menciones': list(MencionCarrera.objects.filter(activa=True).select_related('carrera').order_by('carrera__nombre','nombre')),
        'historial': ImportacionAcademica.objects.select_related('usuario').all()[:12],
        'preview': preview,
        'info': info,
        'carreras_archivo': [],
    }
    if preview and info and info['tipo'] == 'oferta' and not preview['errores']:
        for n, cantidad in sorted(preview['carreras'].items()):
            # Solo coincidencia exacta después de normalización, nunca fuzzy automático.
            sugerida = next((c.pk for c in carreras if normalizar(c.nombre)==normalizar(n)), None)
            clave = hashlib.sha256(n.encode('utf-8')).hexdigest()[:16]
            intento = request.method == 'POST' and request.POST.get('accion') == 'aplicar'
            ctx['carreras_archivo'].append({
                'nombre': n, 'cantidad': cantidad, 'clave': clave,
                'seleccion': request.POST.get('map_'+clave, '') if intento else (str(sugerida) if sugerida else ''),
                'nombre_nuevo': request.POST.get('nuevo_nombre_'+clave, n) if intento else n,
                'escuela_nueva': request.POST.get('nueva_escuela_'+clave, '') if intento else '',
            })
    return ctx


@user_passes_test(_administrador, login_url='/admin/login/')
@require_http_methods(['GET','POST'])
def panel_importaciones(request):
    """Acceso /admin/importaciones-academicas/ solo superusuarios."""
    preview, info = None, None
    if request.method == 'POST':
        accion = request.POST.get('accion')
        try:
            if accion == 'previsualizar':
                archivo = request.FILES.get('archivo')
                if not archivo:
                    raise ValidationError('Selecciona un documento.')
                tipo = request.POST.get('tipo')
                if tipo not in ('malla','oferta'):
                    raise ValidationError('Selecciona un tipo de documento.')
                ext, datos = _leer_archivo_post(archivo)
                nombre = Path(archivo.name.replace('\\','/')).name[:240]
                preview = _previsualizar(datos, nombre, tipo)
                meta = {'tipo':tipo, 'anio':request.POST.get('anio',''),
                        'semestre':request.POST.get('semestre',''),
                        'carrera':request.POST.get('carrera',''),
                        'mencion':request.POST.get('mencion',''),
                        'ingreso':request.POST.get('ingreso','')}
                if tipo=='malla':
                    carrera = Carrera.objects.filter(pk=meta['carrera'], activa=True).first() if meta['carrera'].isdecimal() else None
                    if not carrera:
                        raise ValidationError('Para una malla debes seleccionar una carrera existente.')
                    if meta['mencion']:
                        if not meta['mencion'].isdecimal() or not MencionCarrera.objects.filter(pk=meta['mencion'], carrera=carrera, activa=True).exists():
                            raise ValidationError('La mención debe pertenecer a la carrera seleccionada.')
                    if not meta['ingreso'].isdigit() or not 2000 <= int(meta['ingreso']) <= 2100:
                        raise ValidationError('Indica el año de ingreso de la malla (p. ej. 2026).')
                else:
                    if not meta['anio'].isdigit() or not 2000 <= int(meta['anio']) <= 2100 or meta['semestre'] not in ('1','2'):
                        raise ValidationError('Selecciona año y semestre de la oferta.')
                token = _guardar_temporal(datos, ext)
                request.session['edunova_importacion_academica'] = {
                    **meta, 'token':token, 'ext':ext, 'nombre':nombre,
                    'creado':time.time(), 'sha256':hashlib.sha256(datos).hexdigest(),
                }
                info = request.session['edunova_importacion_academica']
                if preview.get('errores'):
                    messages.error(request, 'El documento tiene errores. Corrígelos antes de confirmar.')
                elif preview.get('pdf'):
                    messages.warning(request, 'PDF de malla: se archivará como referencia, sin extraer asignaturas automáticamente. Para poblar el catálogo usa la plantilla CSV o XLSX.')
                else:
                    messages.info(request, 'Vista previa lista. Revisa los datos y confirma explícitamente antes de guardar.')
            elif accion == 'aplicar':
                if request.POST.get('confirmado') != 'si':
                    raise ValidationError('Debes confirmar expresamente la aplicación de los cambios.')
                info, datos, ruta = _obtener_pendiente(request)
                preview = _previsualizar(datos, info['nombre'], info['tipo'])
                if preview['errores']:
                    raise ValidationError('El documento tiene errores; súbelo corregido.')
                with transaction.atomic():
                    if info['tipo'] == 'malla':
                        carrera = get_object_or_404(Carrera, pk=info['carrera'], activa=True)
                        mencion = get_object_or_404(MencionCarrera, pk=info['mencion'], carrera=carrera, activa=True) if info['mencion'] else None
                        resultado = ({'nota': 'PDF de referencia pendiente de transcripción; no se actualizaron asignaturas.'}
                                     if preview.get('pdf') else
                                     aplicar_malla(preview, carrera, mencion, int(info['ingreso'])))
                        estado = 'pendiente' if preview.get('pdf') else 'aplicada'
                    else:
                        asignacion = {}
                        nuevas = {}
                        for n in preview['carreras']:
                            clave = hashlib.sha256(n.encode('utf-8')).hexdigest()[:16]
                            asignacion[n] = request.POST.get('map_'+clave, '')
                            if asignacion[n] == '__crear__':
                                nuevas[n] = {
                                    'nombre': request.POST.get('nuevo_nombre_'+clave, ''),
                                    'escuela': request.POST.get('nueva_escuela_'+clave, ''),
                                }
                        omitidas = {n for n, opcion in asignacion.items() if not opcion}
                        if omitidas and request.POST.get('confirmar_omisiones') != 'si':
                            raise ValidationError('Hay carreras sin asociar. Marca la confirmación de omisiones o asígnalas todas.')
                        mapeo, carreras_nuevas = resolver_mapeo(preview, asignacion, nuevas)
                        resultado = aplicar_oferta(preview, int(info['anio']), int(info['semestre']), mapeo)
                        resultado['carreras_nuevas'] = carreras_nuevas
                        resultado['nombres_carreras_nuevas'] = [mapeo[n].nombre for n, opcion in asignacion.items() if opcion == '__crear__']
                        estado = 'aplicada'
                    nombre_guardado = secrets.token_hex(16) + info['ext']
                    archivo_respaldo = _root() / nombre_guardado
                    os.replace(ruta, archivo_respaldo)
                    ImportacionAcademica.objects.create(
                        tipo=info['tipo'], estado=estado, archivo_nombre=info['nombre'],
                        archivo_privado=nombre_guardado, sha256=info['sha256'],
                        usuario=request.user, resumen=resultado)
                request.session.pop('edunova_importacion_academica', None)
                messages.success(request, 'Documento procesado. Consulta el historial para ver las cifras y advertencias.')
                return redirect('edunova_importaciones_admin')
            elif accion == 'cancelar':
                request.session.pop('edunova_importacion_academica', None)
                messages.info(request, 'Se canceló la importación pendiente.')
                return redirect('edunova_importaciones_admin')
            else:
                raise ValidationError('Acción de importación no reconocida.')
        except (ValueError, ValidationError) as exc:
            message = '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)
            messages.error(request, message)
            if info and not preview:
                try:
                    preview = _previsualizar(datos, info['nombre'], info['tipo'])
                except (ValueError,ValidationError):
                    pass
    return render(request, 'academico/importacion_admin.html', _contexto(request, preview, info))


@user_passes_test(_administrador, login_url='/admin/login/')
def plantilla_malla(request):
    s = StringIO()
    writer = csv.writer(s, delimiter=';')
    writer.writerow(['codigo_asignatura','nombre_asignatura','anio_curricular','semestre_curricular'])
    writer.writerow(['IPR1001','Fundamentos de Programación','1','1'])
    response = HttpResponse('\ufeff'+s.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_malla_edunova.csv"'
    return response


@user_passes_test(_administrador, login_url='/admin/login/')
def descargar_archivo_importado(request, pk):
    registro = get_object_or_404(ImportacionAcademica, pk=pk)
    nombre = registro.archivo_privado
    if not re.fullmatch(r'[0-9a-f]{32}\.(pdf|csv|xlsx)', nombre or ''):
        raise Http404
    archivo = _root() / nombre
    if not archivo.is_file():
        raise Http404
    return FileResponse(archivo.open('rb'), as_attachment=True, filename=registro.archivo_nombre)
