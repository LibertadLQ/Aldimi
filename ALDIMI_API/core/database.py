import os, json
from typing import Optional

DB_JSON = os.environ.get('ALDIMI_DB_JSON', os.path.join(os.getcwd(), 'ALDIMI_API', 'data', 'aldimi_pacientes.json'))
os.makedirs(os.path.dirname(DB_JSON), exist_ok=True)

def _load_all():
    if not os.path.exists(DB_JSON):
        return {}
    try:
        with open(DB_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_all(d):
    with open(DB_JSON, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def save_record(record: dict):
    d = _load_all()
    ciu = record.get('ciu') or record.get('metadata', {}).get('ciu')
    if not ciu:
        # assign random id
        import uuid
        ciu = str(uuid.uuid4())
        record['ciu'] = ciu
    d[ciu] = record
    _save_all(d)
    return DB_JSON

def load_record(ciu: str) -> Optional[dict]:
    d = _load_all()
    return d.get(ciu)
