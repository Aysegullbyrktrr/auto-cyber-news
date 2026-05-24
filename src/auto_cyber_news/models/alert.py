"""Alert domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertDecision:
    """Decision describing whether an article should alert."""

    should_alert: bool
    reason: str
