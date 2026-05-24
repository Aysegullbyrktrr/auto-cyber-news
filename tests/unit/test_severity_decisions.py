"""Tests for severity scoring and notification decisions."""

from __future__ import annotations

from auto_cyber_news.analysis.decision import (
    should_alert_telegram,
    should_include_in_email_digest,
)
from auto_cyber_news.analysis.severity import score_article
from auto_cyber_news.config.models import (
    AnalysisConfig,
    CategoryConfig,
    DecisionConfig,
    SeverityThresholdConfig,
)
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle, SeverityLevel


def test_score_article_applies_expanded_category_weights() -> None:
    """Category boosts should include supply chain and vulnerability labels."""
    article = _article(
        title="Supply chain compromise enables malware campaign",
        raw_content="Threat intelligence report on dependency abuse.",
    )
    result = score_article(
        article,
        detected_cves=(),
        categories=("supply_chain", "malware", "threat_intelligence"),
        config=_analysis_config(),
        source_config=None,
    )

    assert result.risk_score >= 28
    assert any(reason.startswith("category:supply_chain") for reason in result.reasons)
    assert any(reason.startswith("category:malware") for reason in result.reasons)
    assert result.reasons[-1].startswith("severity_level:")


def test_supply_chain_campaign_scores_high_with_attack_context() -> None:
    """Active supply-chain worm campaigns should score HIGH/CRITICAL, not LOW."""
    article = _article(
        title="TeamPCP Supply Chain Campaign",
        raw_content=(
            "Researchers detail a Jenkins plugin compromise driving an npm and PyPI "
            "worm propagation wave. The supply chain campaign shows active exploitation "
            "against CI/CD build pipelines."
        ),
    )
    result = score_article(
        article,
        detected_cves=(),
        categories=("supply_chain", "threat_intelligence"),
        config=_analysis_config(),
        source_config=None,
    )

    assert result.risk_score >= 70
    assert result.level in {SeverityLevel.HIGH, SeverityLevel.CRITICAL}
    assert any("context:supply_chain+compromise" in reason for reason in result.reasons)
    assert any("context:worm" in reason for reason in result.reasons)
    assert any("context:npm+pypi" in reason for reason in result.reasons)


def test_decision_layer_considers_cves_and_urgent_categories() -> None:
    """Decisions should use risk score and CVEs beyond configured minimum levels."""
    enriched = _enriched(
        severity=SeverityLevel.MEDIUM,
        risk_score=72,
        categories=("vulnerability",),
        detected_cves=("CVE-2026-0001",),
        reasons=("detected_cves:1(+15)", "final_score:72"),
    )
    decisions = DecisionConfig("critical", "high")

    assert should_alert_telegram(enriched, decisions) is True
    assert should_include_in_email_digest(enriched, decisions) is True


def _article(title: str, raw_content: str) -> NormalizedArticle:
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


def _analysis_config() -> AnalysisConfig:
    return AnalysisConfig(
        categories=(
            CategoryConfig("supply_chain", "Supply Chain", ("supply chain",)),
            CategoryConfig("malware", "Malware", ("malware",)),
            CategoryConfig(
                "threat_intelligence",
                "Threat Intelligence",
                ("threat intelligence",),
            ),
        ),
        severity_rules=(),
        severity_thresholds=SeverityThresholdConfig(20, 40, 60, 80),
        decisions=DecisionConfig("critical", "medium"),
    )


def _enriched(
    *,
    severity: SeverityLevel,
    risk_score: int,
    categories: tuple[str, ...],
    detected_cves: tuple[str, ...],
    reasons: tuple[str, ...],
) -> EnrichedArticle:
    article = _article("Test", "content")
    return EnrichedArticle(
        article=article,
        severity=severity,
        detected_cves=detected_cves,
        categories=categories,
        risk_score=risk_score,
        is_critical=severity is SeverityLevel.CRITICAL,
        should_alert_telegram=False,
        should_include_in_email_digest=False,
        severity_reasons=reasons,
    )
