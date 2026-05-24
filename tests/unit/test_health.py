"""Tests for production health checks."""

from __future__ import annotations

import json
import os
from pathlib import Path

from auto_cyber_news.cli import main
from auto_cyber_news.db.connection import connect
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.runtime_state import record_ingestion_cycle
from auto_cyber_news.health import run_health_check


def test_run_health_check_reports_healthy_after_ingestion(tmp_path: Path) -> None:
    """Health check should report healthy when DB and config are valid."""
    config_dir = _write_config(tmp_path)
    sqlite_path = tmp_path / "data" / "app.db"
    run_migrations(sqlite_path)
    connection = connect(sqlite_path)
    record_ingestion_cycle(connection, sources_ok=2, sources_failed=0)
    connection.close()

    os.environ["SQLITE_PATH"] = str(sqlite_path)
    report = run_health_check(config_dir)

    assert report["config_loaded"] is True
    assert report["db_status"] is True
    assert report["rss_sources_ok"] is True
    assert report["ingestion_last_run"] is not None
    assert report["overall_status"] in {"healthy", "degraded"}


def test_health_check_cli_emits_json(tmp_path: Path, capsys) -> None:
    """CLI health-check should print JSON to stdout."""
    config_dir = _write_config(tmp_path)
    exit_code = main(["--config-dir", str(config_dir), "health-check"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code in {0, 1}
    assert payload["overall_status"] in {"healthy", "degraded", "unhealthy"}
    assert "db_status" in payload
    assert "config_loaded" in payload


def _write_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_dir.joinpath("app.yaml").write_text(
        f"""
app:
  name: auto-cyber-news
  environment: production
  timezone: UTC
database:
  sqlite_path: {tmp_path / "data" / "app.db"}
http:
  timeout_seconds: 5
  total_retries: 0
  user_agent: test
  max_concurrency: 2
digest:
  window_hours: 24
  max_articles: 10
  subject_prefix: Test
alerts:
  critical_freshness_minutes: 180
  dry_run: false
  alert_cooldown_hours: 6
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
