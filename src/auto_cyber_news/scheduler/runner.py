"""Scheduler runner for continuous ingestion and analysis."""

from __future__ import annotations

import asyncio
import os
import signal
from datetime import datetime, timedelta, timezone

from auto_cyber_news.analysis.enrich import enrich_articles_async
from auto_cyber_news.config.models import Config
from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.incident_repository import IncidentRepository
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.processed_articles import ProcessedArticleRepository
from auto_cyber_news.db.runtime_state import record_ingestion_cycle
from auto_cyber_news.fetchers.http import HttpClientConfig
from auto_cyber_news.fetchers.registry import build_http_client
from auto_cyber_news.logging import get_logger
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle
from auto_cyber_news.pipeline.incident_alerts import (
    dispatch_telegram_incident_alerts,
    send_email_digest_for_incidents,
)
from auto_cyber_news.pipeline.incidents import group_into_incidents
from auto_cyber_news.pipeline.ingest import run_ingestion
from auto_cyber_news.utils.time import utc_now

LOGGER = get_logger(__name__)

MIN_SCHEDULER_INTERVAL_MINUTES = 1
DEFAULT_INTERVAL_MINUTES = 60
DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1


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
            started_at = datetime.now(timezone.utc)  # noqa: UP017
            try:
                await run_cycle(config)
                LOGGER.info(
                    "Scheduler cycle completed",
                    extra={
                        "duration_seconds": (
                            datetime.now(timezone.utc) - started_at  # noqa: UP017
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
            except TimeoutError:
                continue
    except asyncio.CancelledError:
        LOGGER.info("Scheduler cancelled")
    finally:
        LOGGER.info("Scheduler stopped gracefully")


async def run_cycle(config: Config) -> None:
    """Run one ingestion, analysis, incident grouping, and notification cycle.

    Articles already processed in earlier cycles are dropped before enrichment,
    so the pipeline never re-summarizes (re-bills the summarizer API for) or
    re-alerts old news during continuous operation.
    """
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
        new_articles = _select_unprocessed_articles(config, ingestion_result.articles)
        skipped_existing = len(ingestion_result.articles) - len(new_articles)

        enriched_articles = await enrich_articles_async(new_articles, config)
        incidents = group_into_incidents(enriched_articles)

        sources_ok = sum(1 for result in ingestion_result.source_results if result.error is None)
        sources_failed = sum(
            1 for result in ingestion_result.source_results if result.error is not None
        )

        _persist_cycle_state(
            config,
            enriched_articles=enriched_articles,
            sources_ok=sources_ok,
            sources_failed=sources_failed,
        )

        if sources_failed > 0 and sources_ok == 0:
            LOGGER.error(
                "All sources failed during ingestion cycle",
                extra={"sources_failed": sources_failed},
            )

        LOGGER.info(
            "Analysis completed",
            extra={
                "new_article_count": len(enriched_articles),
                "skipped_existing": skipped_existing,
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
        await send_email_digest_for_incidents(incidents, config)
    finally:
        await http_client.close()


def _select_unprocessed_articles(
    config: Config,
    articles: tuple[NormalizedArticle, ...],
) -> tuple[NormalizedArticle, ...]:
    """Drop articles already seen in earlier cycles (persistent deduplication)."""
    connection = connect(config.database.sqlite_path)
    try:
        repository = ProcessedArticleRepository(connection)
        new_articles = repository.filter_new(articles)
        connection.commit()
    finally:
        connection.close()
    return new_articles


def _persist_cycle_state(
    config: Config,
    *,
    enriched_articles: tuple[EnrichedArticle, ...],
    sources_ok: int,
    sources_failed: int,
) -> None:
    """Record cycle health, processed-article fingerprints, and prune old rows."""
    cutoff_iso = (utc_now() - timedelta(days=_retention_days())).isoformat()
    connection = connect(config.database.sqlite_path)
    try:
        record_ingestion_cycle(connection, sources_ok=sources_ok, sources_failed=sources_failed)
        processed_repository = ProcessedArticleRepository(connection)
        processed_repository.record_all(enriched_articles)
        pruned_articles = processed_repository.prune_older_than(cutoff_iso)
        pruned_alerts = IncidentRepository(connection).prune_alerts_older_than(cutoff_iso)
        connection.commit()
    finally:
        connection.close()
    if pruned_articles or pruned_alerts:
        LOGGER.info(
            "Retention prune completed",
            extra={"pruned_articles": pruned_articles, "pruned_alerts": pruned_alerts},
        )


def _retention_days() -> int:
    raw_value = os.getenv("RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)).strip()
    try:
        return max(MIN_RETENTION_DAYS, int(raw_value))
    except ValueError:
        return DEFAULT_RETENTION_DAYS


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
