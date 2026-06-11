"""Incident-level Telegram and digest dispatch with suppression."""

from __future__ import annotations

import smtplib
import uuid
from datetime import datetime, timezone

from auto_cyber_news.config.models import Config
from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.incident_repository import IncidentRepository
from auto_cyber_news.db.repositories import DigestRecord, create_repositories
from auto_cyber_news.logging import get_logger
from auto_cyber_news.models.incident import SecurityIncident
from auto_cyber_news.notifications.email import (
    DigestArticlePayload,
    EmailConfigurationError,
    EmailNotifier,
    is_email_configured,
)
from auto_cyber_news.notifications.formatting import format_telegram_incident_alert
from auto_cyber_news.notifications.telegram import (
    TelegramConfigurationError,
    TelegramNotifier,
    is_telegram_configured,
)
from auto_cyber_news.pipeline.alert_suppression import evaluate_telegram_suppression
from auto_cyber_news.pipeline.incidents import MAX_RELATED_ARTICLES_IN_ALERT
from auto_cyber_news.utils.time import utc_now

LOGGER = get_logger(__name__)


async def dispatch_telegram_incident_alerts(
    incidents: tuple[SecurityIncident, ...],
    config: Config,
) -> None:
    """Send one Telegram alert per qualifying incident after suppression checks."""
    candidates = tuple(incident for incident in incidents if incident.should_alert_telegram())
    if not candidates:
        return

    if config.alerts.dry_run:
        LOGGER.info(
            "Telegram incident alerts skipped (dry run)",
            extra={"candidate_count": len(candidates)},
        )
        return

    if not is_telegram_configured():
        LOGGER.warning(
            "Telegram incident alerts skipped (not configured)",
            extra={"candidate_count": len(candidates)},
        )
        return

    connection = connect(config.database.sqlite_path)
    repository = IncidentRepository(connection)
    notifier = TelegramNotifier.from_env()

    try:
        for incident in candidates:
            repository.upsert_incident(incident)
            decision = evaluate_telegram_suppression(
                repository,
                incident,
                cooldown_hours=config.alerts.alert_cooldown_hours,
            )
            if not decision.should_alert:
                LOGGER.info(
                    "Telegram incident alert suppressed",
                    extra={
                        "incident_id": incident.incident_id,
                        "reason": decision.reason,
                    },
                )
                continue

            message = format_telegram_incident_alert(
                title=incident.title,
                severity=incident.max_severity.value,
                risk_score=incident.max_risk_score,
                sources=incident.sources,
                categories=incident.categories,
                detected_cves=incident.detected_cves,
                related_articles=_related_article_rows(incident),
                ai_summary=incident.articles[0].ai_summary,
                detected_at=utc_now(),
                max_related_articles=MAX_RELATED_ARTICLES_IN_ALERT,
            )
            await notifier.send_message(message)
            repository.record_alert(
                incident,
                channel="telegram",
                escalation=decision.is_escalation,
            )
            connection.commit()
            LOGGER.info(
                "Telegram incident alert sent",
                extra={
                    "incident_id": incident.incident_id,
                    "article_count": incident.article_count,
                    "severity": incident.max_severity.value,
                    "reason": decision.reason,
                },
            )
    except TelegramConfigurationError:
        LOGGER.exception("Telegram configuration error")
    except RuntimeError:
        LOGGER.exception("Telegram delivery failed")
    finally:
        await notifier.close()
        connection.close()


async def send_email_digest_for_incidents(
    incidents: tuple[SecurityIncident, ...],
    config: Config,
    *,
    digest_date: str | None = None,
) -> bool:
    """Send a digest email at most once per UTC date; return whether one was sent.

    Idempotency is enforced through the ``sent_digest`` table rather than an
    in-memory marker, so cron/run-once invocations and process restarts cannot
    produce duplicate digests for the same day.
    """
    resolved_date = digest_date or datetime.now(timezone.utc).date().isoformat()  # noqa: UP017

    digest_incidents = tuple(
        incident for incident in incidents if incident.should_include_in_email_digest()
    )
    if not digest_incidents:
        return False

    ranked = sorted(
        digest_incidents,
        key=lambda incident: (incident.max_risk_score, incident.article_count),
        reverse=True,
    )[: config.digest.max_articles]

    if config.alerts.dry_run:
        LOGGER.info("Email digest skipped (dry run)", extra={"incident_count": len(ranked)})
        return False

    if not is_email_configured():
        LOGGER.warning(
            "Email digest skipped (not configured)",
            extra={"incident_count": len(ranked)},
        )
        return False

    connection = connect(config.database.sqlite_path)
    repositories = create_repositories(connection)
    try:
        if repositories.digests.get_by_date(resolved_date) is not None:
            LOGGER.info(
                "Email digest already sent for date",
                extra={"digest_date": resolved_date},
            )
            return False

        payloads = tuple(_digest_payload_for_incident(incident) for incident in ranked)
        notifier = EmailNotifier.from_env()
        subject = await notifier.send_daily_digest(
            subject_prefix=config.digest.subject_prefix,
            digest_date=resolved_date,
            articles=payloads,
        )
        repositories.digests.create(
            DigestRecord(
                id=str(uuid.uuid4()),
                digest_date=resolved_date,
                recipient=notifier.recipient,
                subject=subject,
                sent_at=utc_now().isoformat(),
                article_count=len(payloads),
            ),
        )
        connection.commit()
        LOGGER.info(
            "Email digest sent",
            extra={"subject": subject, "incident_count": len(payloads)},
        )
        return True
    except EmailConfigurationError:
        LOGGER.exception("Email configuration error")
    except (OSError, smtplib.SMTPException):
        LOGGER.exception("Email digest delivery failed")
    finally:
        connection.close()

    return False


def _related_article_rows(incident: SecurityIncident) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for article in incident.articles:
        rows.append((article.article.title, article.article.url, article.article.source))
    return tuple(rows)


def _digest_payload_for_incident(incident: SecurityIncident) -> DigestArticlePayload:
    lead = incident.articles[0]
    title = incident.title
    if incident.article_count > 1:
        title = f"{title} (+{incident.article_count - 1} related)"
    return DigestArticlePayload(
        title=title,
        url=lead.article.url,
        severity=incident.max_severity.value,
        risk_score=incident.max_risk_score,
        categories=incident.categories,
        detected_cves=incident.detected_cves,
        ai_summary=lead.ai_summary,
    )
