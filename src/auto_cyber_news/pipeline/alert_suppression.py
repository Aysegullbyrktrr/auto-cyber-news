"""Cooldown and escalation rules for incident-level alerting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from auto_cyber_news.db.incident_repository import IncidentRepository
from auto_cyber_news.models.article import SeverityLevel
from auto_cyber_news.models.incident import SecurityIncident

_SEVERITY_ORDER = {
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}


@dataclass(frozen=True)
class AlertSuppressionDecision:
    """Whether an incident alert should be delivered."""

    should_alert: bool
    reason: str
    is_escalation: bool = False


def evaluate_telegram_suppression(
    repository: IncidentRepository,
    incident: SecurityIncident,
    *,
    cooldown_hours: int,
) -> AlertSuppressionDecision:
    """Apply cooldown and one-time severity escalation rules for Telegram."""
    last_alert = repository.get_latest_alert(incident.incident_id, channel="telegram")
    if last_alert is None:
        return AlertSuppressionDecision(True, "first_alert")

    last_alerted_at = datetime.fromisoformat(last_alert.alerted_at)
    if last_alerted_at.tzinfo is None:
        last_alerted_at = last_alerted_at.replace(tzinfo=timezone.utc)  # noqa: UP017

    elapsed = datetime.now(timezone.utc) - last_alerted_at  # noqa: UP017
    if elapsed >= timedelta(hours=cooldown_hours):
        return AlertSuppressionDecision(True, "cooldown_elapsed")

    last_severity = SeverityLevel(last_alert.severity)
    if _severity_rank(incident.max_severity) > _severity_rank(last_severity):
        if repository.has_escalation_alert(incident.incident_id, channel="telegram"):
            return AlertSuppressionDecision(False, "escalation_already_sent")
        return AlertSuppressionDecision(True, "severity_escalation", is_escalation=True)

    return AlertSuppressionDecision(False, "cooldown_active")


def _severity_rank(level: SeverityLevel) -> int:
    return _SEVERITY_ORDER[level]
