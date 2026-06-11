"""Structured logging configuration helpers."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

_CORRELATION_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="-",
)


class JsonFormatter(logging.Formatter):
    """Format log records as production-oriented JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a logging record as one JSON object."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),  # noqa: UP017
            "level": record.levelname,
            "module": record.name,
            "correlation_id": get_correlation_id(),
            "message": record.getMessage(),
        }
        _merge_extra_fields(record, payload)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    *,
    file_enabled: bool = False,
    file_path: Path = Path("logs/app.log"),
    stream: TextIO | None = None,
) -> None:
    """Configure process-wide logging."""
    normalized_level = _normalize_level(level)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(normalized_level)

    formatter: logging.Formatter
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s correlation_id=%(correlation_id)s %(message)s",
        )

    stream_handler = logging.StreamHandler(stream or sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(_CorrelationIdFilter())
    root_logger.addHandler(stream_handler)

    if file_enabled:
        _attach_file_handler(root_logger, formatter, file_path)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for application modules."""
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str) -> contextvars.Token[str]:
    """Set the current correlation id for subsequent log records."""
    return _CORRELATION_ID.set(correlation_id)


def reset_correlation_id(token: contextvars.Token[str]) -> None:
    """Reset the correlation id to a previous context value."""
    _CORRELATION_ID.reset(token)


def get_correlation_id() -> str:
    """Return the current correlation id."""
    return _CORRELATION_ID.get()


class correlation_context:
    """Context manager for temporarily setting a correlation id."""

    def __init__(self, correlation_id: str) -> None:
        """Initialize the context with the requested correlation id."""
        self._correlation_id = correlation_id
        self._token: contextvars.Token[str] | None = None

    def __enter__(self) -> None:
        """Set the correlation id when entering the context."""
        self._token = set_correlation_id(self._correlation_id)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore the previous correlation id when leaving the context."""
        if self._token is not None:
            reset_correlation_id(self._token)


class _CorrelationIdFilter(logging.Filter):
    """Inject the active correlation id into standard formatted records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current correlation id to a log record."""
        record.correlation_id = get_correlation_id()
        return True


def _normalize_level(level: str) -> int:
    """Convert a supported log level name into a logging level."""
    normalized = level.upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ValueError(f"Unsupported log level: {level}")
    return int(logging.getLevelName(normalized))


def _attach_file_handler(
    root_logger: logging.Logger,
    formatter: logging.Formatter,
    file_path: Path,
) -> None:
    """Attach a rotating file handler without disabling stdout logging."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_CorrelationIdFilter())
        root_logger.addHandler(file_handler)
    except OSError as exc:
        root_logger.warning(
            "File logging disabled; continuing with stdout only",
            extra={"file_path": str(file_path), "error": str(exc)},
        )


def _merge_extra_fields(record: logging.LogRecord, payload: dict[str, Any]) -> None:
    """Add safe custom log fields to a JSON payload."""
    standard_fields = logging.makeLogRecord({}).__dict__.keys()
    for key, value in record.__dict__.items():
        if key in standard_fields or key in {"message", "asctime", "correlation_id"}:
            continue
        payload[key] = value
