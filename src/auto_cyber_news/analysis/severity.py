"""Rules-based severity scoring."""

from __future__ import annotations

from dataclasses import dataclass

from auto_cyber_news.analysis.text import build_analysis_text
from auto_cyber_news.config.models import AnalysisConfig, SourceConfig
from auto_cyber_news.models.article import NormalizedArticle, SeverityLevel, SeverityScore

CVE_WEIGHT = 15
ZERO_DAY_WEIGHT = 25
EXPLOIT_IN_THE_WILD_WEIGHT = 35

# Category boosts (keys are normalized category ids).
CATEGORY_WEIGHTS: dict[str, int] = {
    "malware": 8,
    "ransomware": 12,
    "supply_chain": 14,
    "threat_intelligence": 6,
    "vulnerability": 10,
    "zero_day": 18,
    "exploit": 12,
    "data_breach": 10,
}

# Active-attack context combo bonuses.
CONTEXT_SUPPLY_CHAIN_COMPROMISE_BONUS = 25
CONTEXT_WORM_BONUS = 20
CONTEXT_CICD_COMPROMISE_BONUS = 20
CONTEXT_MULTI_ECOSYSTEM_BONUS = 15
CONTEXT_SUPPLY_CHAIN_CAMPAIGN_BONUS = 12
CONTEXT_COMPROMISE_BONUS = 10
CONTEXT_CICD_BONUS = 8


@dataclass(frozen=True)
class _AttackSignals:
    """Detected attack-context indicators from article text and categories."""

    supply_chain: bool
    compromise: bool
    worm: bool
    cicd: bool
    npm: bool
    pypi: bool
    campaign: bool


