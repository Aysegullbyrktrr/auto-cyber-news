"""Environment loading helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

_LOAD_DOTENV: Callable[..., object] | None

try:
    from dotenv import load_dotenv as _IMPORTED_LOAD_DOTENV
except ImportError:  # pragma: no cover - exercised only in incomplete environments.
    _LOAD_DOTENV = None
else:
    _LOAD_DOTENV = _IMPORTED_LOAD_DOTENV


def load_environment(env_path: Path | None = None) -> None:
    """Load local environment variables from a dotenv file when present."""
    if _LOAD_DOTENV is None:
        return
    _LOAD_DOTENV(dotenv_path=env_path, override=False)
