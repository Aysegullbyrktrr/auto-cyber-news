"""Article normalization."""

from __future__ import annotations

from auto_cyber_news.models.article import NormalizedArticle, RawFeedItem
from auto_cyber_news.models.source import Source
from auto_cyber_news.parsers.canonical_url import canonicalize_url
from auto_cyber_news.parsers.content import (
    UNCATEGORIZED_LABEL,
    extract_summary,
    resolve_raw_content,
)
from auto_cyber_news.parsers.text_clean import clean_title, normalize_optional_text
from auto_cyber_news.utils.hashing import content_hash


class ArticleNormalizationError(ValueError):
    """Raised when a raw feed item cannot be normalized."""


def normalize_item(source: Source, item: RawFeedItem) -> NormalizedArticle:
    """Normalize a raw source item into a standard article schema."""

    title = clean_title(_required_text(item.title, "title"))
    url = _required_text(item.url, "url")
    canonical_url = canonicalize_url(url)

    raw_content = resolve_raw_content(
        primary_content=item.raw_content,
        summary=item.summary,
        title=title,
    )
    summary_placeholder = extract_summary(raw_content)

    return NormalizedArticle(
        title=title,
        url=url,
        canonical_url=canonical_url,
        content_hash=content_hash(f"{source.id}|{title}|{canonical_url}"),
        published_at=normalize_optional_text(item.published_at),
        source=source.name,
        source_id=source.id,
        raw_content=raw_content,
        summary_placeholder=summary_placeholder,
        category_placeholder=UNCATEGORIZED_LABEL,
    )


def _required_text(value: str, field_name: str) -> str:
    """Return stripped text or raise when required text is missing."""
    if value is None:
        raise ArticleNormalizationError(f"Missing required article field: {field_name}")

    stripped = value.strip()
    if not stripped:
        raise ArticleNormalizationError(f"Missing required article field: {field_name}")

    return stripped
