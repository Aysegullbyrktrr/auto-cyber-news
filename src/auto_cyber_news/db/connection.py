"""SQLite connection and session management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    """SQLite connection manager configuration."""

    sqlite_path: Path
    timeout_seconds: float = 30.0


class Database:
    """Centralized SQLite connection manager."""

    def __init__(self, config: DatabaseConfig) -> None:
        """Initialize the manager with a database configuration."""
        self._config = config

    @property
    def sqlite_path(self) -> Path:
        """Return the configured SQLite database path."""
        return self._config.sqlite_path

    def connect(self) -> sqlite3.Connection:
        """Open and configure a SQLite connection."""
        return connect(self._config.sqlite_path, timeout_seconds=self._config.timeout_seconds)

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """Open a transaction-scoped SQLite session."""
        with session(
            self._config.sqlite_path,
            timeout_seconds=self._config.timeout_seconds,
        ) as conn:
            yield conn


def connect(sqlite_path: Path, *, timeout_seconds: float = 30.0) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        sqlite_path,
        timeout=timeout_seconds,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


@contextmanager
def session(sqlite_path: Path, *, timeout_seconds: float = 30.0) -> Iterator[sqlite3.Connection]:
    """Open a transaction-scoped SQLite session with commit and rollback handling."""
    connection = connect(sqlite_path, timeout_seconds=timeout_seconds)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