def score_article(
    article: NormalizedArticle,
    *,
    detected_cves: tuple[str, ...],
    categories: tuple[str, ...],
    config: AnalysisConfig,
    source_config: SourceConfig | None,
) -> SeverityScore:
    """Score an article using deterministic rules."""

    score = 0
    reasons: list[str] = []

    haystack = build_analysis_text(article)
    normalized_categories = tuple(_normalize_category_id(category) for category in categories)

    if detected_cves:
        score += CVE_WEIGHT
        reasons.append(f"detected_cves:{len(detected_cves)}(+{CVE_WEIGHT})")

    if "zero-day" in haystack or "0-day" in haystack or "zero day" in haystack:
        score += ZERO_DAY_WEIGHT
        reasons.append(f"keyword:zero-day(+{ZERO_DAY_WEIGHT})")

    if _has_exploit_in_the_wild(haystack):
        score += EXPLOIT_IN_THE_WILD_WEIGHT
        reasons.append(f"keyword:exploit-in-the-wild(+{EXPLOIT_IN_THE_WILD_WEIGHT})")

    for rule in config.severity_rules:
        if any(term.casefold() in haystack for term in rule.terms):
            score += rule.weight
            reasons.append(f"rule:{rule.id}(+{rule.weight})")

    category_boost = _category_boost_score(normalized_categories, reasons)
    score += category_boost

    context_boost = _attack_context_boost(haystack, normalized_categories, reasons)
    score += context_boost

    if source_config is not None:
        weighted_score = int(round(score * source_config.reliability_weight))
        if weighted_score != score:
            reasons.append(f"source_weight:{source_config.reliability_weight}")
        score = weighted_score

    bounded_score = max(0, min(score, 100))
    level = _level_for_score(bounded_score, config)
    reasons.append(f"final_score:{bounded_score}")
    reasons.append(f"severity_level:{level.value}")

    return SeverityScore(
        level=level,
        risk_score=bounded_score,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _attack_context_boost(
    haystack: str,
    normalized_categories: tuple[str, ...],
    reasons: list[str],
) -> int:
    """Apply active-attack context scoring for real-world SOC-relevant threats."""
    signals = _detect_attack_signals(haystack, normalized_categories)
    boost = 0

    if signals.supply_chain and signals.compromise:
        boost += CONTEXT_SUPPLY_CHAIN_COMPROMISE_BONUS
        reasons.append(f"context:supply_chain+compromise(+{CONTEXT_SUPPLY_CHAIN_COMPROMISE_BONUS})")

    if signals.worm:
        boost += CONTEXT_WORM_BONUS
        reasons.append(f"context:worm(+{CONTEXT_WORM_BONUS})")

    if signals.cicd and signals.compromise:
        boost += CONTEXT_CICD_COMPROMISE_BONUS
        reasons.append(f"context:cicd+compromise(+{CONTEXT_CICD_COMPROMISE_BONUS})")

    if signals.npm and signals.pypi:
        boost += CONTEXT_MULTI_ECOSYSTEM_BONUS
        reasons.append(f"context:npm+pypi(+{CONTEXT_MULTI_ECOSYSTEM_BONUS})")

    if signals.supply_chain and signals.campaign:
        boost += CONTEXT_SUPPLY_CHAIN_CAMPAIGN_BONUS
        reasons.append(f"context:supply_chain_campaign(+{CONTEXT_SUPPLY_CHAIN_CAMPAIGN_BONUS})")

    if signals.compromise and not (signals.supply_chain and signals.compromise):
        boost += CONTEXT_COMPROMISE_BONUS
        reasons.append(f"context:compromise(+{CONTEXT_COMPROMISE_BONUS})")

    if signals.cicd and not (signals.cicd and signals.compromise):
        boost += CONTEXT_CICD_BONUS
        reasons.append(f"context:cicd(+{CONTEXT_CICD_BONUS})")

    return boost


def _detect_attack_signals(
    haystack: str,
    normalized_categories: tuple[str, ...],
) -> _AttackSignals:
    """Detect compromise, worm, CI/CD, and ecosystem signals from text and categories."""
    supply_chain = "supply_chain" in normalized_categories or "supply chain" in haystack
    compromise = any(
        term in haystack
        for term in (
            "compromise",
            "compromised",
            "compromising",
            "backdoored",
            "trojanized",
        )
    )
    worm = any(
        term in haystack
        for term in (
            "worm",
            "self-spreading",
            "self spreading",
            "worm propagation",
            "spreads automatically",
        )
    )
    cicd = any(
        term in haystack
        for term in (
            "jenkins",
            "github actions",
            "ci/cd",
            "ci cd",
            "build pipeline",
            "pipeline compromise",
            "ci pipeline",
            "devops pipeline",
        )
    )
    npm = "npm" in haystack
    pypi = "pypi" in haystack or "py pi" in haystack
    campaign = "campaign" in haystack or "attack campaign" in haystack

    return _AttackSignals(
        supply_chain=supply_chain,
        compromise=compromise,
        worm=worm,
        cicd=cicd,
        npm=npm,
        pypi=pypi,
        campaign=campaign,
    )


def _category_boost_score(
    normalized_categories: tuple[str, ...],
    reasons: list[str],
) -> int:
    """Apply configured category weights once per matched category."""
    boost = 0
    seen: set[str] = set()
    for category_id in normalized_categories:
        if category_id in seen:
            continue
        weight = CATEGORY_WEIGHTS.get(category_id)
        if weight is None:
            continue
        seen.add(category_id)
        boost += weight
        reasons.append(f"category:{category_id}(+{weight})")
    return boost


def _normalize_category_id(category: str) -> str:
    """Normalize a category id for case-insensitive matching."""
    return category.strip().casefold().replace("-", "_").replace(" ", "_")


def _level_for_score(score: int, config: AnalysisConfig) -> SeverityLevel:
    """Map a numeric risk score to a severity level."""
    thresholds = config.severity_thresholds

    if score >= thresholds.critical:
        return SeverityLevel.CRITICAL
    if score >= thresholds.high:
        return SeverityLevel.HIGH
    if score >= thresholds.medium:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


def _has_exploit_in_the_wild(haystack: str) -> bool:
    """Return whether text indicates active exploitation."""
    return any(
        phrase in haystack
        for phrase in (
            "actively exploited",
            "exploited in the wild",
            "in the wild",
            "mass exploitation",
            "active exploitation",
            "under active attack",
            "actively attacking",
        )
    )
