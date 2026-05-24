"""Shared analysis text utilities."""

from __future__ import annotations

from auto_cyber_news.models.article import NormalizedArticle


def build_analysis_text(article: NormalizedArticle) -> str:
    """Build best-effort text for scoring."""

    parts = [
        article.title,
        article.raw_content,
        article.url,
    ]

    return " ".join(p for p in parts if p).strip().casefold()
