from pathlib import Path

p = Path('ALDIMI_DB/aldimi_pacientes.json')
text = p.read_text(encoding='utf-8')
print('length', len(text))
print('starts with', repr(text[:120]))
print('contains pacientes', '"pacientes"' in text)
print('count 499485', text.count('"499485"'))
print('first 499485 index', text.find('"499485"'))
print('first patient key snippet', repr(text[text.find('"499485"')-40:text.find('"499485"')+40]))
print('end snippet', repr(text[-120:]))
