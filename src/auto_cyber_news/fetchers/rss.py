"""RSS fetcher implementation."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]

from auto_cyber_news.fetchers.http import AsyncHttpClient
from auto_cyber_news.models.article import RawFeedItem
from auto_cyber_news.models.source import Source
from auto_cyber_news.parsers.text_clean import normalize_optional_text


class FeedParseError(RuntimeError):
    """Raised when a feed cannot be parsed safely."""


class RssFetcher:
    """Async-ready RSS fetcher."""

    def __init__(self, http_client: AsyncHttpClient) -> None:
        self._http_client = http_client

    async def fetch(self, source: Source) -> list[RawFeedItem]:
        """Fetch and parse RSS items from a source."""

        feed_text = await self._http_client.get_text(source.url)
        parsed_feed = feedparser.parse(feed_text)

        if getattr(parsed_feed, "bozo", False) and not getattr(parsed_feed, "entries", []):
            raise FeedParseError(f"Unable to parse feed for source: {source.id}")

        items: list[RawFeedItem] = []

        for entry in parsed_feed.entries:
            item = _entry_to_raw_item(entry)
            if item is not None:
                items.append(item)

        return items


def parse_rss_items(feed_text: str) -> list[RawFeedItem]:
    """Parse RSS or Atom text into raw feed items."""

    parsed_feed = feedparser.parse(feed_text)

    if getattr(parsed_feed, "bozo", False) and not getattr(parsed_feed, "entries", []):
        raise FeedParseError("Unable to parse feed text")

    items: list[RawFeedItem] = []

    for entry in parsed_feed.entries:
        item = _entry_to_raw_item(entry)
        if item is not None:
            items.append(item)

    return items


def _entry_to_raw_item(entry: Any) -> RawFeedItem | None:
    """Convert a feedparser entry into a raw feed item (safe)."""

    title = _clean_text(entry.get("title"))
    url = _clean_text(entry.get("link"))

    if not title or not url:
        return None

    return RawFeedItem(
        title=title,
        url=url,
        published_at=_extract_published_at(entry),
        raw_content=_extract_primary_content(entry),
        summary=_extract_summary(entry),
    )


def _extract_primary_content(entry: Any) -> str | None:
    """Extract full entry content when provided by the feed."""
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value")
        return _clean_text(value)
    return None


def _extract_summary(entry: Any) -> str | None:
    """Extract summary or description fields for content fallback."""
    for field_name in ("summary", "description", "media:description"):
        value = entry.get(field_name)
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _extract_published_at(entry: Any) -> str | None:
    """Extract best-effort ISO timestamp from a feed entry."""

    for field_name in ("published", "updated", "created"):
        raw_value = entry.get(field_name)
        if not raw_value:
            continue
        try:
            return parsedate_to_datetime(str(raw_value)).isoformat()
        except (TypeError, ValueError):
            cleaned = _clean_text(str(raw_value))
            return cleaned

    return None


def _clean_text(value: Any) -> str | None:
    """Safely normalize text fields, treating empty strings as missing."""
    if value is None:
        return None
    return normalize_optional_text(str(value))
