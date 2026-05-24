"""Configuration loading with YAML files and environment overlays."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    import yaml as _yaml  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - exercised only in incomplete environments.
    yaml: ModuleType | None = None
    _YAML_IMPORT_ERROR: ImportError | None = exc
else:
    yaml = _yaml
    _YAML_IMPORT_ERROR = None

from auto_cyber_news.config.models import (
    AlertConfig,
    AnalysisConfig,
    CategoryConfig,
    Config,
    DatabaseConfig,
    DecisionConfig,
    DigestConfig,
    HttpConfig,
    LoggingConfig,
    SeverityRuleConfig,
    SeverityThresholdConfig,
    SourceConfig,
)
from auto_cyber_news.config.validation import validate_config
from auto_cyber_news.utils.env import load_environment

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


class ConfigError(ValueError):
    """Raised when configuration cannot be loaded or parsed."""


def load_config(config_dir: Path | None = None) -> Config:
    """Load, overlay, and validate application configuration."""
    load_environment()
    if config_dir is not None:
        config_dir_value = str(config_dir)
    else:
        config_dir_value = os.getenv("CONFIG_DIR", "config")
    resolved_config_dir = Path(str(config_dir_value))
    app_data = _read_yaml_file(resolved_config_dir / "app.yaml")
    source_data = _read_yaml_file(resolved_config_dir / "sources.yaml")
    category_data = _read_optional_yaml_file(resolved_config_dir / "categories.yaml")
    severity_data = _read_optional_yaml_file(resolved_config_dir / "severity.yaml")
    config = _build_config(resolved_config_dir, app_data, source_data, category_data, severity_data)
    validate_config(config)
    return config


def _read_yaml_file(path: Path) -> dict[str, Any]:
    """Read a YAML file and expand supported environment placeholders."""
    if yaml is None:
        raise ConfigError(
            "PyYAML is required to load configuration. Install requirements.txt.",
        ) from _YAML_IMPORT_ERROR
    if not path.exists():
        raise ConfigError(f"Configuration file does not exist: {path}")
    raw_text = path.read_text(encoding="utf-8")
    expanded_text = _expand_environment_placeholders(raw_text)
    loaded = yaml.safe_load(expanded_text) or {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration file must contain a mapping: {path}")
    return loaded


def _read_optional_yaml_file(path: Path) -> dict[str, Any]:
    """Read an optional YAML file and return an empty mapping when absent."""
    if not path.exists():
        return {}
    return _read_yaml_file(path)


def _expand_environment_placeholders(value: str) -> str:
    """Expand ``${NAME:-default}`` placeholders using process environment values."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2) or ""
        return os.getenv(name, default)

    return _ENV_PATTERN.sub(replace, value)


def _build_config(
    config_dir: Path,
    app_data: Mapping[str, Any],
    source_data: Mapping[str, Any],
    category_data: Mapping[str, Any],
    severity_data: Mapping[str, Any],
) -> Config:
    """Build a typed configuration object from raw mappings."""
    app_section = _required_mapping(app_data, "app")
    database_section = _required_mapping(app_data, "database")
    http_section = _required_mapping(app_data, "http")
    digest_section = _required_mapping(app_data, "digest")
    alerts_section = _required_mapping(app_data, "alerts")
    source_items = _required_list(source_data, "sources")
    environment = os.getenv(
        "APP_ENV",
        _as_str(app_section.get("environment"), "app.environment"),
    )
    production = _is_production_environment(environment)

    return Config(
        name=_as_str(app_section.get("name"), "app.name"),
        environment=environment,
        timezone=os.getenv("DIGEST_TIMEZONE", _as_str(app_section.get("timezone"), "app.timezone")),
        config_dir=config_dir,
        database=DatabaseConfig(
            sqlite_path=Path(
                str(os.getenv("SQLITE_PATH", database_section.get("sqlite_path", ""))),
            ),
        ),
        logging=LoggingConfig(
            level=_resolve_log_level(production),
            format=os.getenv("LOG_FORMAT", "json").lower(),
            file_enabled=_env_bool("LOG_FILE_ENABLED", default=production),
            file_path=Path(os.getenv("LOG_FILE_PATH", "logs/app.log")),
        ),
        http=HttpConfig(
            timeout_seconds=_as_int(http_section.get("timeout_seconds"), "http.timeout_seconds"),
            total_retries=_as_int(http_section.get("total_retries"), "http.total_retries"),
            user_agent=_as_str(http_section.get("user_agent"), "http.user_agent"),
            max_concurrency=_as_int(http_section.get("max_concurrency"), "http.max_concurrency"),
        ),
        digest=DigestConfig(
            window_hours=_as_int(digest_section.get("window_hours"), "digest.window_hours"),
            max_articles=_as_int(digest_section.get("max_articles"), "digest.max_articles"),
            subject_prefix=_as_str(digest_section.get("subject_prefix"), "digest.subject_prefix"),
        ),
        alerts=AlertConfig(
            critical_freshness_minutes=_as_int(
                alerts_section.get("critical_freshness_minutes"),
                "alerts.critical_freshness_minutes",
            ),
            dry_run=_resolve_dry_run(alerts_section, production),
            alert_cooldown_hours=_as_int(
                os.getenv(
                    "ALERT_COOLDOWN_HOURS",
                    alerts_section.get("alert_cooldown_hours", 6),
                ),
                "alerts.alert_cooldown_hours",
            ),
        ),
        analysis=_build_analysis_config(category_data, severity_data),
        sources=tuple(_build_source(item, index) for index, item in enumerate(source_items)),
    )


