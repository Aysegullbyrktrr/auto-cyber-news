"""Digest domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DigestRequest:
    """Request to render or send a digest for a date."""

    digest_date: date
