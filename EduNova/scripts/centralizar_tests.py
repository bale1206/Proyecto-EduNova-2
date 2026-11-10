#!/usr/bin/env python3
"""Previsualiza o elimina pruebas antiguas tras copiarlas a tests/.

Por seguridad, comprueba hashes y crea una copia ZIP de los originales.
No cambia bases de datos ni ficheros de producción.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
import argparse, hashlib, json, sys

root=Path(__file__).resolve().parents[1]
manifest=root/'MANIFIESTO_PRUEBAS.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description='Centralizar pruebas de EduNova (modo lectura por defecto).')
    p.add_argument('--aplicar',action='store_true',help='Respalda y retira los originales de las aplicaciones.')
    args=p.parse_args()
    if not manifest.is_file():
        sys.exit('ERROR: falta MANIFIESTO_PRUEBAS.json. Ejecuta desde una instalación completa del ZIP.')
    entries=json.loads(manifest.read_text(encoding='utf8'))['app_files']
    errors=[]; existing=[]
    covered={item['origen'] for item in entries}
    for app in ('usuarios','academico','comunicacion'):
        for found in sorted((root/app).glob('test*.py')):
            if found.relative_to(root).as_posix() not in covered:
                errors.append(f'Prueba nueva no incluida en el paquete: {found.relative_to(root)}')
    for item in entries:
        src=root/item['origen']
        dst=root/item['destino'] if item['destino'] else None
        if dst and (not dst.exists() or sha(dst.read_bytes()) != item['sha_destino']):
            errors.append(f'Archivo centralizado ausente/modificado: {item["destino"]}')
        if src.exists():
            if sha(src.read_bytes()) != item['sha_origen']:
                errors.append(f'El original fue modificado; no se eliminará automáticamente: {item["origen"]}')
            else: existing.append(src)
    if errors:
        for e in errors:print('ERROR:',e)
        sys.exit('Se detuvo para evitar pérdida de cambios. Revisa las rutas antes de mover pruebas.')
    print(f'{len(existing)} archivos originales identificados para retirar. Archivos centrales verificados.')
    for path in existing:print(' -',path.relative_to(root))
    if not args.aplicar:
        print('SIMULACIÓN: no se cambió ningún archivo. Para ejecutar: python scripts/centralizar_tests.py --aplicar')
        return
    if not existing:
        print('No hay pruebas antiguas que retirar. Todo centralizado.');return
    backup=root/('RESPALDO_tests_originales_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
    with ZipFile(backup,'x',ZIP_DEFLATED) as z:
        for path in existing:z.write(path,path.relative_to(root).as_posix())
    with ZipFile(backup) as z:
        assert len(z.namelist())==len(existing)
    print('Respaldo creado:',backup)
    for path in existing:path.unlink()
    print('Pruebas anteriores retiradas. Listo: ejecutar python manage.py test tests (solo base de pruebas).')

if __name__ == '__main__':main()
