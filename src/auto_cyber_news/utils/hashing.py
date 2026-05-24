"""Hashing utilities."""

from __future__ import annotations

import hashlib


def content_hash(value: str) -> str:
    """Compute a stable content hash."""
    normalized = " ".join(value.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
