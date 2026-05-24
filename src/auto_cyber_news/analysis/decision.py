"""Decision predicates for notification and digest systems."""

from __future__ import annotations

from auto_cyber_news.config.models import DecisionConfig
from auto_cyber_news.models.article import EnrichedArticle, SeverityLevel

_LEVEL_ORDER = {
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}

_TELEGRAM_RISK_SCORE_THRESHOLD = 70
_EMAIL_RISK_SCORE_THRESHOLD = 45
_URGENT_CATEGORIES = frozenset(
    {
        "zero_day",
        "exploit",
        "ransomware",
        "supply_chain",
        "vulnerability",
    },
)
_ZERO_DAY_REASON_PREFIXES = ("keyword:zero-day", "category:zero_day")
_EXPLOIT_REASON_PREFIXES = ("keyword:exploit-in-the-wild", "category:exploit", "rule:exploit")


def should_alert_telegram(article: EnrichedArticle, decisions: DecisionConfig) -> bool:
    """Return whether an enriched article should trigger Telegram alerting."""
    if _meets_minimum(article.severity, decisions.telegram_alert_min_level):
        return True
    if article.risk_score >= _TELEGRAM_RISK_SCORE_THRESHOLD:
        return True
    if article.detected_cves and _meets_minimum(article.severity, SeverityLevel.HIGH.value):
        return True
    if _has_normalized_category(article, _URGENT_CATEGORIES) and article.risk_score >= 50:
        return True
    if _has_reason_prefix(article, *_ZERO_DAY_REASON_PREFIXES):
        return True
    return _has_reason_prefix(article, *_EXPLOIT_REASON_PREFIXES) and article.risk_score >= 40


def should_include_in_email_digest(article: EnrichedArticle, decisions: DecisionConfig) -> bool:
    """Return whether an enriched article should be included in an email digest."""
    if _meets_minimum(article.severity, decisions.email_digest_min_level):
        return True
    if article.detected_cves and article.risk_score >= _EMAIL_RISK_SCORE_THRESHOLD:
        return True
    if _has_normalized_category(article, _URGENT_CATEGORIES):
        return True
    if article.risk_score >= 55:
        return True
    return _has_reason_prefix(article, *_ZERO_DAY_REASON_PREFIXES, *_EXPLOIT_REASON_PREFIXES)


def _meets_minimum(level: SeverityLevel, minimum_level: str) -> bool:
    """Compare severity levels by configured minimum threshold."""
    configured = SeverityLevel(minimum_level.strip().casefold())
    return _LEVEL_ORDER[level] >= _LEVEL_ORDER[configured]


def _has_normalized_category(article: EnrichedArticle, category_ids: frozenset[str]) -> bool:
    """Return whether any article category matches the given normalized ids."""
    normalized = {category.strip().casefold().replace("-", "_") for category in article.categories}
    return bool(normalized.intersection(category_ids))


def _has_reason_prefix(article: EnrichedArticle, *prefixes: str) -> bool:
    """Return whether any severity reason starts with one of the prefixes."""
    return any(
        reason.startswith(prefix) for reason in article.severity_reasons for prefix in prefixes
    )
