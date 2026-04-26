# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Security: run as non-root
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install system deps required by psycopg2 / cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# ---- dependencies ----
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- runtime ----
FROM deps AS runtime
COPY backend/ ./backend/

# Drop privileges
USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
