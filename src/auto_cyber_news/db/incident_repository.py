"""SQLite persistence for incidents and alert suppression."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass

from auto_cyber_news.models.incident import SecurityIncident
from auto_cyber_news.utils.time import utc_now


@dataclass(frozen=True)
class IncidentAlertRecord:
    """Persisted incident alert delivery record."""

    id: str
    incident_id: str
    channel: str
    severity: str
    risk_score: int
    alerted_at: str
    escalation: bool


class IncidentRepository:
    """Repository for incident tracking and alert cooldown state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_incident(self, incident: SecurityIncident) -> None:
        """Create or update an incident row."""
        now = utc_now().isoformat()
        existing = self._connection.execute(
            "SELECT created_at FROM incidents WHERE incident_id = ?",
            (incident.incident_id,),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else now
        self._connection.execute(
            """
            INSERT INTO incidents (
                incident_id, title, max_severity, max_risk_score, article_count,
                sources, created_at, updated_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_id) DO UPDATE SET
                title = excluded.title,
                max_severity = excluded.max_severity,
                max_risk_score = excluded.max_risk_score,
                article_count = excluded.article_count,
                sources = excluded.sources,
                updated_at = excluded.updated_at,
                last_seen_at = excluded.last_seen_at
            """,
            (
                incident.incident_id,
                incident.title,
                incident.max_severity.value,
                incident.max_risk_score,
                incident.article_count,
                json.dumps(list(incident.sources), separators=(",", ":")),
                created_at,
                now,
                now,
            ),
        )

    def get_latest_alert(self, incident_id: str, *, channel: str) -> IncidentAlertRecord | None:
        """Return the most recent alert for an incident and channel."""
        row = self._connection.execute(
            """
            SELECT id, incident_id, channel, severity, risk_score, alerted_at, escalation
            FROM incident_alerts
            WHERE incident_id = ? AND channel = ?
            ORDER BY alerted_at DESC
            LIMIT 1
            """,
            (incident_id, channel),
        ).fetchone()
        return _alert_from_row(row) if row is not None else None

    def has_escalation_alert(self, incident_id: str, *, channel: str) -> bool:
        """Return whether an escalation alert was already sent for this incident."""
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM incident_alerts
            WHERE incident_id = ? AND channel = ? AND escalation = 1
            """,
            (incident_id, channel),
        ).fetchone()
        return int(row["count"]) > 0

    def prune_alerts_older_than(self, cutoff_iso: str) -> int:
        """Delete incident alert rows older than the cutoff to bound table growth.

        The cutoff is far larger than the alert cooldown window, so suppression
        decisions are unaffected.
        """
        cursor = self._connection.execute(
            "DELETE FROM incident_alerts WHERE alerted_at < ?",
            (cutoff_iso,),
        )
        return max(0, cursor.rowcount)

    def record_alert(
        self,
        incident: SecurityIncident,
        *,
        channel: str,
        escalation: bool = False,
    ) -> IncidentAlertRecord:
        """Persist a delivered incident alert."""
        record = IncidentAlertRecord(
            id=str(uuid.uuid4()),
            incident_id=incident.incident_id,
            channel=channel,
            severity=incident.max_severity.value,
            risk_score=incident.max_risk_score,
            alerted_at=utc_now().isoformat(),
            escalation=escalation,
        )
        self._connection.execute(
            """
            INSERT INTO incident_alerts (
                id, incident_id, channel, severity, risk_score, alerted_at, escalation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.incident_id,
                record.channel,
                record.severity,
                record.risk_score,
                record.alerted_at,
                1 if record.escalation else 0,
            ),
        )
        return record


def _alert_from_row(row: sqlite3.Row) -> IncidentAlertRecord:
    return IncidentAlertRecord(
        id=str(row["id"]),
        incident_id=str(row["incident_id"]),
        channel=str(row["channel"]),
        severity=str(row["severity"]),
        risk_score=int(row["risk_score"]),
        alerted_at=str(row["alerted_at"]),
        escalation=bool(row["escalation"]),
    )
