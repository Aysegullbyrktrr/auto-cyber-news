"""Tests for deterministic intelligence analysis."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.analysis.categorize import categorize_article
from auto_cyber_news.analysis.cve import extract_cves
from auto_cyber_news.analysis.decision import (
    should_alert_telegram,
    should_include_in_email_digest,
)
from auto_cyber_news.analysis.enrich import enrich_article
from auto_cyber_news.config.models import (
    AlertConfig,
    AnalysisConfig,
    CategoryConfig,
    Config,
    DatabaseConfig,
    DecisionConfig,
    DigestConfig,
    HttpConfig,
    LoggingConfig,
    SeverityRuleConfig,
    SeverityThresholdConfig,
    SourceConfig,
)
from auto_cyber_news.models.article import NormalizedArticle, SeverityLevel


def test_extract_cves_normalizes_and_deduplicates() -> None:
    """CVE extraction should normalize case and remove duplicates."""
    assert extract_cves("cve-2026-1234 and CVE-2026-1234", "CVE-2025-99999") == (
        "CVE-2025-99999",
        "CVE-2026-1234",
    )


def test_categorize_article_supports_multiple_labels() -> None:
    """Threat categorization should allow multiple labels."""
    article = _article(
        title="Zero-day CVE exploited by ransomware group",
        raw_content="Cloud customers are affected.",
    )

    assert categorize_article(article, _config().analysis.categories) == (
        "ransomware",
        "vulnerability",
        "zero_day",
        "cloud_security",
    )


def test_enrich_article_scores_critical_and_sets_decisions() -> None:
    """Enrichment should add severity, CVEs, categories, risk score, and decisions."""
    enriched = enrich_article(
        _article(
            title="CVE-2026-1234 zero-day ransomware exploit actively exploited in the wild",
            raw_content="A data breach campaign is underway.",
        ),
        _config(),
    )

    assert enriched.severity is SeverityLevel.CRITICAL
    assert enriched.detected_cves == ("CVE-2026-1234",)
    assert "ransomware" in enriched.categories
    assert "zero_day" in enriched.categories
    assert enriched.risk_score == 100
    assert enriched.is_critical is True
    assert should_alert_telegram(enriched, _config().analysis.decisions) is True
    assert should_include_in_email_digest(enriched, _config().analysis.decisions) is True


def _article(title: str, raw_content: str | None) -> NormalizedArticle:
    """Build a normalized article for analysis tests."""
    return NormalizedArticle(
        title=title,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        content_hash="hash",
        published_at=None,
        source="Example",
        source_id="example",
        raw_content=raw_content,
        summary_placeholder="",
        category_placeholder="",
    )


def _config() -> Config:
    """Build deterministic analysis test config."""
    return Config(
        name="auto-cyber-news",
        environment="test",
        timezone="UTC",
        config_dir=Path("config"),
        database=DatabaseConfig(sqlite_path=Path("data/test.db")),
        logging=LoggingConfig("INFO", "json", False, Path("logs/app.log")),
        http=HttpConfig(5, 0, "test", 2),
        digest=DigestConfig(24, 10, "Test"),
        alerts=AlertConfig(180, True, 6),
        analysis=AnalysisConfig(
            categories=(
                CategoryConfig("ransomware", "Ransomware", ("ransomware",)),
                CategoryConfig("vulnerability", "Vulnerability", ("cve", "vulnerability")),
                CategoryConfig("zero_day", "Zero-Day", ("zero-day",)),
                CategoryConfig("data_breach", "Data Breach", ("breach",)),
                CategoryConfig("cloud_security", "Cloud Security", ("cloud",)),
            ),
            severity_rules=(
                SeverityRuleConfig("active", "Active exploitation", 35, ("actively exploited",)),
                SeverityRuleConfig("ransomware", "Ransomware", 25, ("ransomware",)),
                SeverityRuleConfig("exploit", "Exploit", 20, ("exploit",)),
                SeverityRuleConfig("breach", "Breach", 20, ("breach",)),
            ),
            severity_thresholds=SeverityThresholdConfig(20, 40, 60, 80),
            decisions=DecisionConfig("critical", "medium"),
        ),
        sources=(
            SourceConfig(
                id="example",
                name="Example",
                type="rss",
                enabled=True,
                url="https://example.com/feed",
                homepage="https://example.com",
                poll_interval_minutes=60,
                reliability_weight=1.0,
                category_hints=(),
            ),
        ),
    )
