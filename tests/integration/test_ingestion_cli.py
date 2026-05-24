"""Integration tests for the ingestion CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_cyber_news.cli import main
from auto_cyber_news.fetchers.http import AsyncHttpClient


def test_run_ingestion_cli_outputs_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """run-ingestion should emit normalized articles as JSON."""
    monkeypatch.setattr(AsyncHttpClient, "get_text", _mock_get_text)
    config_dir = _write_config(tmp_path)

    assert main(["--config-dir", str(config_dir), "run-ingestion"]) == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload["article_count"] == 1
    assert payload["articles"][0]["title"] == "Critical CVE exploited"
    assert payload["articles"][0]["canonical_url"] == "https://example.com/story"


async def _mock_get_text(self: AsyncHttpClient, url: str) -> str:
    """Return a mocked RSS feed for CLI tests."""
    return """
    <rss version="2.0">
      <channel>
        <item>
          <title>Critical CVE exploited</title>
          <link>https://example.com/story?utm_source=feed</link>
          <pubDate>Sun, 24 May 2026 08:00:00 GMT</pubDate>
          <description>Example summary</description>
        </item>
      </channel>
    </rss>
    """


def _write_config(tmp_path: Path) -> Path:
    """Write a minimal config directory for ingestion CLI tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_dir.joinpath("app.yaml").write_text(
        """
app:
  name: auto-cyber-news
  environment: test
  timezone: UTC
database:
  sqlite_path: data/test.db
http:
  timeout_seconds: 5
  total_retries: 0
  user_agent: auto-cyber-news/test
  max_concurrency: 2
digest:
  window_hours: 24
  max_articles: 10
  subject_prefix: Test Digest
alerts:
  critical_freshness_minutes: 180
  dry_run: true
""",
        encoding="utf-8",
    )
    config_dir.joinpath("sources.yaml").write_text(
        """
sources:
  - id: example
    name: Example
    type: rss
    enabled: true
    url: https://example.com/feed.xml
    homepage: https://example.com/
    poll_interval_minutes: 60
    reliability_weight: 1.0
    category_hints: []
""",
        encoding="utf-8",
    )
    return config_dir
