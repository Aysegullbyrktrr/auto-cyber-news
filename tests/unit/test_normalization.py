"""Tests for article normalization and pre-DB deduplication."""

from __future__ import annotations

from auto_cyber_news.models.article import RawFeedItem
from auto_cyber_news.models.source import Source
from auto_cyber_news.parsers.canonical_url import canonicalize_url
from auto_cyber_news.parsers.content import extract_summary
from auto_cyber_news.parsers.normalizer import normalize_item
from auto_cyber_news.parsers.text_clean import clean_title
from auto_cyber_news.pipeline.deduplicate import deduplicate_articles


def test_canonicalize_url_strips_tracking_parameters() -> None:
    """Canonical URLs should drop common tracking query parameters."""
    canonical_url = canonicalize_url(
        "https://www.example.com/news/?utm_source=x&b=2&a=1&ref=feed#section",
    )

    assert canonical_url == "https://example.com/news?a=1&b=2"


def test_normalize_item_returns_standard_article_schema() -> None:
    """Normalizer should produce the standard article schema."""
    source = Source(id="example", name="Example", type="rss", url="https://example.com/feed")
    article = normalize_item(
        source,
        RawFeedItem(
            title=" New vulnerability ",
            url="https://example.com/news?utm_campaign=test",
            published_at="2026-05-24T08:00:00+00:00",
            raw_content="Raw content",
        ),
    )

    assert article.title == "New vulnerability"
    assert article.url == "https://example.com/news?utm_campaign=test"
    assert article.canonical_url == "https://example.com/news"
    assert article.source == "Example"
    assert article.source_id == "example"
    assert article.raw_content == "Raw content"
    assert article.summary_placeholder == extract_summary("Raw content")
    assert article.category_placeholder == "uncategorized"


def test_normalize_item_falls_back_to_summary_when_content_missing() -> None:
    """Empty primary content should fall back to feed summary text."""
    source = Source(id="example", name="Example", type="rss", url="https://example.com/feed")
    article = normalize_item(
        source,
        RawFeedItem(
            title="Supply chain alert",
            url="https://example.com/alert",
            published_at=None,
            raw_content=None,
            summary="Summary from the feed description field.",
        ),
    )

    assert article.raw_content == "Summary from the feed description field."
    assert article.summary_placeholder == extract_summary(article.raw_content)


def test_normalize_item_falls_back_to_title_when_body_missing() -> None:
    """Articles without body text should use the title as minimal content."""
    source = Source(id="example", name="Example", type="rss", url="https://example.com/feed")
    article = normalize_item(
        source,
        RawFeedItem(
            title="Same story",
            url="https://example.com/story?utm_source=a",
            published_at=None,
            raw_content=None,
            summary=None,
        ),
    )

    assert article.raw_content == "Same story"
    assert article.summary_placeholder == "Same story"


def test_clean_title_decodes_entities_and_extra_commas() -> None:
    """Titles should decode HTML entities and collapse stray commas."""
    title = clean_title("Alert &#x5b;CVE-2026-1234&#x5d;, , follow-up")
    assert title == "Alert [CVE-2026-1234], follow-up"


def test_deduplicate_articles_uses_canonical_url() -> None:
    """Deduplication should remove duplicate canonical URLs."""
    source = Source(id="example", name="Example", type="rss", url="https://example.com/feed")
    first = normalize_item(
        source,
        RawFeedItem(
            title="Same story",
            url="https://example.com/story?utm_source=a",
            published_at=None,
            raw_content=None,
        ),
    )
    second = normalize_item(
        source,
        RawFeedItem(
            title="Same story",
            url="https://www.example.com/story?ref=b",
            published_at=None,
            raw_content=None,
        ),
    )

    assert deduplicate_articles([first, second]) == [first]
