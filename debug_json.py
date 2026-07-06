from pathlib import Path
import json

p = Path('ALDIMI_DB/aldimi_pacientes.json')
raw = p.read_text(encoding='utf-8')
print('raw_len', len(raw))
print('tail_repr', repr(raw[-80:]))
try:
    json.loads(raw)
    print('loads ok')
except json.JSONDecodeError as e:
    print('json.loads fail', e)
    decoder = json.JSONDecoder()
    obj, idx = decoder.raw_decode(raw)
    print('idx', idx)
    resto = raw[idx:]
    print('rest repr', repr(resto[:80]))
    print('rest stripped repr', repr(resto.strip().strip('\x00')))
    print('rest empty?', resto.strip().strip('\x00') == '')
    print(type(obj))
    print(obj.keys())
