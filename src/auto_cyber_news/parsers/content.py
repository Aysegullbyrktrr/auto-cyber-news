"""Content extraction and fallback helpers."""

from __future__ import annotations

from auto_cyber_news.parsers.text_clean import normalize_optional_text

SUMMARY_MAX_LENGTH = 200
UNCATEGORIZED_LABEL = "uncategorized"


def resolve_raw_content(
    *,
    primary_content: str | None,
    summary: str | None,
    title: str,
) -> str:
    """Resolve article body text using content, summary, then title expansion."""
    for candidate in (primary_content, summary):
        normalized = normalize_optional_text(candidate)
        if normalized:
            return normalized
    return expand_title_fallback(title)


def expand_title_fallback(title: str) -> str:
    """Use the article title as minimal body text when no feed content exists."""
    normalized = normalize_optional_text(title)
    return normalized or "Untitled article"


def extract_summary(text: str) -> str:
    """Build a deterministic summary from the first 200 characters of body text."""
    normalized = normalize_optional_text(text)
    if not normalized:
        return ""
    if len(normalized) <= SUMMARY_MAX_LENGTH:
        return normalized
    return normalized[:SUMMARY_MAX_LENGTH]


def format_category_placeholder(categories: tuple[str, ...]) -> str:
    """Format detected categories or fall back to uncategorized."""
    if not categories:
        return UNCATEGORIZED_LABEL
    return ", ".join(categories)
