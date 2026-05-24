"""Article enrichment orchestration."""

from __future__ import annotations

from dataclasses import replace

from auto_cyber_news.analysis.categorize import categorize_article
from auto_cyber_news.analysis.cve import extract_cves
from auto_cyber_news.analysis.decision import (
    should_alert_telegram,
    should_include_in_email_digest,
)
from auto_cyber_news.analysis.severity import score_article
from auto_cyber_news.config.models import Config, SourceConfig
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle, SeverityLevel
from auto_cyber_news.parsers.content import format_category_placeholder


def enrich_article(article: NormalizedArticle, config: Config) -> EnrichedArticle:
    """Enrich a normalized article with deterministic intelligence fields."""

    detected_cves = extract_cves(
        article.title,
        article.raw_content,
        article.url,
    )

    categories = categorize_article(
        article,
        config.analysis.categories,
    )
    article = replace(
        article,
        category_placeholder=format_category_placeholder(categories),
    )

    severity_score = score_article(
        article,
        detected_cves=detected_cves,
        categories=categories,
        config=config.analysis,
        source_config=_find_source(article.source_id, config.sources),
    )

    initial = EnrichedArticle(
        article=article,
        severity=severity_score.level,
        detected_cves=detected_cves,
        categories=categories,
        risk_score=severity_score.risk_score,
        is_critical=severity_score.level is SeverityLevel.CRITICAL,
        should_alert_telegram=False,
        should_include_in_email_digest=False,
        severity_reasons=severity_score.reasons,
    )

    return replace(
        initial,
        should_alert_telegram=should_alert_telegram(
            initial,
            config.analysis.decisions,
        ),
        should_include_in_email_digest=should_include_in_email_digest(
            initial,
            config.analysis.decisions,
        ),
    )


def enrich_articles(
    articles: tuple[NormalizedArticle, ...],
    config: Config,
) -> tuple[EnrichedArticle, ...]:
    """Enrich multiple normalized articles."""
    return tuple(enrich_article(article, config) for article in articles)


def _find_source(
    source_id: str,
    sources: tuple[SourceConfig, ...],
) -> SourceConfig | None:
    """Find a configured source by id."""
    for source in sources:
        if source.id == source_id:
            return source
    return None
