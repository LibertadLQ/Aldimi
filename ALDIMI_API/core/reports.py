import os
import json
import datetime
from typing import Any, Dict, List
from .chatbot import analizar_sentimiento, detect_risk_language

REPORTS_JSON = os.environ.get(
    'ALDIMI_REPORTS_JSON',
    os.path.join(os.getcwd(), 'ALDIMI_API', 'data', 'aldimi_reports.json')
)
os.makedirs(os.path.dirname(REPORTS_JSON), exist_ok=True)


def _load_reports() -> Dict[str, Any]:
    if not os.path.exists(REPORTS_JSON):
        return {'alerts': [], 'daily_reports': []}
    try:
        with open(REPORTS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                'alerts': data.get('alerts', []),
                'daily_reports': data.get('daily_reports', []),
            }
    except Exception:
        return {'alerts': [], 'daily_reports': []}


def _save_reports(data: Dict[str, Any]) -> bool:
    try:
        with open(REPORTS_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def register_daily_report(patient_id: str, medical_data: Dict[str, Any], emotional_note: str) -> Dict[str, Any]:
    required = ['presion', 'temperatura', 'peso']
    missing = [field for field in required if field not in medical_data]
    if missing:
        return {'error': f'Campos faltantes: {missing}'}
    data = _load_reports()
    reports = data.setdefault('daily_reports', [])
    alerts = data.setdefault('alerts', [])
    report_id = f'RPT-{len(reports) + 1:04d}'
    sentimiento = analizar_sentimiento(emotional_note)
    report = {
        'report_id': report_id,
        'patient_id': patient_id,
        'datos_medicos': medical_data,
        'nota_emocional': emotional_note,
        'sentimiento': sentimiento,
        'timestamp': datetime.datetime.now().isoformat(),
        'alerta': None,
    }
    if detect_risk_language(emotional_note):
        alert = {
            'alert_id': f'ALT-{len(alerts) + 1:04d}',
            'patient_id': patient_id,
            'tipo': 'PSICOSOCIAL',
            'reason': f'Riesgo en nota: "{str(emotional_note)[:60]}"',
            'timestamp': datetime.datetime.now().isoformat(),
            'status': 'pendiente',
        }
        alerts.append(alert)
        report['alerta'] = alert['alert_id']
    reports.append(report)
    _save_reports(data)
    return report


def get_pending_alerts() -> List[Dict[str, Any]]:
    data = _load_reports()
    return [alert for alert in data.get('alerts', []) if alert.get('status') == 'pendiente']


def get_reports_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    data = _load_reports()
    return [report for report in data.get('daily_reports', []) if report.get('patient_id') == patient_id]
