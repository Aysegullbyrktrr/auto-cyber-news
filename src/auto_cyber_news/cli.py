"""Command-line interface for operational workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from auto_cyber_news.analysis.enrich import enrich_articles
from auto_cyber_news.config.loader import ConfigError, load_config
from auto_cyber_news.config.models import Config
from auto_cyber_news.config.validation import ConfigValidationError
from auto_cyber_news.db.migrations import get_applied_migrations, get_table_counts, run_migrations
from auto_cyber_news.logging import configure_logging, correlation_context, get_logger
from auto_cyber_news.models.article import NormalizedArticle
from auto_cyber_news.notifications.email import (
    DigestArticlePayload,
    EmailConfigurationError,
    EmailNotifier,
)
from auto_cyber_news.notifications.telegram import TelegramConfigurationError, TelegramNotifier
from auto_cyber_news.pipeline.ingest import run_ingestion
from auto_cyber_news.health import run_health_check
from auto_cyber_news.scheduler.runner import run_cycle, run_scheduler

LOGGER = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(prog="auto-cyber-news")
    parser.add_argument("--config-dir", default="config", help="Configuration directory path.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("validate-config", help="Validate application configuration.")
    subparsers.add_parser("init-db", help="Initialize the SQLite database.")
    subparsers.add_parser("migrate", help="Apply pending SQLite migrations.")
    subparsers.add_parser("db-status", help="Show SQLite migration and table status.")
    subparsers.add_parser("run-ingestion", help="Fetch and normalize articles without persistence.")
    analysis_parser = subparsers.add_parser(
        "run-analysis",
        help="Enrich normalized ingestion output without persistence.",
    )
    analysis_parser.add_argument(
        "--input",
        help=(
            "Optional path to JSON output produced by run-ingestion. "
            "If omitted, ingestion runs first."
        ),
    )
    subparsers.add_parser("run-once", help="Run one ingestion and analysis cycle.")
    subparsers.add_parser("run-scheduler", help="Run continuous ingestion and analysis.")
    subparsers.add_parser("send-test-telegram", help="Send a test Telegram message.")
    subparsers.add_parser("send-test-email", help="Send a test HTML email.")
    subparsers.add_parser("digest", help="Render and send the daily digest.")
    subparsers.add_parser("health-check", help="Report production health status as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "validate-config":
        return _validate_config(Path(args.config_dir))
    if args.command == "init-db":
        return _migrate(Path(args.config_dir), command_name="init-db")
    if args.command == "migrate":
        return _migrate(Path(args.config_dir), command_name="migrate")
    if args.command == "db-status":
        return _db_status(Path(args.config_dir))
    if args.command == "run-ingestion":
        return _run_ingestion_cli(Path(args.config_dir))
    if args.command == "run-analysis":
        return _run_analysis_cli(Path(args.config_dir), input_path=args.input)
    if args.command == "run-once":
        return _run_once_cli(Path(args.config_dir))
    if args.command == "run-scheduler":
        return _run_scheduler_cli(Path(args.config_dir))
    if args.command == "send-test-telegram":
        return _send_test_telegram_cli(Path(args.config_dir))
    if args.command == "send-test-email":
        return _send_test_email_cli(Path(args.config_dir))
    if args.command == "digest":
        return _send_digest_cli(Path(args.config_dir))
    if args.command == "health-check":
        return _health_check_cli(Path(args.config_dir))
    raise NotImplementedError(f"Command is not implemented yet: {args.command}")


def _validate_config(config_dir: Path) -> int:
    """Validate configuration and report the result through structured logs."""
    correlation_id = f"validate-config-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = load_config(config_dir)
            configure_logging(
                config.logging.level,
                config.logging.format,
                file_enabled=config.logging.file_enabled,
                file_path=config.logging.file_path,
            )
            LOGGER.info(
                "Configuration validation succeeded",
                extra={
                    "source_count": len(config.sources),
                    "environment": config.environment,
                    "config_dir": str(config.config_dir),
                },
            )
            return 0
        except (ConfigError, ConfigValidationError, ValueError) as exc:
            configure_logging("ERROR", "json")
            LOGGER.error("Configuration validation failed", extra={"error": str(exc)})
            return 1


def _migrate(config_dir: Path, *, command_name: str) -> int:
    """Apply database migrations and report the result."""
    correlation_id = f"{command_name}-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir)
            result = run_migrations(config.database.sqlite_path)
            LOGGER.info(
                "Database migrations completed",
                extra={
                    "database_path": str(config.database.sqlite_path),
                    "applied_migrations": list(result.applied),
                    "skipped_migrations": list(result.skipped),
                },
            )
            return 0
        except (
            ConfigError,
            ConfigValidationError,
            OSError,
            sqlite3.DatabaseError,
            ValueError,
        ) as exc:
            configure_logging("ERROR", "json")
            LOGGER.error("Database migration failed", extra={"error": str(exc)})
            return 1


def _db_status(config_dir: Path) -> int:
    """Report database migration state and table counts."""
    correlation_id = f"db-status-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir)
            migrations = get_applied_migrations(config.database.sqlite_path)
            table_counts = get_table_counts(
                config.database.sqlite_path,
                tables=(
                    "schema_migrations",
                    "news",
                    "sent_digest",
                    "metadata",
                    "incidents",
                    "incident_alerts",
                ),
            )
            LOGGER.info(
                "Database status",
                extra={
                    "database_path": str(config.database.sqlite_path),
                    "applied_migrations": [
                        {"version": migration.version, "applied_at": migration.applied_at}
                        for migration in migrations
                    ],
                    "table_counts": table_counts,
                },
            )
            return 0
        except (
            ConfigError,
            ConfigValidationError,
            OSError,
            sqlite3.DatabaseError,
            ValueError,
        ) as exc:
            configure_logging("ERROR", "json")
            LOGGER.error("Database status failed", extra={"error": str(exc)})
            return 1


def _load_configured_logging(config_dir: Path, *, log_stream: TextIO | None = None) -> Config:
    """Load config and configure logging from it."""
    config = load_config(config_dir)
    configure_logging(
        config.logging.level,
        config.logging.format,
        file_enabled=config.logging.file_enabled,
        file_path=config.logging.file_path,
        stream=log_stream,
    )
    return config


def _run_ingestion_cli(config_dir: Path) -> int:
    """Run ingestion and emit normalized article JSON."""
    correlation_id = f"run-ingestion-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stderr)
            result = asyncio.run(run_ingestion(config))
            payload = {
                "article_count": len(result.articles),
                "articles": [article.to_dict() for article in result.articles],
                "source_results": [
                    {
                        "source_id": source_result.source_id,
                        "article_count": len(source_result.articles),
                        "error": source_result.error,
                    }
                    for source_result in result.source_results
                ],
            }
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            sys.stdout.write("\n")
            return 0
        except (ConfigError, ConfigValidationError, ValueError) as exc:
            configure_logging("ERROR", "json")
            LOGGER.error("Ingestion failed", extra={"error": str(exc)})
            return 1


def _run_analysis_cli(config_dir: Path, *, input_path: str | None) -> int:
    """Run deterministic analysis and emit enriched article JSON."""
    correlation_id = f"run-analysis-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stderr)
            if input_path is None:
                ingestion_result = asyncio.run(run_ingestion(config))
                articles = ingestion_result.articles
            else:
                articles = _load_normalized_articles(Path(input_path))
            enriched_articles = enrich_articles(articles, config)
            payload = {
                "article_count": len(enriched_articles),
                "articles": [article.to_dict() for article in enriched_articles],
            }
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            sys.stdout.write("\n")
            return 0
        except (ConfigError, ConfigValidationError, OSError, ValueError, KeyError) as exc:
            configure_logging("ERROR", "json", stream=sys.stderr)
            LOGGER.error("Analysis failed", extra={"error": str(exc)})
            return 1


def _load_normalized_articles(input_path: Path) -> tuple[NormalizedArticle, ...]:
    """Load normalized articles from a run-ingestion JSON output file."""
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    raw_articles = payload.get("articles")
    if not isinstance(raw_articles, list):
        raise ValueError("Analysis input must contain an articles list.")
    return tuple(_normalized_article_from_mapping(item) for item in raw_articles)


def _normalized_article_from_mapping(value: object) -> NormalizedArticle:
    """Build a normalized article from a JSON mapping."""
    if not isinstance(value, dict):
        raise ValueError("Each article must be a JSON object.")
    return NormalizedArticle(
        title=_json_str(value, "title"),
        url=_json_str(value, "url"),
        canonical_url=_json_str(value, "canonical_url"),
        content_hash=_json_str(value, "content_hash"),
        published_at=_json_optional_str(value, "published_at"),
        source=_json_str(value, "source"),
        source_id=_json_str(value, "source_id"),
        raw_content=_json_optional_str(value, "raw_content"),
        summary_placeholder=_json_optional_str(value, "summary_placeholder") or "",
        category_placeholder=_json_optional_str(value, "category_placeholder") or "uncategorized",
    )


def _json_str(value: dict[str, object], key: str) -> str:
    """Read a required string from a JSON object."""
    raw_value = value.get(key)
    if not isinstance(raw_value, str):
        raise ValueError(f"Article field must be a string: {key}")
    return raw_value


def _run_once_cli(config_dir: Path) -> int:
    """Run a single scheduler cycle."""
    correlation_id = f"run-once-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stderr)
            asyncio.run(run_cycle(config))
            return 0
        except (ConfigError, ConfigValidationError, ValueError) as exc:
            configure_logging("ERROR", "json", stream=sys.stderr)
            LOGGER.error("Run-once cycle failed", extra={"error": str(exc)})
            return 1


def _run_scheduler_cli(config_dir: Path) -> int:
    """Run the continuous scheduler loop."""
    correlation_id = f"run-scheduler-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stdout)
            asyncio.run(run_scheduler(config))
            return 0
        except (ConfigError, ConfigValidationError, ValueError) as exc:
            configure_logging("ERROR", "json", stream=sys.stdout)
            LOGGER.error("Scheduler failed", extra={"error": str(exc)})
            return 1


def _health_check_cli(config_dir: Path) -> int:
    """Emit JSON health status for production monitoring."""
    report = run_health_check(config_dir)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    if report["overall_status"] == "unhealthy":
        return 1
    return 0


def _send_test_telegram_cli(config_dir: Path) -> int:
    """Send a test Telegram message using configured credentials."""
    correlation_id = f"send-test-telegram-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            _load_configured_logging(config_dir, log_stream=sys.stderr)
            notifier = TelegramNotifier.from_env()

            async def _send() -> None:
                await notifier.send_message(
                    "*auto\\-cyber\\-news* test alert\n"
                    "Telegram delivery is configured correctly\\.",
                    disable_web_page_preview=True,
                )
                await notifier.close()

            asyncio.run(_send())
            LOGGER.info("Test Telegram message sent")
            return 0
        except (
            ConfigError,
            ConfigValidationError,
            TelegramConfigurationError,
            RuntimeError,
        ) as exc:
            configure_logging("ERROR", "json", stream=sys.stderr)
            LOGGER.error("Test Telegram message failed", extra={"error": str(exc)})
            return 1


def _send_test_email_cli(config_dir: Path) -> int:
    """Send a test HTML email using configured SMTP credentials."""
    correlation_id = f"send-test-email-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stderr)
            notifier = EmailNotifier.from_env()
            html = notifier.render_digest_html(
                subject="auto-cyber-news test email",
                digest_date="test",
                articles=(
                    DigestArticlePayload(
                        title="Test article",
                        url="https://example.com/test",
                        severity="high",
                        risk_score=75,
                        categories=("vulnerability",),
                        detected_cves=("CVE-2026-0001",),
                    ),
                ),
            )

            async def _send() -> None:
                await notifier.send_html("auto-cyber-news test email", html)

            asyncio.run(_send())
            LOGGER.info(
                "Test email sent",
                extra={"subject_prefix": config.digest.subject_prefix},
            )
            return 0
        except (ConfigError, ConfigValidationError, EmailConfigurationError, OSError) as exc:
            configure_logging("ERROR", "json", stream=sys.stderr)
            LOGGER.error("Test email failed", extra={"error": str(exc)})
            return 1


def _send_digest_cli(config_dir: Path) -> int:
    """Run ingestion and send a digest email from the current cycle."""
    correlation_id = f"digest-{uuid.uuid4()}"
    with correlation_context(correlation_id):
        try:
            config = _load_configured_logging(config_dir, log_stream=sys.stderr)
            ingestion_result = asyncio.run(run_ingestion(config))
            enriched_articles = enrich_articles(ingestion_result.articles, config)
            digest_articles = tuple(
                article for article in enriched_articles if article.should_include_in_email_digest
            )
            if not digest_articles:
                LOGGER.info("No digest candidates found in current ingestion cycle")
                return 0
            if config.alerts.dry_run:
                LOGGER.info(
                    "Digest skipped (dry run)",
                    extra={"candidate_count": len(digest_articles)},
                )
                return 0

            notifier = EmailNotifier.from_env()
            digest_date = datetime.now(timezone.utc).date().isoformat()
            payloads = tuple(
                DigestArticlePayload(
                    title=article.article.title,
                    url=article.article.url,
                    severity=article.severity.value,
                    risk_score=article.risk_score,
                    categories=article.categories,
                    detected_cves=article.detected_cves,
                )
                for article in sorted(
                    digest_articles,
                    key=lambda item: item.risk_score,
                    reverse=True,
                )[: config.digest.max_articles]
            )

            async def _send() -> str:
                return await notifier.send_daily_digest(
                    subject_prefix=config.digest.subject_prefix,
                    digest_date=digest_date,
                    articles=payloads,
                )

            subject = asyncio.run(_send())
            LOGGER.info("Digest sent", extra={"subject": subject, "article_count": len(payloads)})
            return 0
        except (
            ConfigError,
            ConfigValidationError,
            EmailConfigurationError,
            OSError,
            ValueError,
        ) as exc:
            configure_logging("ERROR", "json", stream=sys.stderr)
            LOGGER.error("Digest failed", extra={"error": str(exc)})
            return 1


def _json_optional_str(value: dict[str, object], key: str) -> str | None:
    """Read an optional string from a JSON object."""
    raw_value = value.get(key)
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError(f"Article field must be a string or null: {key}")
    return raw_value
