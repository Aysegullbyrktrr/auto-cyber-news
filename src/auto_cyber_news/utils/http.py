"""HTTP utility placeholders."""

from __future__ import annotations


def default_headers(user_agent: str) -> dict[str, str]:
    """Build default HTTP request headers."""
    return {"User-Agent": user_agent}
