"""Production health check reporting."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from auto_cyber_news.config.loader import ConfigError, load_config
from auto_cyber_news.config.validation import ConfigValidationError
from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.runtime_state import (
    KEY_INGESTION_LAST_RUN,
    KEY_LAST_CYCLE_SOURCES_FAILED,
    KEY_LAST_CYCLE_SOURCES_OK,
    get_metadata,
)

STALE_INGESTION_MULTIPLIER = 2


def run_health_check(config_dir: Path) -> dict[str, Any]:
    """Build a JSON-serializable health report without external network calls."""
    config_loaded = False
    db_status = False
    ingestion_last_run: str | None = None
    rss_sources_ok = False
    details: dict[str, Any] = {}

    try:
        config = load_config(config_dir)
        config_loaded = True
        details["environment"] = config.environment
        rss_sources_ok = _rss_sources_config_ok(config)
        details["enabled_source_count"] = sum(1 for source in config.sources if source.enabled)

        sqlite_path = config.database.sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        run_migrations(sqlite_path)
        connection = connect(sqlite_path)
        try:
            connection.execute("SELECT 1")
            db_status = True
            ingestion_last_run = get_metadata(connection, KEY_INGESTION_LAST_RUN)
            details["last_cycle_sources_ok"] = get_metadata(connection, KEY_LAST_CYCLE_SOURCES_OK)
            details["last_cycle_sources_failed"] = get_metadata(
                connection,
                KEY_LAST_CYCLE_SOURCES_FAILED,
            )
        finally:
            connection.close()
    except (ConfigError, ConfigValidationError, OSError, sqlite3.DatabaseError, ValueError) as exc:
        details["error"] = str(exc)

    overall_status = _overall_status(
        config_loaded=config_loaded,
        db_status=db_status,
        rss_sources_ok=rss_sources_ok,
        ingestion_last_run=ingestion_last_run,
    )

    return {
        "overall_status": overall_status,
        "db_status": db_status,
        "config_loaded": config_loaded,
        "ingestion_last_run": ingestion_last_run,
        "rss_sources_ok": rss_sources_ok,
        "details": details,
    }


def _overall_status(
    *,
    config_loaded: bool,
    db_status: bool,
    rss_sources_ok: bool,
    ingestion_last_run: str | None,
) -> str:
    if not config_loaded or not db_status:
        return "unhealthy"
    if not rss_sources_ok:
        return "degraded"
    if ingestion_last_run is None:
        return "degraded"
    if _ingestion_is_stale(ingestion_last_run):
        return "degraded"
    return "healthy"


def _ingestion_is_stale(ingestion_last_run: str) -> bool:
    try:
        last_run = datetime.fromisoformat(ingestion_last_run)
    except ValueError:
        return True
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)

    interval_minutes = _scheduler_interval_minutes()
    stale_after = timedelta(minutes=interval_minutes * STALE_INGESTION_MULTIPLIER)
    return datetime.now(timezone.utc) - last_run > stale_after


def _scheduler_interval_minutes() -> int:
    raw_value = os.getenv("SCHEDULER_INTERVAL_MINUTES", "15").strip()
    try:
        return max(10, int(raw_value))
    except ValueError:
        return 15


def _rss_sources_config_ok(config: object) -> bool:
    """Validate that enabled RSS sources are configured with usable URLs."""
    sources = getattr(config, "sources", ())
    enabled = [source for source in sources if getattr(source, "enabled", False)]
    if not enabled:
        return False

    rss_sources = [source for source in enabled if getattr(source, "type", "") == "rss"]
    if not rss_sources:
        return True

    for source in rss_sources:
        url = getattr(source, "url", "")
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
    return True
