"""Tests for structured logging setup."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from auto_cyber_news.logging import configure_logging, correlation_context, get_logger


def test_json_logging_includes_required_fields(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON logs should include production correlation and source fields."""
    configure_logging("INFO", "json")
    logger = get_logger("tests.logging")

    with correlation_context("test-correlation-id"):
        logger.info("hello", extra={"component": "unit-test"})

    captured = capsys.readouterr().err
    payload = json.loads(captured)

    assert payload["level"] == "INFO"
    assert payload["module"] == "tests.logging"
    assert payload["correlation_id"] == "test-correlation-id"
    assert payload["message"] == "hello"
    assert payload["component"] == "unit-test"


def test_json_logging_can_write_to_file(tmp_path: Path) -> None:
    """JSON logging should optionally write to a configured file."""
    log_path = tmp_path / "app.log"
    configure_logging("INFO", "json", file_enabled=True, file_path=log_path)
    logging.getLogger("tests.file").info("file-log")

    payload = json.loads(log_path.read_text(encoding="utf-8"))

    assert payload["message"] == "file-log"