def _build_analysis_config(
    category_data: Mapping[str, Any],
    severity_data: Mapping[str, Any],
) -> AnalysisConfig:
    """Build analysis rule configuration."""
    category_items = category_data.get("categories", _default_categories())
    if not isinstance(category_items, list):
        raise ConfigError("categories must be a list")
    severity_section = severity_data.get("severity", {})
    if not isinstance(severity_section, Mapping):
        raise ConfigError("severity must be a mapping")
    thresholds = severity_section.get("thresholds", _default_thresholds())
    if not isinstance(thresholds, Mapping):
        raise ConfigError("severity.thresholds must be a mapping")
    rule_items = severity_section.get("rules", _default_severity_rules())
    if not isinstance(rule_items, list):
        raise ConfigError("severity.rules must be a list")
    decisions = severity_section.get("decisions", {})
    if not isinstance(decisions, Mapping):
        raise ConfigError("severity.decisions must be a mapping")

    return AnalysisConfig(
        categories=tuple(_build_category(item, index) for index, item in enumerate(category_items)),
        severity_rules=tuple(
            _build_severity_rule(item, index) for index, item in enumerate(rule_items)
        ),
        severity_thresholds=SeverityThresholdConfig(
            low=_as_int(thresholds.get("low", 20), "severity.thresholds.low"),
            medium=_as_int(thresholds.get("medium", 40), "severity.thresholds.medium"),
            high=_as_int(thresholds.get("high", 60), "severity.thresholds.high"),
            critical=_as_int(thresholds.get("critical", 80), "severity.thresholds.critical"),
        ),
        decisions=DecisionConfig(
            telegram_alert_min_level=_as_str(
                decisions.get("telegram_alert_min_level", "critical"),
                "severity.decisions.telegram_alert_min_level",
            ).lower(),
            email_digest_min_level=_as_str(
                decisions.get("email_digest_min_level", "medium"),
                "severity.decisions.email_digest_min_level",
            ).lower(),
        ),
    )


def _build_category(raw_category: object, index: int) -> CategoryConfig:
    """Build a typed category config entry."""
    if not isinstance(raw_category, Mapping):
        raise ConfigError(f"categories[{index}] must be a mapping")
    keywords = raw_category.get("keywords", [])
    if not isinstance(keywords, list):
        raise ConfigError(f"categories[{index}].keywords must be a list")
    return CategoryConfig(
        id=_as_str(raw_category.get("id"), f"categories[{index}].id"),
        name=_as_str(raw_category.get("name"), f"categories[{index}].name"),
        keywords=tuple(_as_str(keyword, f"categories[{index}].keywords") for keyword in keywords),
    )


def _build_severity_rule(raw_rule: object, index: int) -> SeverityRuleConfig:
    """Build a typed severity rule config entry."""
    if not isinstance(raw_rule, Mapping):
        raise ConfigError(f"severity.rules[{index}] must be a mapping")
    terms = raw_rule.get("terms", [])
    if not isinstance(terms, list):
        raise ConfigError(f"severity.rules[{index}].terms must be a list")
    return SeverityRuleConfig(
        id=_as_str(raw_rule.get("id"), f"severity.rules[{index}].id"),
        description=_as_str(raw_rule.get("description"), f"severity.rules[{index}].description"),
        weight=_as_int(raw_rule.get("weight"), f"severity.rules[{index}].weight"),
        terms=tuple(_as_str(term, f"severity.rules[{index}].terms") for term in terms),
    )


def _build_source(raw_source: object, index: int) -> SourceConfig:
    """Build a typed source configuration entry."""
    if not isinstance(raw_source, Mapping):
        raise ConfigError(f"sources[{index}] must be a mapping")
    hints = raw_source.get("category_hints", [])
    if not isinstance(hints, list):
        raise ConfigError(f"sources[{index}].category_hints must be a list")
    return SourceConfig(
        id=_as_str(raw_source.get("id"), f"sources[{index}].id"),
        name=_as_str(raw_source.get("name"), f"sources[{index}].name"),
        type=_as_str(raw_source.get("type"), f"sources[{index}].type"),
        enabled=_as_bool(raw_source.get("enabled"), f"sources[{index}].enabled"),
        url=_as_str(raw_source.get("url"), f"sources[{index}].url"),
        homepage=_optional_str(raw_source.get("homepage"), f"sources[{index}].homepage"),
        poll_interval_minutes=_as_int(
            raw_source.get("poll_interval_minutes"),
            f"sources[{index}].poll_interval_minutes",
        ),
        reliability_weight=_as_float(
            raw_source.get("reliability_weight"),
            f"sources[{index}].reliability_weight",
        ),
        category_hints=tuple(_as_str(hint, f"sources[{index}].category_hints") for hint in hints),
    )


