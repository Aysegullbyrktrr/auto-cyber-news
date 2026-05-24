"""Rules-based threat categorization."""

from __future__ import annotations

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
        if any(keyword.casefold() in haystack for keyword in category.keywords):
            categories.append(category.id)
    return tuple(categories)


def _article_text(article: NormalizedArticle) -> str:
    """Return normalized text used by categorization rules."""
    return " ".join(
        value for value in (article.title, article.raw_content, article.url) if value is not None
    ).casefold()
