# ─── Build stage ─────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Install Tesseract OCR + French language pack
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure uploads directory exists
RUN mkdir -p uploads

# ─── Runtime ─────────────────────────────────────────────────────────
EXPOSE 5000

# Default: production server with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
