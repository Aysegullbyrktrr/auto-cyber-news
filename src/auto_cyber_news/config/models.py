"""Typed configuration models for application startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HttpConfig:
    """HTTP runtime configuration."""

    timeout_seconds: int
    total_retries: int
    user_agent: str
    max_concurrency: int


@dataclass(frozen=True)
class DatabaseConfig:
    """Database runtime configuration."""

    sqlite_path: Path


@dataclass(frozen=True)
class LoggingConfig:
    """Structured logging configuration."""

    level: str
    format: str
    file_enabled: bool
    file_path: Path


@dataclass(frozen=True)
class DigestConfig:
    """Digest generation configuration."""

    window_hours: int
    max_articles: int
    subject_prefix: str


@dataclass(frozen=True)
class AlertConfig:
    """Critical alert configuration."""

    critical_freshness_minutes: int
    dry_run: bool
    alert_cooldown_hours: int


@dataclass(frozen=True)
class SourceConfig:
    """Configured cybersecurity news source."""

    id: str
    name: str
    type: str
    enabled: bool
    url: str
    homepage: str | None
    poll_interval_minutes: int
    reliability_weight: float
    category_hints: tuple[str, ...]


@dataclass(frozen=True)
class CategoryConfig:
    """Threat category rule configuration."""

    id: str
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class SeverityRuleConfig:
    """Severity scoring rule configuration."""

    id: str
    description: str
    weight: int
    terms: tuple[str, ...]


@dataclass(frozen=True)
class SeverityThresholdConfig:
    """Severity score threshold configuration."""

    low: int
    medium: int
    high: int
    critical: int


@dataclass(frozen=True)
class DecisionConfig:
    """Analysis decision rule configuration."""

    telegram_alert_min_level: str
    email_digest_min_level: str


@dataclass(frozen=True)
class AnalysisConfig:
    """Rules used by deterministic article analysis."""

    categories: tuple[CategoryConfig, ...]
    severity_rules: tuple[SeverityRuleConfig, ...]
    severity_thresholds: SeverityThresholdConfig
    decisions: DecisionConfig


@dataclass(frozen=True)
class Config:
    """Top-level typed application configuration."""

    name: str
    environment: str
    timezone: str
    config_dir: Path
    database: DatabaseConfig
    logging: LoggingConfig
    http: HttpConfig
    digest: DigestConfig
    alerts: AlertConfig
    analysis: AnalysisConfig
    sources: tuple[SourceConfig, ...]
