from pathlib import Path
from backend import ocr_robusto as ocr

p = Path('DNI_ALDIMI')
files = sorted([x for x in p.glob('*.png')])
if not files:
    print('no files in DNI_ALDIMI')
else:
    f = files[0]
    print('Testing', f)
    res = ocr.procesar_documento(str(f))
    print('Result keys:', list(res.keys()))
    import json
    print(json.dumps(res, indent=2, ensure_ascii=False))
