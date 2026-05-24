"""Security incident domain models."""

from __future__ import annotations

from dataclasses import dataclass

from auto_cyber_news.models.article import EnrichedArticle, SeverityLevel


@dataclass(frozen=True)
class SecurityIncident:
    """Grouped security event spanning one or more related articles."""

    incident_id: str
    title: str
    articles: tuple[EnrichedArticle, ...]
    max_severity: SeverityLevel
    max_risk_score: int
    sources: tuple[str, ...]
    categories: tuple[str, ...]
    detected_cves: tuple[str, ...]

    @property
    def article_count(self) -> int:
        """Return the number of articles in this incident."""
        return len(self.articles)

    def should_alert_telegram(self) -> bool:
        """Return whether any grouped article qualifies for Telegram alerting."""
        return any(article.should_alert_telegram for article in self.articles)

    def should_include_in_email_digest(self) -> bool:
        """Return whether any grouped article qualifies for email digest inclusion."""
        return any(article.should_include_in_email_digest for article in self.articles)
