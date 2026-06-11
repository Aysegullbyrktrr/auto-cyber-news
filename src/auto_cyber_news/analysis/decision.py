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

# Telegram is the page-the-human channel, so it stays conservative: only fire
# on an act-now signal (active exploitation), a genuinely high score, or a
# strong indicator (zero-day / CVE / urgent category) that is *already* riding a
# high-risk story. A bare CVE mention or a common category alone is NOT enough —
# that is what previously caused alert fatigue.
_TELEGRAM_HIGH_RISK = 70
_TELEGRAM_CONTEXT_FLOOR = 60
_ZERO_DAY_FLOOR = 40

# Email digest is lower-stakes than a page, so it casts a wider (but still
# floored) net than Telegram.
_EMAIL_RISK_SCORE_THRESHOLD = 45
_EMAIL_CONTEXT_FLOOR = 40

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
# Active, in-the-wild exploitation is the strongest "act now" SOC signal and is
# always alert-worthy regardless of the numeric score, so it is never missed.
_ACTIVE_EXPLOITATION_PREFIXES = (
    "keyword:exploit-in-the-wild",
    "rule:active_exploitation",
    "rule:active",
)


def should_alert_telegram(article: EnrichedArticle, decisions: DecisionConfig) -> bool:
    """Return whether an enriched article should trigger Telegram alerting."""
    if _meets_minimum(article.severity, decisions.telegram_alert_min_level):
        return True
    if _has_reason_prefix(article, *_ACTIVE_EXPLOITATION_PREFIXES):
        return True
    if article.risk_score >= _TELEGRAM_HIGH_RISK:
        return True
    if (
        _has_reason_prefix(article, *_ZERO_DAY_REASON_PREFIXES)
        and article.risk_score >= _ZERO_DAY_FLOOR
    ):
        return True
    if article.detected_cves and article.risk_score >= _TELEGRAM_CONTEXT_FLOOR:
        return True
    return (
        _has_normalized_category(article, _URGENT_CATEGORIES)
        and article.risk_score >= _TELEGRAM_CONTEXT_FLOOR
    )


def should_include_in_email_digest(article: EnrichedArticle, decisions: DecisionConfig) -> bool:
    """Return whether an enriched article should be included in an email digest."""
    if _meets_minimum(article.severity, decisions.email_digest_min_level):
        return True
    if _has_reason_prefix(article, *_ACTIVE_EXPLOITATION_PREFIXES, *_ZERO_DAY_REASON_PREFIXES):
        return True
    if article.risk_score >= _EMAIL_RISK_SCORE_THRESHOLD:
        return True
    if article.detected_cves and article.risk_score >= _EMAIL_CONTEXT_FLOOR:
        return True
    return (
        _has_normalized_category(article, _URGENT_CATEGORIES)
        and article.risk_score >= _EMAIL_CONTEXT_FLOOR
    )


def _meets_minimum(level: SeverityLevel, minimum_level: str) -> bool:
    """Compare severity levels by configured minimum threshold."""
    try:
        configured = SeverityLevel(minimum_level.strip().casefold())
    except ValueError:
        configured = SeverityLevel.CRITICAL
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
