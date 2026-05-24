"""Integration tests for the analysis CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_cyber_news.cli import main


def test_run_analysis_cli_accepts_ingestion_output_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """run-analysis should enrich existing run-ingestion JSON output."""
    config_dir = _write_config(tmp_path)
    input_path = tmp_path / "ingestion.json"
    input_path.write_text(
        json.dumps(
            {
                "article_count": 1,
                "articles": [
                    {
                        "title": "CVE-2026-1234 zero-day exploit actively exploited",
                        "url": "https://example.com/story",
                        "canonical_url": "https://example.com/story",
                        "content_hash": "hash",
                        "published_at": None,
                        "source": "Example",
                        "source_id": "example",
                        "raw_content": "Ransomware campaign causes data breach.",
                        "summary_placeholder": "",
                        "category_placeholder": "",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    assert main(["--config-dir", str(config_dir), "run-analysis", "--input", str(input_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    article = payload["articles"][0]
    assert article["severity"] == "critical"
    assert article["detected_cves"] == ["CVE-2026-1234"]
    assert article["is_critical"] is True
    assert article["should_alert_telegram"] is True


def _write_config(tmp_path: Path) -> Path:
    """Write a minimal config directory for analysis CLI tests."""
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
