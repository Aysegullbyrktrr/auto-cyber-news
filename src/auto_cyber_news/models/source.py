"""Source domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """Configured news source."""

    id: str
    name: str
    type: str
    url: str
    enabled: bool = True
    poll_interval_minutes: int = 60
