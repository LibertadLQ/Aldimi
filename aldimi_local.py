# -*- coding: utf-8 -*-
"""
aldimi_local.py — Ejecutor local de ALDIMI

Versión Python del notebook ALDIMI_Core_AI.ipynb.
Proporciona funciones para:
- Escaneo de carpetas locales (DNI_ALDIMI, LAB_ALDIMI)
- Consulta de expedientes
- Gestión de persistencia

Uso:
    python aldimi_local.py
    from aldimi_local import ejecutar_local_scan, consultar_expediente
"""

import sys
from pathlib import Path

# Setup paths
ROOT = Path.cwd().resolve()
BACKEND_PATH = ROOT / 'backend'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

print(f'ALDIMI ROOT: {ROOT}')
print(f'Backend path agregado: {BACKEND_PATH}')

# Import backend modules
from backend.expediente import sincronizar_carpetas
from backend.db import cargar_bd

print('Módulos disponibles: sincronizar_carpetas, cargar_bd')


def ejecutar_local_scan(max_images: int = 0) -> dict:
    """Escanea DNI_ALDIMI y LAB_ALDIMI localmente."""
    resultado = sincronizar_carpetas(max_images=max_images)
    print(f'Escaneo local completado: {resultado["procesados"]} imágenes procesadas')
    return resultado


def consultar_expediente(ciu: str) -> dict:
    """Carga expediente de un paciente."""
    ciu = str(ciu).strip().upper()
    bd = cargar_bd()
    registro = bd.get(ciu)
    if registro is None:
        print(f'No encontrado: {ciu}')
        return None
    else:
        print(f'Expediente {ciu}:')
        print(registro)
    return registro


def listar_todos_pacientes() -> dict:
    """Lista todos los pacientes en la base de datos."""
    bd = cargar_bd()
    print(f'Total pacientes: {len(bd)}')
    return bd


def main():
    """Función principal para ejecución directa."""
    print("\n=== ALDIMI Local Executor ===\n")
    print("Opciones disponibles:")
    print("1. Escanear carpetas locales")
    print("2. Consultar expediente")
    print("3. Listar todos los pacientes")
    print("4. Salir")
    
    while True:
        opcion = input("\nSelecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            max_img = input("¿Máximo de imágenes por carpeta? (0 = sin límite): ").strip()
            try:
                max_images = int(max_img) if max_img else 0
            except ValueError:
                max_images = 0
            ejecutar_local_scan(max_images=max_images)
        
        elif opcion == "2":
            ciu = input("Ingresa el CIU del paciente: ").strip()
            consultar_expediente(ciu)
        
        elif opcion == "3":
            listar_todos_pacientes()
        
        elif opcion == "4":
            print("Saliendo...")
            break
        
        else:
            print("Opción no válida")


if __name__ == "__main__":
    main()
