#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostico_lab_parser.py — Analiza imágenes de dos carpetas:
  - informes con datos numericos
  - informes sin datos numericos

Extrae texto OCR y lo procesa con el parser actual para identificar problemas.
"""

import os
import sys
from pathlib import Path

# Agregar backend al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent))

from backend.ocr_robusto import extraer_texto_ocr, procesar_lab, predict_document_cnn

def diagnosticar_carpeta(carpeta_path: str, tipo: str) -> None:
    """Procesa todas las imágenes en una carpeta y reporta resultados."""
    carpeta = Path(carpeta_path)
    if not carpeta.exists():
        print(f"[ERROR] Carpeta no existe: {carpeta_path}")
        return
    
    imagenes = sorted([p for p in carpeta.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
    if not imagenes:
        print(f"[WARN] Sin imágenes en: {carpeta_path}")
        return
    
    print(f"\n{'='*80}")
    print(f"[DIAGNOSTICO] {tipo.upper()}")
    print(f"{'='*80}")
    print(f"Carpeta: {carpeta_path}")
    print(f"Imágenes encontradas: {len(imagenes)}\n")
    
    for idx, img_path in enumerate(imagenes[:3], 1):  # Procesar máximo 3 por carpeta
        print(f"\n{'-'*80}")
        print(f"[{idx}] Imagen: {img_path.name}")
        print(f"{'-'*80}")
        
        # Extraer texto OCR
        print("[OCR] Extrayendo texto...")
        texto = extraer_texto_ocr(str(img_path))
        if not texto:
            print("[ERROR] OCR no devolvió texto")
            continue
        
        print(f"[OK] Texto extraído ({len(texto)} caracteres)")
        print(f"\nPrimeras 500 caracteres:\n{texto[:500]}\n")
        
        # Procesar como informe de laboratorio
        print("[LAB] Procesando como LAB_REPORT...")
        try:
            resultado = procesar_lab(texto)
            
            ciu = resultado.get('ciu', 'NO_DETECTADO')
            pruebas = resultado.get('pruebas', [])
            alertas = resultado.get('alertas_detectadas', [])
            
            print(f"[OK] CIU detectado: {ciu}")
            print(f"[OK] Pruebas extraídas: {len(pruebas)}")
            print(f"[OK] Alertas detectadas: {len(alertas)}")
            
            if pruebas:
                print(f"\n[PRUEBAS] Primeras 5 pruebas:")
                for i, p in enumerate(pruebas[:5], 1):
                    nombre = p.get('nombre', 'SIN_NOMBRE')
                    valor = p.get('valor', '?')
                    unidad = p.get('unidad', '')
                    flag = p.get('flag', '')
                    ref = p.get('referencia', '')
                    
                    print(f"  {i}. {nombre}")
                    print(f"     Valor: {valor} {unidad}")
                    print(f"     Flag: {flag if flag else '(sin flag)'}")
                    print(f"     Ref: {ref if ref else '(sin referencia)'}")
            
            if alertas:
                print(f"\n[ALERTAS] Detectadas:")
                for a in alertas[:5]:
                    print(f"  * {a.get('prueba', '?')}: {a.get('tipo', '?')} ({a.get('valor', '?')})")
        
        except Exception as e:
            print(f"[ERROR] Al procesar: {e}")
            import traceback
            traceback.print_exc()

def main() -> None:
    """Punto de entrada."""
    ruta_desktop = Path.home() / "Desktop" / "imagenes generales de LAB_ALDIMI"
    
    if not ruta_desktop.exists():
        print(f"[ERROR] Carpeta no existe: {ruta_desktop}")
        return
    
    carpeta_numericos = ruta_desktop / "informes con datos numericos"
    carpeta_texto = ruta_desktop / "informes sin datos numericos"
    
    diagnosticar_carpeta(str(carpeta_numericos), "Informes CON datos numéricos")
    diagnosticar_carpeta(str(carpeta_texto), "Informes SIN datos numéricos (texto)")
    
    print(f"\n{'='*80}")
    print("[DIAGNOSTICO] Completado")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
