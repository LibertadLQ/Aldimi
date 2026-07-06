from pathlib import Path
p = Path('ALDIMI_DB/aldimi_pacientes.json')
text = p.read_text('utf-8')
print(text[:400])
