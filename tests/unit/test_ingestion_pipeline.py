"""Tests for async ingestion orchestration."""

from __future__ import annotations

import pytest

from auto_cyber_news.config.models import (
    AlertConfig,
    AnalysisConfig,
    Config,
    DatabaseConfig,
    DecisionConfig,
    DigestConfig,
    HttpConfig,
    LoggingConfig,
    SeverityThresholdConfig,
    SourceConfig,
)
from auto_cyber_news.fetchers.http import AsyncHttpClient
from auto_cyber_news.pipeline.ingest import run_ingestion


@pytest.mark.asyncio
async def test_run_ingestion_normalizes_and_deduplicates_mocked_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline should fetch configured feeds and return deduplicated articles."""
    monkeypatch.setattr(AsyncHttpClient, "get_text", _mock_get_text)
    config = _config(
        sources=(
            SourceConfig(
                id="example",
                name="Example",
                type="rss",
                enabled=True,
                url="https://example.com/feed.xml",
                homepage="https://example.com",
                poll_interval_minutes=60,
                reliability_weight=1.0,
                category_hints=(),
            ),
        ),
    )

    result = await run_ingestion(config)

    assert len(result.articles) == 1
    assert result.articles[0].title == "Critical CVE exploited"
    assert result.articles[0].canonical_url == "https://example.com/story"
    assert result.source_results[0].error is None


@pytest.mark.asyncio
async def test_run_ingestion_isolates_source_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """One source failure should not fail the whole ingestion run."""
    monkeypatch.setattr(AsyncHttpClient, "get_text", _mock_get_text)
    config = _config(
        sources=(
            SourceConfig(
                id="good",
                name="Good",
                type="rss",
                enabled=True,
                url="https://example.com/feed.xml",
                homepage="https://example.com",
                poll_interval_minutes=60,
                reliability_weight=1.0,
                category_hints=(),
            ),
            SourceConfig(
                id="bad",
                name="Bad",
                type="html",
                enabled=True,
                url="https://bad.example.com/",
                homepage="https://bad.example.com",
                poll_interval_minutes=60,
                reliability_weight=1.0,
                category_hints=(),
            ),
        ),
    )

    result = await run_ingestion(config)

    assert len(result.articles) == 1
    assert result.source_results[0].error is None
    assert result.source_results[1].error is not None


async def _mock_get_text(self: AsyncHttpClient, url: str) -> str:
    """Return a mocked RSS feed for ingestion tests."""
    return """
    <rss version="2.0">
      <channel>
        <title>Example Feed</title>
        <item>
          <title>Critical CVE exploited</title>
          <link>https://example.com/story?utm_source=newsletter</link>
          <pubDate>Sun, 24 May 2026 08:00:00 GMT</pubDate>
          <description>Example summary</description>
        </item>
        <item>
          <title>Critical CVE exploited</title>
          <link>https://www.example.com/story?ref=feed</link>
          <pubDate>Sun, 24 May 2026 08:00:00 GMT</pubDate>
          <description>Duplicate summary</description>
        </item>
      </channel>
    </rss>
    """


def _config(*, sources: tuple[SourceConfig, ...]) -> Config:
    """Build a test config with a mocked feed URL."""
    from pathlib import Path

    return Config(
        name="auto-cyber-news",
        environment="test",
        timezone="UTC",
        config_dir=Path("config"),
        database=DatabaseConfig(sqlite_path=Path("data/test.db")),
        logging=LoggingConfig(
            level="INFO",
            format="json",
            file_enabled=False,
            file_path=Path("logs/app.log"),
        ),
        http=HttpConfig(
            timeout_seconds=5,
            total_retries=0,
            user_agent="auto-cyber-news/test",
            max_concurrency=2,
        ),
        digest=DigestConfig(window_hours=24, max_articles=10, subject_prefix="Test"),
        alerts=AlertConfig(critical_freshness_minutes=180, dry_run=True, alert_cooldown_hours=6),
        analysis=AnalysisConfig(
            categories=(),
            severity_rules=(),
            severity_thresholds=SeverityThresholdConfig(20, 40, 60, 80),
            decisions=DecisionConfig("critical", "medium"),
        ),
        sources=sources,
    )
