"""Script de ayuda para ejecutar autoscan de forma controlada.
Llama a backend.ocr_robusto.autoscan_folders y muestra resumen.
"""
import sys
from pathlib import Path

# Asegurar que el root del proyecto esté en sys.path para poder importar 'backend'
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from backend import ocr_robusto as ocr
except Exception as e:
    print("ERROR: no se pudo importar backend.ocr_robusto:", e)
    raise

DNI = Path("DNI_ALDIMI")
LAB = Path("LAB_ALDIMI")
OUT = Path("backend") / "aldimi_pacientes.json"

print("Iniciando autoscan...\nDNI folder:", DNI.resolve(), "\nLAB folder:", LAB.resolve())
# Límite temporal: procesar 1 imagen por carpeta (ajustable)
res = ocr.autoscan_folders(str(DNI), str(LAB), str(OUT), max_images=1)

print("\n--- Autoscan resumen ---")
print(f"Timestamp: {res.get('timestamp')}")
print(f"DNI procesados: {res.get('dni_procesados')}")
print(f"LAB procesados: {res.get('lab_procesados')}")
print(f"Errores: {res.get('errores')}")
print(f"Pacientes detectados: {len(res.get('pacientes', {}))}")

if res.get('alertas'):
    print("Alertas:")
    for a in res['alertas'][:10]:
        print('-', a)

print('\nSalida guardada en', OUT)

# Exit non-zero if errors
if res.get('errores', 0) > 0:
    sys.exit(1)
