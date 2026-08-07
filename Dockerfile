# Usa una versione di Python leggera basata su Linux
FROM python:3.10-slim

# Installa Tesseract OCR nel sistema Linux di Render
RUN apt-get update && apt-get install -y tesseract-ocr

# Copia i file del tuo bot
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Avvia il bot
CMD ["python", "main.py"]