#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_alert_detection.py — Prueba la detección de alertas desde referencias capturadas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.ocr_robusto import _detectar_alerta_por_rango, _parse_referencia, detectar_alertas

# Pruebas simples
pruebas_test = [
    {
        "nombre": "Sodio (Na)",
        "valor": 137.0,
        "unidad": "mmol/L",
        "flag": "",
        "referencia": "135.0-145.0",  # Dentro del rango
    },
    {
        "nombre": "Potasio (K)",
        "valor": 6.5,
        "unidad": "mmol/L",
        "flag": "",
        "referencia": "3.50-5.10",  # FUERA (alto)
    },
    {
        "nombre": "Glucosa",
        "valor": 250.0,
        "unidad": "mg/dL",
        "flag": "",
        "referencia": "70.0-140.0",  # FUERA (alto)
    },
    {
        "nombre": "Creatinina",
        "valor": 0.3,
        "unidad": "mg/dL",
        "flag": "",
        "referencia": "0.5-1.3",  # FUERA (bajo)
    },
]

print("[TEST] Probando detección de alertas desde referencias capturadas\n")

for prueba in pruebas_test:
    nombre = prueba["nombre"]
    valor = prueba["valor"]
    ref = prueba["referencia"]
    
    print(f"Prueba: {nombre}")
    print(f"  Valor: {valor}")
    print(f"  Referencia: {ref}")
    
    # Prueba _parse_referencia
    low, high = _parse_referencia(ref)
    print(f"  Parseado: low={low}, high={high}")
    
    # Prueba _detectar_alerta_por_rango
    tipo = _detectar_alerta_por_rango(prueba)
    print(f"  Alerta (por rango): {tipo}\n")

# Prueba el flujo completo
print("=" * 60)
print("[FLUJO COMPLETO] Llamar detectar_alertas()\n")

alertas = detectar_alertas(pruebas_test)
print(f"Alertas detectadas: {len(alertas)}\n")

for alerta in alertas:
    print(f"  • {alerta['prueba']}: {alerta['tipo']} (metodo={alerta.get('metodo')})")
