"""Article domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


@dataclass(frozen=True)
class RawFeedItem:
    """Raw parsed item from an RSS or Atom feed."""

    title: str
    url: str
    published_at: str | None
    raw_content: str | None
    summary: str | None = None


@dataclass(frozen=True)
class NormalizedArticle:
    """Normalized article prepared for downstream persistence or enrichment."""

    title: str
    url: str
    canonical_url: str
    content_hash: str
    published_at: str | None
    source: str
    source_id: str
    raw_content: str | None
    summary_placeholder: str
    category_placeholder: str

    def to_dict(self) -> dict[str, object]:
        """Convert the article into a JSON-serializable dictionary."""
        return asdict(self)


class SeverityLevel(str, Enum):  # noqa: UP042
    """Supported severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SeverityScore:
    """Rules-based severity scoring result."""

    level: SeverityLevel
    risk_score: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the severity score into a JSON-serializable dictionary."""
        return {
            "level": self.level.value,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class EnrichedArticle:
    """Normalized article with deterministic intelligence enrichment."""

    article: NormalizedArticle
    severity: SeverityLevel
    detected_cves: tuple[str, ...]
    categories: tuple[str, ...]
    risk_score: int
    is_critical: bool
    should_alert_telegram: bool
    should_include_in_email_digest: bool
    severity_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the enriched article into a JSON-serializable dictionary."""
        payload = self.article.to_dict()
        payload.update(
            {
                "severity": self.severity.value,
                "detected_cves": list(self.detected_cves),
                "categories": list(self.categories),
                "risk_score": self.risk_score,
                "is_critical": self.is_critical,
                "should_alert_telegram": self.should_alert_telegram,
                "should_include_in_email_digest": self.should_include_in_email_digest,
                "severity_reasons": list(self.severity_reasons),
            },
        )
        return payload
