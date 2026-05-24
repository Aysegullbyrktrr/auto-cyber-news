"""Async ingestion workflow for fetching and normalizing articles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from auto_cyber_news.config.models import Config, SourceConfig
from auto_cyber_news.fetchers.http import AsyncHttpClient, FetchError, HttpClientConfig
from auto_cyber_news.fetchers.registry import build_http_client, get_fetcher
from auto_cyber_news.logging import get_logger
from auto_cyber_news.models.article import NormalizedArticle
from auto_cyber_news.models.source import Source
from auto_cyber_news.parsers.normalizer import ArticleNormalizationError, normalize_item
from auto_cyber_news.pipeline.deduplicate import deduplicate_articles

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class SourceIngestionResult:
    """Result of processing one configured source."""

    source_id: str
    articles: tuple[NormalizedArticle, ...]
    error: str | None = None


@dataclass(frozen=True)
class IngestionResult:
    """Result of an ingestion run."""

    articles: tuple[NormalizedArticle, ...]
    source_results: tuple[SourceIngestionResult, ...]


async def run_ingestion(
    config: Config,
    *,
    http_client: AsyncHttpClient | None = None,
) -> IngestionResult:
    """Run one ingestion cycle and return normalized, deduplicated articles."""
    enabled_sources = tuple(source for source in config.sources if source.enabled)
    owns_client = http_client is None
    client = http_client or build_http_client(
        HttpClientConfig(
            timeout_seconds=config.http.timeout_seconds,
            total_retries=config.http.total_retries,
            user_agent=config.http.user_agent,
        ),
    )
    semaphore = asyncio.Semaphore(config.http.max_concurrency)

    source_results = await asyncio.gather(
        *(_run_source(source, client, semaphore) for source in enabled_sources),
        return_exceptions=False,
    )
    all_articles = [
        article for source_result in source_results for article in source_result.articles
    ]
    deduplicated_articles = deduplicate_articles(all_articles)

    LOGGER.info(
        "Ingestion completed",
        extra={
            "sources_attempted": len(enabled_sources),
            "sources_failed": sum(1 for result in source_results if result.error is not None),
            "articles_seen": len(all_articles),
            "articles_after_dedup": len(deduplicated_articles),
        },
    )
    result = IngestionResult(
        articles=tuple(deduplicated_articles),
        source_results=tuple(source_results),
    )
    if owns_client:
        await client.close()
    return result


async def _run_source(
    source_config: SourceConfig,
    http_client: AsyncHttpClient,
    semaphore: asyncio.Semaphore,
) -> SourceIngestionResult:
    """Fetch and normalize one source while isolating source failures."""
    source = _source_from_config(source_config)
    async with semaphore:
        try:
            fetcher = get_fetcher(source.type, http_client)
            raw_items = await fetcher.fetch(source)
            articles: list[NormalizedArticle] = []
            for raw_item in raw_items:
                try:
                    articles.append(normalize_item(source, raw_item))
                except ArticleNormalizationError as exc:
                    LOGGER.warning(
                        "Article normalization failed",
                        extra={"source_id": source.id, "error": str(exc)},
                    )
            LOGGER.info(
                "Source ingestion completed",
                extra={
                    "source_id": source.id,
                    "raw_item_count": len(raw_items),
                    "normalized_article_count": len(articles),
                },
            )
            return SourceIngestionResult(source_id=source.id, articles=tuple(articles))
        except (FetchError, ValueError, RuntimeError) as exc:
            LOGGER.error(
                "Source ingestion failed",
                extra={"source_id": source.id, "error": str(exc)},
            )
            return SourceIngestionResult(source_id=source.id, articles=(), error=str(exc))


def _source_from_config(source_config: SourceConfig) -> Source:
    """Convert source configuration into a fetcher domain source."""
    return Source(
        id=source_config.id,
        name=source_config.name,
        type=source_config.type,
        url=source_config.url,
        enabled=source_config.enabled,
        poll_interval_minutes=source_config.poll_interval_minutes,
    )
