FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    CONFIG_DIR=/app/config \
    SQLITE_PATH=/app/data/auto-cyber-news.db

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

ENTRYPOINT ["auto-cyber-news"]
CMD ["--help"]

