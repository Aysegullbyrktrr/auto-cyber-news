"""Article enrichment orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from auto_cyber_news.analysis.categorize import categorize_article
from auto_cyber_news.analysis.cve import extract_cves
from auto_cyber_news.analysis.decision import (
    should_alert_telegram,
    should_include_in_email_digest,
)
from auto_cyber_news.analysis.severity import score_article
from auto_cyber_news.analysis.summarize import summarize_article, summarize_article_rule_based
from auto_cyber_news.config.models import Config, SourceConfig
from auto_cyber_news.logging import get_logger
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle, SeverityLevel
from auto_cyber_news.parsers.content import format_category_placeholder

LOGGER = get_logger(__name__)


def enrich_article(article: NormalizedArticle, config: Config) -> EnrichedArticle:
    """Enrich a normalized article with deterministic intelligence fields."""
    return _build_enriched_article(
        article,
        config,
        ai_summary=summarize_article_rule_based(article),
    )


async def enrich_article_async(article: NormalizedArticle, config: Config) -> EnrichedArticle:
    """Enrich a normalized article with deterministic intelligence and AI summary."""
    ai_summary = await summarize_article(article)
    return _build_enriched_article(article, config, ai_summary=ai_summary)


def _build_enriched_article(
    article: NormalizedArticle,
    config: Config,
    *,
    ai_summary: str,
) -> EnrichedArticle:
    """Build one enriched article from normalized input and a prepared summary."""

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
        ai_summary=ai_summary,
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
    enriched_articles: list[EnrichedArticle] = []
    for article in articles:
        try:
            enriched_articles.append(enrich_article(article, config))
        except Exception as exc:
            LOGGER.error(
                "Article enrichment failed",
                extra={
                    "title": getattr(article, "title", None),
                    "source_id": getattr(article, "source_id", None),
                    "error": str(exc),
                },
            )
    return tuple(enriched_articles)


async def enrich_articles_async(
    articles: tuple[NormalizedArticle, ...],
    config: Config,
) -> tuple[EnrichedArticle, ...]:
    """Enrich multiple normalized articles while isolating per-article failures."""
    if not articles:
        return ()

    semaphore = asyncio.Semaphore(4)

    async def enrich_guarded(article: NormalizedArticle) -> EnrichedArticle | None:
        async with semaphore:
            try:
                return await enrich_article_async(article, config)
            except Exception as exc:
                LOGGER.error(
                    "Article enrichment failed",
                    extra={
                        "title": getattr(article, "title", None),
                        "source_id": getattr(article, "source_id", None),
                        "error": str(exc),
                    },
                )
                return None

    results = await asyncio.gather(*(enrich_guarded(article) for article in articles))
    return tuple(article for article in results if article is not None)


def _find_source(
    source_id: str,
    sources: tuple[SourceConfig, ...],
) -> SourceConfig | None:
    """Find a configured source by id."""
    for source in sources:
        if source.id == source_id:
            return source
    return None
