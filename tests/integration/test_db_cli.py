"""Integration tests for database CLI commands."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.cli import main


def test_database_cli_commands(tmp_path: Path) -> None:
    """Database CLI commands should run against a configured SQLite path."""
    config_dir = _write_config(tmp_path)

    assert main(["--config-dir", str(config_dir), "init-db"]) == 0
    assert main(["--config-dir", str(config_dir), "migrate"]) == 0
    assert main(["--config-dir", str(config_dir), "db-status"]) == 0


def _write_config(tmp_path: Path) -> Path:
    """Write a minimal config directory for CLI tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    sqlite_path = tmp_path / "data" / "app.db"
    config_dir.joinpath("app.yaml").write_text(
        f"""
app:
  name: auto-cyber-news
  environment: test
  timezone: UTC
database:
  sqlite_path: {sqlite_path}
http:
  timeout_seconds: 20
  total_retries: 2
  user_agent: auto-cyber-news/test
  max_concurrency: 4
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
