"""In-memory pre-persistence deduplication."""

from __future__ import annotations

from auto_cyber_news.logging import get_logger
from auto_cyber_news.models.article import NormalizedArticle

LOGGER = get_logger(__name__)


def deduplicate_articles(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """Remove duplicate articles by canonical URL and content hash while preserving order."""
    seen_canonical_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique_articles: list[NormalizedArticle] = []

    for article in articles:
        canonical_url = _safe_key(article.canonical_url)
        article_hash = _safe_key(article.content_hash)
        if not canonical_url or not article_hash:
            LOGGER.warning(
                "Article skipped during deduplication because identity fields are missing",
                extra={
                    "title": getattr(article, "title", None),
                    "source_id": getattr(article, "source_id", None),
                },
            )
            continue
        if canonical_url in seen_canonical_urls or article_hash in seen_hashes:
            continue
        seen_canonical_urls.add(canonical_url)
        seen_hashes.add(article_hash)
        unique_articles.append(article)

    return unique_articles


def _safe_key(value: object) -> str:
    """Return a non-empty string key for deduplication."""
    if not isinstance(value, str):
        return ""
    return value.strip()
