import os
import json
import hashlib
import datetime
from typing import Optional, Dict, Any

USERS_JSON = os.environ.get(
    'ALDIMI_USERS_JSON',
    os.path.join(os.getcwd(), 'ALDIMI_API', 'data', 'aldimi_users.json')
)
os.makedirs(os.path.dirname(USERS_JSON), exist_ok=True)

VALID_ROLES = {'admin', 'medico', 'enfermero', 'psicologo', 'usuario'}
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'Medico2024!'


def _load_users() -> Dict[str, Any]:
    if not os.path.exists(USERS_JSON):
        return {}
    try:
        with open(USERS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users: Dict[str, Any]) -> bool:
    try:
        with open(USERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _verify_pw(password: str, hashed: str) -> bool:
    return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed


def _seed_default_admin(users: Dict[str, Any]) -> Dict[str, Any]:
    if not users:
        users[DEFAULT_ADMIN_USERNAME] = {
            'hashed_pw': _hash_pw(DEFAULT_ADMIN_PASSWORD),
            'role': 'admin',
            'activo': True,
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': None,
        }
        _save_users(users)
    return users


def create_user(admin: Optional[str], username: str, password: str, role: str) -> Dict[str, Any]:
    users = _load_users()
    if not users:
        if role != 'admin':
            return {'error': 'Primero debe crearse un usuario admin.'}
        users[username] = {
            'hashed_pw': _hash_pw(password),
            'role': 'admin',
            'activo': True,
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': None,
        }
        _save_users(users)
        return {'username': username, 'role': 'admin', 'activo': True}
    if admin is None:
        return {'error': 'Se requiere nombre de admin para crear usuarios.'}
    if username in users:
        return {'error': f'Usuario {username} ya existe.'}
    if role not in VALID_ROLES:
        return {'error': f'Rol inválido: {role}. Roles válidos: {sorted(VALID_ROLES)}'}
    if len(password) < 8:
        return {'error': 'Contraseña: mínimo 8 caracteres.'}
    if admin not in users or users[admin]['role'] != 'admin':
        return {'error': f'Admin inválido o sin permisos: {admin}'}
    users[username] = {
        'hashed_pw': _hash_pw(password),
        'role': role,
        'activo': True,
        'created_at': datetime.datetime.now().isoformat(),
        'updated_at': None,
    }
    _save_users(users)
    return {'username': username, 'role': role, 'activo': True}


def authenticate_user(username: str, password: str) -> Dict[str, Any]:
    users = _load_users()
    if username not in users:
        return {'error': 'Usuario no encontrado.'}
    user = users[username]
    if not user.get('activo', False):
        return {'error': 'Cuenta desactivada.'}
    if not _verify_pw(password, user.get('hashed_pw', '')):
        return {'error': 'Contraseña incorrecta.'}
    return {'username': username, 'role': user.get('role'), 'status': 'autenticado'}


def update_user(admin: str, username: str, new_role: Optional[str] = None, activo: Optional[bool] = None) -> Dict[str, Any]:
    users = _load_users()
    if admin not in users or users[admin].get('role') != 'admin':
        return {'error': 'Solo admins pueden modificar usuarios.'}
    if username not in users:
        return {'error': f'Usuario {username} no encontrado.'}
    if new_role is not None and new_role not in VALID_ROLES:
        return {'error': f'Rol inválido: {new_role}. Roles válidos: {sorted(VALID_ROLES)}'}
    if new_role is not None:
        users[username]['role'] = new_role
    if activo is not None:
        users[username]['activo'] = activo
    users[username]['updated_at'] = datetime.datetime.now().isoformat()
    _save_users(users)
    result = {'username': username}
    if new_role is not None:
        result['role'] = new_role
    if activo is not None:
        result['activo'] = activo
    return result


def get_user(username: str) -> Optional[Dict[str, Any]]:
    return _load_users().get(username)


def list_users() -> Dict[str, Any]:
    return _load_users()
