# ─── Build stage ─────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# OpenCV dependencies (required by EasyOCR)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user early (needed for model cache permissions)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models (French + English) so first request is fast
# Uses EASYOCR_MODULE_PATH to cache models inside the app directory
ENV EASYOCR_MODULE_PATH=/app/.EasyOCR
RUN python -c "import easyocr; easyocr.Reader(['fr', 'en'], gpu=False)" && \
    chown -R appuser:appuser /app/.EasyOCR

# Copy application code
COPY . .

# Ensure uploads dir and app files have correct ownership
RUN mkdir -p uploads && chown -R appuser:appuser /app uploads

# ─── Runtime ─────────────────────────────────────────────────────────
EXPOSE 5000

# Run as non-root user
USER appuser

# Default: production server with gunicorn (1 worker — EasyOCR models ~100MB in RAM)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--worker-class", "gevent", "--timeout", "120", "app:app"]