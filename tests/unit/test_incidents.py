"""Tests for incident grouping and alert suppression."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.incident_repository import IncidentRepository
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle, SeverityLevel
from auto_cyber_news.models.incident import SecurityIncident
from auto_cyber_news.notifications.formatting import format_telegram_incident_alert
from auto_cyber_news.pipeline.alert_suppression import evaluate_telegram_suppression
from auto_cyber_news.pipeline.incidents import generate_incident_id, group_into_incidents


def test_group_into_incidents_merges_same_campaign_from_multiple_sources() -> None:
    """Related supply-chain articles should become one incident."""
    articles = (
        _enriched(
            title="TeamPCP Supply Chain Campaign hits npm and PyPI",
            url="https://source-a.example/teampcp",
            canonical_url="https://example.com/teampcp-a",
            source="Source A",
            content_hash="hash-a",
            severity=SeverityLevel.HIGH,
            risk_score=82,
            categories=("supply_chain", "malware"),
            cves=(),
        ),
        _enriched(
            title="TeamPCP supply chain worm campaign spreads via npm PyPI",
            url="https://source-b.example/teampcp",
            canonical_url="https://example.com/teampcp-b",
            source="Source B",
            content_hash="hash-b",
            severity=SeverityLevel.HIGH,
            risk_score=78,
            categories=("supply_chain", "exploit"),
            cves=(),
        ),
    )

    incidents = group_into_incidents(articles)

    assert len(incidents) == 1
    assert incidents[0].article_count == 2
    assert set(incidents[0].sources) == {"Source A", "Source B"}
    assert incidents[0].max_severity is SeverityLevel.HIGH


def test_generate_incident_id_is_stable_for_same_url() -> None:
    """Incident ids should be deterministic for a single canonical URL."""
    article = _enriched(
        title="Single story",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source="Example",
        content_hash="hash-1",
        severity=SeverityLevel.MEDIUM,
        risk_score=50,
        categories=(),
        cves=(),
    )
    first = generate_incident_id((article,))
    second = generate_incident_id((article,))
    assert first == second


def test_telegram_suppression_blocks_repeat_alerts_within_cooldown(tmp_path: Path) -> None:
    """Cooldown should suppress repeat Telegram alerts for the same incident."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)
    connection = connect(sqlite_path)
    repository = IncidentRepository(connection)

    incident = SecurityIncident(
        incident_id="incident-test",
        title="Repeat campaign",
        articles=(_article_tuple(),),
        max_severity=SeverityLevel.HIGH,
        max_risk_score=80,
        sources=("Example",),
        categories=("supply_chain",),
        detected_cves=(),
    )
    repository.upsert_incident(incident)
    repository.record_alert(incident, channel="telegram")
    connection.commit()

    decision = evaluate_telegram_suppression(repository, incident, cooldown_hours=6)
    assert decision.should_alert is False
    assert decision.reason == "cooldown_active"
    connection.close()


def test_telegram_suppression_allows_one_severity_escalation(tmp_path: Path) -> None:
    """A severity jump during cooldown should allow one escalation alert."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)
    connection = connect(sqlite_path)
    repository = IncidentRepository(connection)

    low_incident = SecurityIncident(
        incident_id="incident-escalation",
        title="Escalating campaign",
        articles=(_article_tuple(severity=SeverityLevel.LOW, risk_score=30),),
        max_severity=SeverityLevel.LOW,
        max_risk_score=30,
        sources=("Example",),
        categories=("malware",),
        detected_cves=(),
    )
    repository.upsert_incident(low_incident)
    repository.record_alert(low_incident, channel="telegram")
    connection.commit()

    critical_incident = SecurityIncident(
        incident_id="incident-escalation",
        title="Escalating campaign",
        articles=(_article_tuple(severity=SeverityLevel.CRITICAL, risk_score=95),),
        max_severity=SeverityLevel.CRITICAL,
        max_risk_score=95,
        sources=("Example",),
        categories=("malware",),
        detected_cves=("CVE-2026-9999",),
    )

    decision = evaluate_telegram_suppression(repository, critical_incident, cooldown_hours=6)
    assert decision.should_alert is True
    assert decision.is_escalation is True

    repository.record_alert(critical_incident, channel="telegram", escalation=True)
    connection.commit()

    blocked = evaluate_telegram_suppression(repository, critical_incident, cooldown_hours=6)
    assert blocked.should_alert is False
    connection.close()


def test_format_telegram_incident_alert_lists_related_articles() -> None:
    """Grouped Telegram output should include multiple related articles."""
    message = format_telegram_incident_alert(
        title="TeamPCP Supply Chain Campaign",
        severity="high",
        risk_score=85,
        sources=("Krebs", "BleepingComputer"),
        categories=("supply_chain", "malware"),
        detected_cves=("CVE-2026-1000",),
        related_articles=(
            ("Story A", "https://example.com/a", "Krebs"),
            ("Story B", "https://example.com/b", "BleepingComputer"),
        ),
    )

    assert "INCIDENT HIGH" in message
    assert "Krebs" in message
    assert "Story A" in message
    assert "Story B" in message


def _enriched(
    *,
    title: str,
    url: str,
    canonical_url: str,
    source: str,
    content_hash: str,
    severity: SeverityLevel,
    risk_score: int,
    categories: tuple[str, ...],
    cves: tuple[str, ...],
) -> EnrichedArticle:
    return EnrichedArticle(
        article=NormalizedArticle(
            title=title,
            url=url,
            canonical_url=canonical_url,
            content_hash=content_hash,
            published_at=None,
            source=source,
            source_id=source.casefold().replace(" ", "_"),
            raw_content=f"{title} supply chain worm exploit campaign",
            summary_placeholder=title,
            category_placeholder="uncategorized",
        ),
        severity=severity,
        detected_cves=cves,
        categories=categories,
        risk_score=risk_score,
        ai_summary="Incident summary",
        is_critical=severity is SeverityLevel.CRITICAL,
        should_alert_telegram=True,
        should_include_in_email_digest=True,
        severity_reasons=("test",),
    )


def _article_tuple(
    *,
    severity: SeverityLevel = SeverityLevel.HIGH,
    risk_score: int = 80,
) -> EnrichedArticle:
    return _enriched(
        title="Campaign update",
        url="https://example.com/update",
        canonical_url="https://example.com/update",
        source="Example",
        content_hash="hash-update",
        severity=severity,
        risk_score=risk_score,
        categories=("supply_chain",),
        cves=(),
    )
