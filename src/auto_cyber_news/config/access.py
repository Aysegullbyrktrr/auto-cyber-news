"""Safe configuration access helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

T = TypeVar("T")


class MissingConfigKeyError(KeyError):
    """Raised when a required configuration key is missing."""


def require_key(mapping: Mapping[str, T], key: str) -> T:  # noqa: UP047
    """Return a required key from a mapping."""
    if key not in mapping:
        raise MissingConfigKeyError(key)
    return mapping[key]


def get_optional(mapping: Mapping[str, T], key: str, default: T) -> T:  # noqa: UP047
    """Return an optional key from a mapping with a default value."""
    return mapping.get(key, default)
