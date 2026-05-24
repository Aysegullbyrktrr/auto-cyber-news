"""Application composition root for dependency wiring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Application:
    """Container for configured application services."""

    environment: str


def create_application(environment: str) -> Application:
    """Create an application container for the requested environment."""
    return Application(environment=environment)
