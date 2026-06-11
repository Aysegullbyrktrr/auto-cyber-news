FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    CONFIG_DIR=/app/config \
    SQLITE_PATH=/app/data/auto-cyber-news.db \
    SCHEDULER_INTERVAL_MINUTES=60 \
    LOG_FORMAT=json

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY config ./config
COPY src ./src
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data && chown -R app:app /app
USER app

VOLUME ["/app/data"]

# Liveness: the CLI health-check exits non-zero only when config/DB are broken,
# so the orchestrator restarts a genuinely unhealthy container.
HEALTHCHECK --interval=5m --timeout=30s --start-period=90s --retries=3 \
    CMD auto-cyber-news health-check || exit 1

ENTRYPOINT ["auto-cyber-news"]
CMD ["run-scheduler"]

