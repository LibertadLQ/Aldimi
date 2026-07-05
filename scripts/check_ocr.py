import sys
sys.path.insert(0, '.')
try:
    from backend import ocr_robusto as ocr
    print('TESSERACT_OK =', getattr(ocr, '_TESSERACT_OK', None))
    print('EASYOCR_OK   =', getattr(ocr, '_EASYOCR_OK', None))
except Exception as e:
    print('ERROR importing ocr_robusto:', e)
    raise
