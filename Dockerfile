FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONHASHSEED=random \
    DYNAMICPRO_ENV=production \
    DYNAMICPRO_MODE=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-production.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements-production.txt

COPY . .

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin dynamicpro && \
    mkdir -p /app/logs /app/uploads && \
    chown -R dynamicpro:dynamicpro /app

USER dynamicpro

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/ready', timeout=5)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
