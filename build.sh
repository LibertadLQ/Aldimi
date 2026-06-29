#!/usr/bin/env bash
set -e
pip install -r requirements.txt
python -m nltk.downloader punkt punkt_tab stopwords
python -c "import easyocr; easyocr.Reader(['es','en'], gpu=False, verbose=False); print('EasyOCR modelos descargados')"