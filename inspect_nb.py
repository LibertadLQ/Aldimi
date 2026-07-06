import json
import os

nb_path = 'C:/Users/JUAN FELIPE/Desktop/ALDIMI_FINAL.ipynb'
if not os.path.exists(nb_path):
    print('NOTEBOOK_NOT_FOUND')
    raise SystemExit(0)
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)
for i, cell in enumerate(nb.get('cells', []), 1):
    src = ''.join(cell.get('source', []))
    lowered = src.lower()
    if any(x in lowered for x in ['cnn', 'grayscale', 'tesseract', 'easyocr', 'procesar_documento', 'extraer']):
        print('CELL', i, 'type', cell.get('cell_type'))
        print(src[:1000].replace('\n', '\\n'))
        print('---')
