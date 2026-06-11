"""Tests for deterministic intelligence analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_cyber_news.analysis.categorize import categorize_article
from auto_cyber_news.analysis.cve import extract_cves, extract_cvss_score
from auto_cyber_news.analysis.decision import (
    should_alert_telegram,
    should_include_in_email_digest,
)
from auto_cyber_news.analysis.enrich import enrich_article
from auto_cyber_news.analysis.summarize import (
    _extract_gemini_text,
    _gemini_retry_delay,
    _parse_gemini_retry_delay,
    summarize_article,
)
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


def test_extract_cves_rejects_out_of_range_years() -> None:
    """CVE extraction should ignore implausible years like 0000/9999."""
    assert extract_cves("CVE-0000-1234 CVE-9999-12345 CVE-2026-1234") == ("CVE-2026-1234",)


def test_gemini_retry_delay_honors_api_hint_and_caps() -> None:
    """429 backoff should use the API's retryDelay, capped, else exponential."""
    hinted = json.dumps(
        {"error": {"code": 429, "details": [{"@type": "RetryInfo", "retryDelay": "7s"}]}}
    )
    assert _parse_gemini_retry_delay(hinted) == 7
    assert _gemini_retry_delay(hinted, 0) == 7.0

    huge = json.dumps({"error": {"details": [{"retryDelay": "600s"}]}})
    assert _gemini_retry_delay(huge, 0) == 30.0

    assert _parse_gemini_retry_delay("not json") is None
    assert _gemini_retry_delay("not json", 2) == 4.0


def test_extract_cvss_score_picks_base_score() -> None:
    """CVSS extraction should return the base score, not the vector version."""
    assert extract_cvss_score("Flaw rated CVSS 9.8 critical") == 9.8
    assert extract_cvss_score("CVSS:3.1 vector with base score 7.5 high") == 7.5
    assert extract_cvss_score("No score is mentioned here") is None


def test_high_cvss_advisory_scores_high_without_buzzwords() -> None:
    """A high-CVSS CVE advisory must score HIGH even without sensational wording."""
    enriched = enrich_article(
        _article(
            title="CVE-2026-7777 in Acme Gateway rated CVSS 9.8",
            raw_content="A remote code execution issue. A patch is available.",
        ),
        _config(),
    )

    assert enriched.risk_score >= 60
    assert enriched.severity in {SeverityLevel.HIGH, SeverityLevel.CRITICAL}
    assert any(reason.startswith("cvss:") for reason in enriched.severity_reasons)
    assert should_alert_telegram(enriched, _config().analysis.decisions) is True


def _url_article(
    title: str, raw_content: str, url: str = "https://example.com/story"
) -> NormalizedArticle:
    return NormalizedArticle(
        title=title,
        url=url,
        canonical_url=url,
        content_hash="hash",
        published_at=None,
        source="Example",
        source_id="example",
        raw_content=raw_content,
        summary_placeholder="",
        category_placeholder="",
    )


def test_categorize_word_boundary_url_and_exclusion() -> None:
    """Categorization matches whole words, ignores the URL, and honors exclusions."""
    rules = (
        CategoryConfig("cloud_security", "Cloud", ("aws", "cloud")),
        CategoryConfig("nation_state", "Nation", ("apt",), ("apt-get",)),
        CategoryConfig("ai_security", "AI", ("ai",)),
    )

    # Substrings inside other words must NOT match ("laws" / "said").
    assert categorize_article(_url_article("New laws said to be ready", ""), rules) == ()

    # Keywords appearing only in the URL must NOT match.
    assert (
        categorize_article(
            _url_article("Generic product update", "nothing here", "https://aws.amazon.com/cloud"),
            rules,
        )
        == ()
    )

    # Genuine whole-word matches.
    assert "nation_state" in categorize_article(_url_article("APT group hits banks", ""), rules)
    assert "cloud_security" in categorize_article(_url_article("AWS S3 bucket exposed", ""), rules)

    # Exclusion suppresses the false positive (apt-get tutorial is not nation-state).
    assert "nation_state" not in categorize_article(
        _url_article("Using apt-get on Ubuntu", "run apt-get update"),
        rules,
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
    assert enriched.ai_summary == "A data breach campaign is underway."
    assert enriched.is_critical is True
    assert should_alert_telegram(enriched, _config().analysis.decisions) is True
    assert should_include_in_email_digest(enriched, _config().analysis.decisions) is True


async def test_summarize_article_uses_rule_based_fallback_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no provider key set, summarization must not call any API."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    content = "A remote code execution flaw was disclosed. A patch is available now. Rotate keys."
    article = _article(title="Critical RCE disclosed", raw_content=content)

    summary = await summarize_article(article)

    assert summary == content


def test_extract_gemini_text_parses_candidate() -> None:
    """Gemini response parsing should pull and clean the candidate summary text."""
    response = {
        "candidates": [
            {"content": {"parts": [{"text": "Actively exploited RCE. "}, {"text": "Patch now."}]}},
        ],
    }
    assert _extract_gemini_text(response) == "Actively exploited RCE. Patch now."
    assert _extract_gemini_text({"candidates": []}) == ""
    assert _extract_gemini_text("not a dict") == ""


def test_enrich_article_adds_rule_based_summary_for_missing_api_key() -> None:
    """Enrichment should always include an AI summary field with fallback content."""
    enriched = enrich_article(
        _article(
            title="Supply chain exploit hits CI/CD systems",
            raw_content=(
                "Attackers compromised a build pipeline. "
                "The campaign affects npm packages. "
                "Organizations should rotate credentials. "
                "A fourth sentence is omitted."
            ),
        ),
        _config(),
    )

    assert enriched.ai_summary == (
        "Attackers compromised a build pipeline. "
        "The campaign affects npm packages. "
        "Organizations should rotate credentials."
    )


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
