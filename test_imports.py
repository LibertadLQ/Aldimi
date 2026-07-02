#!/usr/bin/env python
# test_imports.py — Verify all modules load correctly

print("=" * 60)
print("Testing aldimi consolidation...")
print("=" * 60)

try:
    import aldimi
    print("✓ aldimi module loaded successfully")
    print(f"  - Mode: {aldimi.ALDIMI_ENV}")
    print(f"  - Tesseract enabled: {aldimi._USE_TESSERACT}")
    print(f"  - Tesseract available: {aldimi._TESSERACT_OK}")
    print(f"  - EasyOCR available: {aldimi._EASYOCR_OK}")
    print(f"  - Database folder: {aldimi.DB_FOLDER}")
    print(f"  - Patients in memory: {len(aldimi._BD)}")
except Exception as e:
    print(f"✗ Failed to import aldimi: {e}")
    exit(1)

try:
    import aldimi_core
    print("\n✓ aldimi_core module loaded successfully")
    print(f"  - Re-exported functions: {len(aldimi_core.__all__)} items")
    print(f"  - Can call chatbot_response_nlp: {callable(aldimi_core.chatbot_response_nlp)}")
except Exception as e:
    print(f"✗ Failed to import aldimi_core: {e}")
    exit(1)

try:
    import ocr
    print("\n✓ ocr module (FastAPI) loaded successfully")
    print(f"  - FastAPI app: {ocr.app}")
except Exception as e:
    print(f"✗ Failed to import ocr: {e}")
    exit(1)

try:
    import nlp
    print("\n✓ nlp module loaded successfully")
    print(f"  - Functions exported: {nlp.__all__}")
except Exception as e:
    print(f"✗ Failed to import nlp: {e}")
    exit(1)

try:
    import cnn
    print("\n✓ cnn module loaded successfully")
    print(f"  - Functions exported: {cnn.__all__}")
except Exception as e:
    print(f"✗ Failed to import cnn: {e}")
    exit(1)

# Test NLP response
print("\n" + "=" * 60)
print("Testing NLP chatbot...")
print("=" * 60)
intent, conf, response = aldimi_core.chatbot_response_nlp("¿Cuál es el horario?")
print(f"Intent: {intent}, Confidence: {conf}")
print(f"Response: {response[:80]}...")

print("\n" + "=" * 60)
print("✓ All modules successfully consolidated and working!")
print("=" * 60)
