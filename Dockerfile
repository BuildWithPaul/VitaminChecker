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

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    mkdir -p uploads && chown -R appuser:appuser /app uploads

# ─── Runtime ─────────────────────────────────────────────────────────
EXPOSE 5000

# Run as non-root user
USER appuser

# Default: production server with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]