"""In-memory pre-persistence deduplication."""

from __future__ import annotations

from auto_cyber_news.models.article import NormalizedArticle


def deduplicate_articles(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """Remove duplicate articles by canonical URL and content hash while preserving order."""
    seen_canonical_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique_articles: list[NormalizedArticle] = []

    for article in articles:
        if article.canonical_url in seen_canonical_urls or article.content_hash in seen_hashes:
            continue
        seen_canonical_urls.add(article.canonical_url)
        seen_hashes.add(article.content_hash)
        unique_articles.append(article)

    return unique_articles


def deduplicate() -> None:
    """Compatibility placeholder for future persisted deduplication workflows."""
    raise NotImplementedError("Persisted deduplication is not implemented yet.")
