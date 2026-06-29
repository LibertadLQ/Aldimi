from fastapi.testclient import TestClient
from ALDIMI_API.main import app

client = TestClient(app)


def test_root():
    r = client.get('/')
    assert r.status_code == 200
    assert r.json().get('ok') is True
    assert 'routes' in r.json()


def test_chat_endpoint():
    r = client.post('/chat', json={'message': '¿Cuál es el horario?'})
    assert r.status_code == 200
    assert r.json().get('intent') == 'HORARIO'


def test_cnn_prediction_with_text():
    r = client.post('/cnn', json={'texto': 'Hemoglobina 13.5 g/dl'})
    assert r.status_code == 200
    assert r.json().get('clase_predicha') == 'LAB_REPORT'


def test_user_auth_and_create():
    # Create a default admin if needed, then create a new user
    admin_login = client.post('/auth', json={'username': 'admin', 'password': 'Medico2024!'})
    assert admin_login.status_code in (200, 400)
    if admin_login.status_code == 200:
        r = client.post('/users', json={'admin': 'admin', 'username': 'testuser', 'password': 'Password123', 'role': 'usuario'})
        assert r.status_code == 200
        assert r.json().get('username') == 'testuser'


def test_report_and_alerts():
    payload = {
        'patient_id': '42951703',
        'medical_data': {'presion': '120/80', 'temperatura': '36.7', 'peso': '65'},
        'emotional_note': 'Estoy muy preocupado y algo triste',
    }
    r = client.post('/reports', json=payload)
    assert r.status_code == 200
    assert 'report_id' in r.json()
    alerts = client.get('/alerts/pending')
    assert alerts.status_code == 200
    assert 'pending_alerts' in alerts.json()
