# -*- coding: utf-8 -*-
"""
health_check.py — Verifica alertas clínicas previas al iniciar ALDIMI

Al arrancar el backend, escanea aldimi_pacientes.json y reporta:
- Total de pacientes
- Pacientes con alertas clínicas pendientes
- Alertas críticas (valores extremos)
"""

from pathlib import Path
from typing import Dict, Any, List
from .db import cargar_bd

def check_alertas_previas() -> Dict[str, Any]:
    """
    Escanea la BD de pacientes y reporta alertas clínicas pendientes.
    
    Retorna:
    {
        "timestamp": "2026-07-08T...",
        "total_pacientes": 150,
        "pacientes_con_alertas": 23,
        "alertas_criticas_count": 5,
        "resumen_por_tipo": {"BAJO": 12, "ALTO": 11},
        "alertas_top_5": [
            {"ciu": "42951703", "alerta": "Hemoglobina BAJO", "valor": 6.5}
        ]
    }
    """
    from datetime import datetime
    
    try:
        bd = cargar_bd()
    except Exception as e:
        print(f"[HEALTH_CHECK] Error al cargar BD: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    if not isinstance(bd, dict):
        return {"error": "BD inválida", "total_pacientes": 0}
    
    total_pacientes = len(bd)
    pacientes_con_alertas = 0
    alertas_criticas = []
    alertas_por_tipo = {}
    todas_alertas = []
    
    for ciu, registro in bd.items():
        if not isinstance(registro, dict):
            continue
        
        alertas = registro.get("alertas_clinicas", []) or []
        if alertas:
            pacientes_con_alertas += 1
            for alerta in alertas:
                if isinstance(alerta, dict):
                    tipo = alerta.get("tipo", "DESCONOCIDO")
                    alertas_por_tipo[tipo] = alertas_por_tipo.get(tipo, 0) + 1
                    
                    todas_alertas.append({
                        "ciu": ciu,
                        "alerta": f"{alerta.get('prueba', '?')} {tipo}",
                        "valor": alerta.get("valor"),
                        "critica": alerta.get("critica", False)
                    })
                    
                    if alerta.get("critica") or alerta.get("severidad") == "CRÍTICA":
                        alertas_criticas.append({
                            "ciu": ciu,
                            "prueba": alerta.get("prueba"),
                            "valor": alerta.get("valor"),
                            "tipo": tipo
                        })
    
    # Top 5 alertas más recientes
    alertas_top = todas_alertas[-5:] if todas_alertas else []
    
    resultado = {
        "timestamp": datetime.now().isoformat(),
        "total_pacientes": total_pacientes,
        "pacientes_con_alertas": pacientes_con_alertas,
        "alertas_totales": len(todas_alertas),
        "alertas_criticas": len(alertas_criticas),
        "resumen_por_tipo": alertas_por_tipo,
        "alertas_top_5": alertas_top,
        "alertas_criticas_lista": alertas_criticas[:10],  # Top 10 críticas
    }
    
    return resultado


def mostrar_resumen_alertas(reporte: Dict[str, Any]) -> str:
    """Formatea el reporte de alertas para mostrar en logs."""
    if "error" in reporte:
        return f"[HEALTH_CHECK] Error: {reporte['error']}"
    
    total = reporte.get("total_pacientes", 0)
    con_alertas = reporte.get("pacientes_con_alertas", 0)
    alertas_tot = reporte.get("alertas_totales", 0)
    criticas = reporte.get("alertas_criticas", 0)
    
    lineas = [
        "[HEALTH_CHECK] ════════════════════════════════════════",
        f"[HEALTH_CHECK] RESUMEN DE ALERTAS CLINICAS",
        f"[HEALTH_CHECK] Pacientes en BD: {total}",
        f"[HEALTH_CHECK] Pacientes CON alertas: {con_alertas} ({100*con_alertas/max(total,1):.1f}%)",
        f"[HEALTH_CHECK] Total de alertas: {alertas_tot}",
        f"[HEALTH_CHECK] Alertas CRITICAS: {criticas}",
    ]
    
    # Resumen por tipo
    tipos = reporte.get("resumen_por_tipo", {})
    if tipos:
        lineas.append(f"[HEALTH_CHECK] Por tipo: {tipos}")
    
    # Top alertas críticas
    criticas_lista = reporte.get("alertas_criticas_lista", [])
    if criticas_lista:
        lineas.append("[HEALTH_CHECK] TOP ALERTAS CRITICAS:")
        for i, alerta in enumerate(criticas_lista[:5], 1):
            lineas.append(
                f"[HEALTH_CHECK]   {i}. CIU {alerta['ciu']}: "
                f"{alerta['prueba']} = {alerta['valor']} ({alerta['tipo']})"
            )
    
    lineas.append("[HEALTH_CHECK] ════════════════════════════════════════")
    
    return "\n".join(lineas)


if __name__ == "__main__":
    reporte = check_alertas_previas()
    print(mostrar_resumen_alertas(reporte))
