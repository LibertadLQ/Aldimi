# diag_ocr.py - diagnóstico: detecta tesseract, activa debug y procesa muestras
from pathlib import Path
import importlib
import shutil
import json
import os

print('Working dir:', Path.cwd())

# Detect Tesseract default install on Windows and export for pytesseract
default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(default_tess):
    os.environ.setdefault('TESSERACT_CMD', default_tess)
    print('Found Tesseract at', default_tess, '- setting TESSERACT_CMD')
else:
    print('Tesseract not found at default path; leave TESSERACT_CMD unset')

# Enable verbose OCR debug
os.environ.setdefault('ALDIMI_DEBUG_OCR', '1')

ocr = importlib.import_module('backend.ocr_robusto')
print('_TESSERACT_OK=', getattr(ocr, '_TESSERACT_OK', None))
print('_EASYOCR_OK=', getattr(ocr, '_EASYOCR_OK', None))
from backend import storage
print('DB_PATH=', storage.DB_PATH)
print('DNI_DIR=', storage.DNI_DIR)
print('LAB_DIR=', storage.LAB_DIR)
root = Path.cwd()
# ensure test.png exists
if not (root / 'test.png').exists():
    try:
        from PIL import Image
        Image.new('RGB', (100, 60), 'white').save(root / 'test.png')
        print('Created test.png')
    except Exception as e:
        print('Could not create test.png:', e)


def list_files(p):
    if not p.exists():
        print(f'{p} does not exist')
        return []
    files = [f for f in p.iterdir() if f.is_file()]
    print(f'{p} -> {len(files)} files')
    for f in files[:20]:
        print('  -', f.name)
    return files


dni_files = list_files(storage.DNI_DIR)
lab_files = list_files(storage.LAB_DIR)

if not dni_files:
    dest = storage.DNI_DIR / 'sample_dni.png'
    shutil.copy2(root / 'test.png', dest)
    print('Copied test.png to', dest)
    dni_files = [dest]
if not lab_files:
    dest2 = storage.LAB_DIR / 'sample_lab.png'
    shutil.copy2(root / 'test.png', dest2)
    print('Copied test.png to', dest2)
    lab_files = [dest2]

print('\nProcessing DNI file:')
try:
    r = ocr.procesar_documento(str(dni_files[0]))
    print(json.dumps(r, indent=2, ensure_ascii=False))
except Exception as e:
    print('Error procesar_documento DNI:', e)

print('\nProcessing LAB file:')
try:
    r2 = ocr.procesar_documento(str(lab_files[0]))
    print(json.dumps(r2, indent=2, ensure_ascii=False))
except Exception as e:
    print('Error procesar_documento LAB:', e)
