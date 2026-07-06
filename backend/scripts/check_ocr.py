from backend import ocr_robusto as ocr

print('TESSERACT_OK =', getattr(ocr, '_TESSERACT_OK', None))
print('EASYOCR_OK   =', getattr(ocr, '_EASYOCR_OK', None))
