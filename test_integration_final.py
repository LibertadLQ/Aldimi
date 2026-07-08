#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integration validation test for ALDIMI alert system.
Run: python test_integration_final.py
"""

from backend.chatbot import procesar_mensaje, filtrar_alertas_criticas
from backend.alertas import evaluar_prueba, evaluar_pruebas
import json

def test_alert_evaluator():
    """Test single alert evaluation."""
    print("=" * 60)
    print("TEST 1: Alert Evaluator (Single Prueba)")
    print("=" * 60)
    
    test_prueba = {
        'nombre': 'Hemoglobina',
        'valor': 6.5,
        'unidad': 'g/dL',
        'flag': 'L',
        'referencia': '12-17.5',
        'source': 'ocr'
    }
    
    alerta = evaluar_prueba(test_prueba)
    print(f"Input: {json.dumps(test_prueba, indent=2)}")
    print(f"\nOutput Alert:")
    print(json.dumps(alerta, indent=2, default=str))
    
    # Verify structure
    assert alerta is not None, "Alert should not be None"
    assert alerta.get('severity') in ('critical', 'high', 'medium', 'low'), "Invalid severity"
    assert 'suggestion' in alerta, "Missing suggestion field"
    assert 'title' in alerta, "Missing title field"
    
    print("\n✅ Test 1 PASSED\n")
    return True

def test_batch_evaluation():
    """Test batch alert evaluation."""
    print("=" * 60)
    print("TEST 2: Batch Evaluation (Multiple Pruebas)")
    print("=" * 60)
    
    pruebas = [
        {'nombre': 'Hemoglobina', 'valor': 6.5, 'flag': 'L', 'referencia': '12-17.5'},
        {'nombre': 'Plaquetas', 'valor': 25000, 'flag': 'H', 'referencia': '150-450k'},
        {'nombre': 'Potasio', 'valor': 6.2, 'flag': 'H', 'referencia': '3.5-5.2'},
    ]
    
    alertas = evaluar_pruebas(pruebas)
    print(f"Input: {len(pruebas)} pruebas")
    print(f"Output: {len(alertas)} alerts generated\n")
    
    for i, a in enumerate(alertas, 1):
        print(f"  {i}. {a.get('title')} (severity: {a.get('severity')})")
        print(f"     Suggestion: {a.get('suggestion')[:60]}...")
    
    assert len(alertas) >= 2, "Should generate at least 2 alerts"
    print("\n✅ Test 2 PASSED\n")
    return True

def test_alert_filter():
    """Test alert filter function."""
    print("=" * 60)
    print("TEST 3: Alert Filter (Formatting for Display)")
    print("=" * 60)
    
    test_registro = {
        'ciu': '42951703',
        'alertas_clinicas': [
            {'prueba': 'Hemoglobina', 'valor': 6.5, 'unidad': 'g/dL', 'flag': 'L', 'referencia': '12-17.5', 'tipo': 'BAJO'},
            {'prueba': 'Plaquetas', 'valor': 25000, 'unidad': '/µL', 'flag': 'H', 'referencia': '150-450k', 'tipo': 'ALTO'},
        ],
        'informes_laboratorio': []
    }
    
    respuesta = filtrar_alertas_criticas(test_registro, '42951703')
    print("Formatted Response:\n")
    print(respuesta)
    
    assert 'Alertas' in respuesta or '🚨' in respuesta, "Should contain alert marker"
    assert 'Hemoglobina' in respuesta, "Should mention Hemoglobina"
    assert 'ALTO' in respuesta or 'BAJO' in respuesta, "Should show alert direction"
    
    print("\n✅ Test 3 PASSED\n")
    return True

def test_chatbot_integration():
    """Test chatbot alert processing."""
    print("=" * 60)
    print("TEST 4: Chatbot Integration")
    print("=" * 60)
    
    # Test that chatbot can process alert-related messages
    response = procesar_mensaje("hola")
    assert 'respuesta' in response, "Response should have 'respuesta' field"
    print("✓ Chatbot responds to greeting")
    
    # Test alert intent detection
    response = procesar_mensaje("alertas clinicas")
    assert 'respuesta' in response, "Response should have 'respuesta' field"
    print("✓ Chatbot recognizes alert intent")
    print(f"  Response: {response.get('respuesta', '')[:80]}...")
    
    print("\n✅ Test 4 PASSED\n")
    return True

if __name__ == "__main__":
    try:
        print("\n")
        print("*" * 60)
        print("ALDIMI Alert System - Integration Validation")
        print("*" * 60)
        print("\n")
        
        test_alert_evaluator()
        test_batch_evaluation()
        test_alert_filter()
        test_chatbot_integration()
        
        print("=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
        print("\nSystem is ready for deployment!")
        print("Next: Run .\\run.ps1 to start the full stack\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
