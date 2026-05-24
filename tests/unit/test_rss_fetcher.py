"""Tests for RSS parsing."""

from __future__ import annotations

from auto_cyber_news.fetchers.rss import parse_rss_items


def test_parse_rss_items_extracts_standard_fields() -> None:
    """RSS parsing should extract title, link, published time, and content."""
    items = parse_rss_items(
        """
        <rss version="2.0">
          <channel>
            <title>Example Feed</title>
            <item>
              <title>Critical CVE exploited</title>
              <link>https://example.com/story?utm_source=newsletter</link>
              <pubDate>Sun, 24 May 2026 08:00:00 GMT</pubDate>
              <description>Example summary</description>
            </item>
          </channel>
        </rss>
        """,
    )

    assert len(items) == 1
    assert items[0].title == "Critical CVE exploited"
    assert items[0].url == "https://example.com/story?utm_source=newsletter"
    assert items[0].published_at == "2026-05-24T08:00:00+00:00"
    assert items[0].summary == "Example summary"
    assert items[0].raw_content is None
