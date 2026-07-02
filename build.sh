#!/usr/bin/env bash
set -e

# 1) Instalar PyTorch en su variante CPU-only PRIMERO, desde el índice
#    oficial de PyTorch. Se hace en un paso separado para que no haya
#    ambigüedad de qué índice usa pip: aquí solo se instala torch.
#    Esto evita que se descarguen ~3-4 GB de librerías CUDA (nvidia-*)
#    que la instancia gratuita de Render (sin GPU) nunca va a usar,
#    y que infladaban tanto el build como el consumo de memoria.
pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu

# 2) Instalar el resto de dependencias normalmente desde PyPI.
#    Como torch y torchvision ya están instalados (paso 1), pip los
#    detecta satisfechos y no los reinstala desde PyPI con CUDA.
pip install -r requirements.txt

# 3) Descargar recursos de NLTK necesarios para el chatbot.
python -m nltk.downloader punkt punkt_tab stopwords

# 4) Pre-descargar los modelos de EasyOCR durante el build (no en la
#    primera petición real), para que el primer usuario no tenga que
#    esperar la descarga ni se dispare un pico de memoria en caliente.
python -c "import easyocr; easyocr.Reader(['es'], gpu=False, verbose=False); print('EasyOCR modelos descargados')"