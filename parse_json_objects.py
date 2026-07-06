from pathlib import Path
import json

p = Path('ALDIMI_DB/aldimi_pacientes.json.bak')
text = p.read_text(encoding='utf-8')
print('total len', len(text))
idx = 0
decoder = json.JSONDecoder()
count = 0
objects = []
while idx < len(text):
    while idx < len(text) and text[idx] in ('\x00', '\ufeff', '\n', '\r', '\t', ' ', '\v', '\f'):
        idx += 1
    if idx >= len(text):
        break
    try:
        obj, end = decoder.raw_decode(text[idx:])
    except json.JSONDecodeError as e:
        print('json decode fail at idx', idx, e)
        break
    count += 1
    obj_len = end
    objects.append((idx, obj_len, obj))
    print('object', count, 'start', idx, 'parsed len', obj_len)
    if isinstance(obj, dict):
        print('  keys', list(obj.keys()))
        if 'pacientes' in obj and isinstance(obj['pacientes'], dict):
            print('  pacientes len', len(obj['pacientes']))
            sample = list(obj['pacientes'].keys())[:10]
            print('  sample keys', sample)
    idx += obj_len
print('total objects', count)
for i, (start, length, obj) in enumerate(objects, start=1):
    print(i, 'start', start, 'len', length, 'has pacientes', isinstance(obj, dict) and 'pacientes' in obj)
