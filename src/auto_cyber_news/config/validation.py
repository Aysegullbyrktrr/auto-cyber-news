"""Configuration validation rules."""

from __future__ import annotations

from urllib.parse import urlparse

from auto_cyber_news.config.models import Config


class ConfigValidationError(ValueError):
    """Raised when typed configuration fails validation rules."""


def validate_config(config: Config) -> None:
    """Validate application configuration and raise one combined error."""
    errors: list[str] = []

    _validate_choice(
        config.logging.level,
        {"DEBUG", "INFO", "WARNING", "ERROR"},
        "LOG_LEVEL",
        errors,
    )
    _validate_choice(config.logging.format, {"json", "console"}, "LOG_FORMAT", errors)
    _validate_positive(config.http.timeout_seconds, "http.timeout_seconds", errors)
    _validate_non_negative(config.http.total_retries, "http.total_retries", errors)
    _validate_positive(config.http.max_concurrency, "http.max_concurrency", errors)
    _validate_positive(config.digest.window_hours, "digest.window_hours", errors)
    _validate_positive(config.digest.max_articles, "digest.max_articles", errors)
    _validate_positive(
        config.alerts.critical_freshness_minutes,
        "alerts.critical_freshness_minutes",
        errors,
    )
    _validate_positive(config.alerts.alert_cooldown_hours, "alerts.alert_cooldown_hours", errors)
    _validate_choice(
        config.analysis.decisions.telegram_alert_min_level,
        {"low", "medium", "high", "critical"},
        "severity.decisions.telegram_alert_min_level",
        errors,
    )
    _validate_choice(
        config.analysis.decisions.email_digest_min_level,
        {"low", "medium", "high", "critical"},
        "severity.decisions.email_digest_min_level",
        errors,
    )
    _validate_thresholds(config, errors)

    if not config.sources:
        errors.append("sources must contain at least one source")

    seen_source_ids: set[str] = set()
    for source in config.sources:
        if source.id in seen_source_ids:
            errors.append(f"duplicate source id: {source.id}")
        seen_source_ids.add(source.id)
        _validate_choice(source.type, {"rss", "html"}, f"sources.{source.id}.type", errors)
        _validate_positive(
            source.poll_interval_minutes,
            f"sources.{source.id}.poll_interval_minutes",
            errors,
        )
        if source.reliability_weight <= 0:
            errors.append(f"sources.{source.id}.reliability_weight must be greater than zero")
        _validate_url(source.url, f"sources.{source.id}.url", errors)
        if source.homepage is not None:
            _validate_url(source.homepage, f"sources.{source.id}.homepage", errors)

    if errors:
        raise ConfigValidationError("; ".join(errors))


def _validate_choice(value: str, allowed: set[str], field_name: str, errors: list[str]) -> None:
    """Validate that a value is in an allowed set."""
    if value not in allowed:
        errors.append(f"{field_name} must be one of {sorted(allowed)}")


def _validate_thresholds(config: Config, errors: list[str]) -> None:
    """Validate severity thresholds are ascending."""
    thresholds = config.analysis.severity_thresholds
    if not thresholds.low < thresholds.medium < thresholds.high < thresholds.critical:
        errors.append("severity thresholds must be ascending: low < medium < high < critical")


def _validate_positive(value: int, field_name: str, errors: list[str]) -> None:
    """Validate that an integer is greater than zero."""
    if value <= 0:
        errors.append(f"{field_name} must be greater than zero")


def _validate_non_negative(value: int, field_name: str, errors: list[str]) -> None:
    """Validate that an integer is zero or greater."""
    if value < 0:
        errors.append(f"{field_name} must be zero or greater")


def _validate_url(value: str, field_name: str, errors: list[str]) -> None:
    """Validate that a string looks like an HTTP URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{field_name} must be a valid HTTP(S) URL")
