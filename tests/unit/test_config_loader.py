"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_cyber_news.config.loader import ConfigError, load_config
from auto_cyber_news.config.validation import ConfigValidationError


def test_load_config_reads_sources_and_environment_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config loading should read YAML and apply environment overrides."""
    config_dir = _write_config(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SQLITE_PATH", "data/test.db")

    config = load_config(config_dir)

    assert config.environment == "test"
    assert config.logging.level == "DEBUG"
    assert config.database.sqlite_path == Path("data/test.db")
    assert len(config.sources) == 1
    assert config.sources[0].id == "example"


def test_load_config_rejects_invalid_source_type(tmp_path: Path) -> None:
    """Config validation should reject unsupported source types."""
    config_dir = _write_config(tmp_path, source_type="unsupported")

    with pytest.raises(ConfigValidationError):
        load_config(config_dir)


def test_load_config_requires_sources_file(tmp_path: Path) -> None:
    """Config loading should fail clearly when required files are absent."""
    (tmp_path / "app.yaml").write_text(_app_yaml(), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def _write_config(tmp_path: Path, *, source_type: str = "rss") -> Path:
    """Write a minimal valid config directory."""
    tmp_path.joinpath("app.yaml").write_text(_app_yaml(), encoding="utf-8")
    tmp_path.joinpath("sources.yaml").write_text(_sources_yaml(source_type), encoding="utf-8")
    return tmp_path


def _app_yaml() -> str:
    """Return minimal app YAML for loader tests."""
    return """
app:
  name: auto-cyber-news
  environment: development
  timezone: UTC
database:
  sqlite_path: data/auto-cyber-news.db
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
"""


def _sources_yaml(source_type: str) -> str:
    """Return minimal sources YAML for loader tests."""
    return f"""
sources:
  - id: example
    name: Example
    type: {source_type}
    enabled: true
    url: https://example.com/feed.xml
    homepage: https://example.com/
    poll_interval_minutes: 60
    reliability_weight: 1.0
    category_hints: []
"""
