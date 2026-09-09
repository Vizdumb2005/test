FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
# Production deps only (no dev extras) for a smaller image.
RUN pip install --upgrade pip && pip install -e .

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY reports/ ./reports/

# Pre-create writable dirs and drop privileges: never run as root.
RUN mkdir -p /app/data /app/reports /home/appuser/.cache/huggingface \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=90s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
