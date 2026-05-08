# ─── Build stage ─────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Install Tesseract OCR + French & English language packs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure uploads dir and app files have correct ownership
RUN mkdir -p uploads && chown -R appuser:appuser /app uploads

# Entrypoint to fix bind mount permissions at container start
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# ─── Runtime ─────────────────────────────────────────────────────────
EXPOSE 5000

# Run as non-root user
USER appuser

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Tesseract uses virtually no RAM — 2 workers fine for IO-bound receipt processing
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--worker-class", "gevent", "--timeout", "120", "app:app"]