def _required_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a required nested mapping from raw configuration."""
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ConfigError(f"Missing or invalid mapping: {key}")
    return value


def _required_list(data: Mapping[str, Any], key: str) -> list[Any]:
    """Return a required list from raw configuration."""
    value = data.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"Missing or invalid list: {key}")
    return value


def _as_str(value: object, field_name: str) -> str:
    """Convert a required value to a non-empty string."""
    if value is None:
        raise ConfigError(f"Missing required field: {field_name}")
    result = str(value).strip()
    if not result:
        raise ConfigError(f"Required field cannot be empty: {field_name}")
    return result


def _optional_str(value: object, field_name: str) -> str | None:
    """Convert an optional value to a non-empty string or ``None``."""
    if value is None:
        return None
    result = str(value).strip()
    if not result:
        raise ConfigError(f"Optional field cannot be blank when provided: {field_name}")
    return result


def _as_int(value: object, field_name: str) -> int:
    """Convert a required value to an integer."""
    try:
        return int(_as_str(value, field_name))
    except ValueError as exc:
        raise ConfigError(f"Field must be an integer: {field_name}") from exc


def _as_float(value: object, field_name: str) -> float:
    """Convert a required value to a float."""
    try:
        return float(_as_str(value, field_name))
    except ValueError as exc:
        raise ConfigError(f"Field must be a number: {field_name}") from exc


def _as_bool(value: object, field_name: str) -> bool:
    """Convert a required value to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"Field must be a boolean: {field_name}")


def _env_bool(name: str, *, default: bool) -> bool:
    """Read a boolean value from the environment."""
    value = os.getenv(name)
    if value is None:
        return default
    return _as_bool(value, name)


def _is_production_environment(environment: str) -> bool:
    """Return whether the active environment is a production deployment."""
    return environment.strip().casefold() in {"production", "prod"}


def _resolve_log_level(production: bool) -> str:
    """Resolve the default log level with production-safe defaults."""
    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        return env_level.upper()
    if production:
        return "INFO"
    return "INFO"


def _resolve_dry_run(alerts_section: Mapping[str, Any], production: bool) -> bool:
    """Resolve alert dry-run behavior with production-safe defaults."""
    dry_run_env = os.getenv("ALERTS_DRY_RUN")
    if dry_run_env is not None:
        return _as_bool(dry_run_env, "ALERTS_DRY_RUN")
    default_value = False if production else True
    return _as_bool(alerts_section.get("dry_run", default_value), "alerts.dry_run")


def _default_thresholds() -> dict[str, int]:
    """Return default severity thresholds."""
    return {"low": 20, "medium": 40, "high": 60, "critical": 80}


def _default_categories() -> list[dict[str, object]]:
    """Return default category rules for minimal test configurations."""
    return [
        {"id": "ransomware", "name": "Ransomware", "keywords": ["ransomware", "extortion"]},
        {"id": "malware", "name": "Malware", "keywords": ["malware", "trojan", "backdoor"]},
        {"id": "vulnerability", "name": "Vulnerability", "keywords": ["cve", "vulnerability"]},
        {"id": "zero_day", "name": "Zero-Day", "keywords": ["zero-day", "0-day"]},
        {"id": "data_breach", "name": "Data Breach", "keywords": ["breach", "leak"]},
        {
            "id": "threat_intelligence",
            "name": "Threat Intelligence",
            "keywords": ["ioc", "campaign", "threat actor"],
        },
        {"id": "nation_state", "name": "Nation-State", "keywords": ["apt", "nation-state"]},
        {"id": "cloud_security", "name": "Cloud Security", "keywords": ["aws", "azure", "cloud"]},
        {"id": "ai_security", "name": "AI Security", "keywords": ["ai", "llm", "model"]},
    ]


def _default_severity_rules() -> list[dict[str, object]]:
    """Return default severity scoring rules for minimal test configurations."""
    return [
        {
            "id": "active_exploitation",
            "description": "Active exploitation language.",
            "weight": 35,
            "terms": ["actively exploited", "in the wild", "mass exploitation"],
        },
        {
            "id": "ransomware",
            "description": "Ransomware language.",
            "weight": 25,
            "terms": ["ransomware", "extortion"],
        },
        {
            "id": "exploit",
            "description": "Exploit language.",
            "weight": 20,
            "terms": ["exploit", "exploitation", "poc"],
        },
        {
            "id": "data_breach",
            "description": "Data breach language.",
            "weight": 20,
            "terms": ["data breach", "breach", "leaked records"],
        },
    ]
