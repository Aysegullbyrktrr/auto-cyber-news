"""Tests for content fallback and summary helpers."""

from __future__ import annotations

from auto_cyber_news.parsers.content import extract_summary, resolve_raw_content


def test_extract_summary_truncates_to_200_characters() -> None:
    """Summaries should be deterministic and capped at 200 characters."""
    body = "word " * 80
    assert len(extract_summary(body)) == 200


def test_resolve_raw_content_prefers_summary_over_title() -> None:
    """Summary fallback should be used before title expansion."""
    assert (
        resolve_raw_content(
            primary_content=None,
            summary="Feed summary body",
            title="Short title",
        )
        == "Feed summary body"
    )
