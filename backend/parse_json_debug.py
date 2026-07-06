from pathlib import Path
import json

p = Path('ALDIMI_DB/aldimi_pacientes.json.bak')
text = p.read_text('utf-8', errors='replace')
print('len', len(text))
print('--- boundary')
print(repr(text[3060:3085]))
idx = 3066
while idx < len(text) and text[idx] in (chr(0), '\n', '\r', '\t', ' ', chr(11), chr(12)):
    idx += 1
print('first non-null after 3066 at', idx, repr(text[idx:idx+20]))
print('--- head')
print(repr(text[idx:idx+200]))
print('--- tail around parser fail')
start = 125300
end = min(len(text), 125450)
print(repr(text[start:end]))
print('--- search positions')
for pat in ['{"sesion"', '"sesion"', '"pacientes"', '"campos"', '"499485"', '"ci"', '"apellidos"']:
    idx2 = text.find(pat)
    print(pat, idx2)
    if idx2 != -1:
        print('  snippet:', repr(text[idx2:idx2+80]))
print('--- search non-null block around tail')
for i in range(125300, 125500):
    if text[i] not in (chr(0), '\n', '\r', '\t', ' ', chr(11), chr(12)):
        print('first non-null in region', i, repr(text[i:i+80]))
        break
