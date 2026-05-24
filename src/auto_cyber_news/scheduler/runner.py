"""Scheduler runner for continuous ingestion and analysis."""

from __future__ import annotations

import asyncio
import os
import signal
from datetime import datetime, timezone

from auto_cyber_news.analysis.enrich import enrich_articles
from auto_cyber_news.config.models import Config
from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.runtime_state import record_ingestion_cycle
from auto_cyber_news.fetchers.http import AsyncHttpClient, HttpClientConfig
from auto_cyber_news.fetchers.registry import build_http_client
from auto_cyber_news.logging import get_logger
from auto_cyber_news.pipeline.incident_alerts import (
    dispatch_telegram_incident_alerts,
    send_email_digest_for_incidents,
)
from auto_cyber_news.pipeline.incidents import group_into_incidents
from auto_cyber_news.pipeline.ingest import run_ingestion

LOGGER = get_logger(__name__)

MIN_SCHEDULER_INTERVAL_MINUTES = 10
DEFAULT_INTERVAL_MINUTES = 15
_last_digest_sent_at: datetime | None = None


async def run_scheduler(
    config: Config,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Run ingestion and analysis on a periodic asyncio loop until shutdown."""
    interval = interval_seconds if interval_seconds is not None else _interval_seconds_from_env()
    shutdown_event = asyncio.Event()
    _register_shutdown_handlers(shutdown_event)

    LOGGER.info(
        "Scheduler started",
        extra={"interval_seconds": interval, "environment": config.environment},
    )

    try:
        while not shutdown_event.is_set():
            started_at = datetime.now(timezone.utc)
            try:
                await run_cycle(config)
                LOGGER.info(
                    "Scheduler cycle completed",
                    extra={
                        "duration_seconds": (
                            datetime.now(timezone.utc) - started_at
                        ).total_seconds(),
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Scheduler cycle failed")

            if shutdown_event.is_set():
                break

            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        LOGGER.info("Scheduler cancelled")
    finally:
        LOGGER.info("Scheduler stopped gracefully")


async def run_cycle(config: Config) -> None:
    """Run one ingestion, analysis, incident grouping, and notification cycle."""
    global _last_digest_sent_at

    run_migrations(config.database.sqlite_path)
    http_client = build_http_client(
        HttpClientConfig(
            timeout_seconds=config.http.timeout_seconds,
            total_retries=config.http.total_retries,
            user_agent=config.http.user_agent,
        ),
    )

    try:
        ingestion_result = await run_ingestion(config, http_client=http_client)
        enriched_articles = enrich_articles(ingestion_result.articles, config)
        incidents = group_into_incidents(enriched_articles)

        sources_ok = sum(1 for result in ingestion_result.source_results if result.error is None)
        sources_failed = sum(
            1 for result in ingestion_result.source_results if result.error is not None
        )

        connection = connect(config.database.sqlite_path)
        try:
            record_ingestion_cycle(
                connection,
                sources_ok=sources_ok,
                sources_failed=sources_failed,
            )
        finally:
            connection.close()

        LOGGER.info(
            "Analysis completed",
            extra={
                "article_count": len(enriched_articles),
                "incident_count": len(incidents),
                "sources_ok": sources_ok,
                "sources_failed": sources_failed,
                "telegram_incident_candidates": sum(
                    1 for incident in incidents if incident.should_alert_telegram()
                ),
                "digest_incident_candidates": sum(
                    1 for incident in incidents if incident.should_include_in_email_digest()
                ),
            },
        )

        await dispatch_telegram_incident_alerts(incidents, config)
        _last_digest_sent_at = await send_email_digest_for_incidents(
            incidents,
            config,
            last_digest_sent_at=_last_digest_sent_at,
        )
    finally:
        await http_client.close()


def _interval_seconds_from_env() -> float:
    raw_value = os.getenv("SCHEDULER_INTERVAL_MINUTES", str(DEFAULT_INTERVAL_MINUTES)).strip()
    try:
        minutes = max(MIN_SCHEDULER_INTERVAL_MINUTES, int(raw_value))
    except ValueError:
        minutes = DEFAULT_INTERVAL_MINUTES
    return float(minutes * 60)


def _register_shutdown_handlers(shutdown_event: asyncio.Event) -> None:
    """Register SIGINT/SIGTERM handlers for graceful scheduler shutdown."""

    def _request_shutdown() -> None:
        LOGGER.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, _request_shutdown)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_args, **_kwargs: _request_shutdown())
