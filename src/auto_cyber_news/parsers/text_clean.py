"""Text normalization helpers for ingestion and article parsing."""

from __future__ import annotations

import html
import re

_MULTI_COMMA_PATTERN = re.compile(r",\s*,+")
_TRAILING_COMMA_PATTERN = re.compile(r",\s*$")


def normalize_text(value: str) -> str:
    """Decode HTML entities and collapse redundant whitespace."""
    decoded = html.unescape(value)
    return " ".join(decoded.split())


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional text, returning None when empty after cleaning."""
    if value is None:
        return None
    normalized = normalize_text(value)
    return normalized or None


def clean_title(value: str) -> str:
    """Normalize a title and remove duplicated or trailing commas."""
    normalized = normalize_text(value)
    without_duplicate_commas = _MULTI_COMMA_PATTERN.sub(",", normalized)
    return _TRAILING_COMMA_PATTERN.sub("", without_duplicate_commas).strip()
