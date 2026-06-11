"""Rules-based threat categorization.

Matching is word-boundary aware (so ``ai`` does not match ``said`` and ``aws``
does not match ``laws``) and runs over the title and body only — the article
URL is deliberately excluded, since URL tokens (``cloudflare.com``, ``apt-get``,
``/exploit-db/``) otherwise drive off-topic category matches. Each category may
declare ``exclude_keywords`` that suppress it when present.
"""

from __future__ import annotations

import re
from functools import lru_cache

from auto_cyber_news.config.models import CategoryConfig
from auto_cyber_news.models.article import NormalizedArticle


def categorize_article(
    article: NormalizedArticle,
    category_rules: tuple[CategoryConfig, ...],
) -> tuple[str, ...]:
    """Classify an article into zero or more configured threat categories."""
    haystack = _article_text(article)
    categories: list[str] = []
    for category in category_rules:
        if not _matches_any(haystack, category.keywords):
            continue
        if _matches_any(haystack, category.exclude_keywords):
            continue
        categories.append(category.id)
    return tuple(categories)


def _article_text(article: NormalizedArticle) -> str:
    """Return normalized text used by categorization rules (title + body, no URL)."""
    return " ".join(
        value for value in (article.title, article.raw_content) if value is not None
    ).casefold()


def _matches_any(haystack: str, keywords: tuple[str, ...]) -> bool:
    return any(_matches(haystack, keyword) for keyword in keywords)


def _matches(haystack: str, keyword: str) -> bool:
    normalized = keyword.casefold().strip()
    if not normalized:
        return False
    return _pattern(normalized).search(haystack) is not None


@lru_cache(maxsize=512)
def _pattern(keyword: str) -> re.Pattern[str]:
    # Boundaries on alphanumerics so the keyword matches as a whole token/phrase
    # but still allows surrounding punctuation (e.g. "cve" in "cve-2026-1234").
    return re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])")
