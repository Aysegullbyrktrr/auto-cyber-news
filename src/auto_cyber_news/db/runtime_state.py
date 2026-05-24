"""Lightweight runtime state persisted in the metadata table."""

from __future__ import annotations

import sqlite3

from auto_cyber_news.utils.time import utc_now

KEY_INGESTION_LAST_RUN = "ingestion_last_run"
KEY_LAST_CYCLE_SOURCES_OK = "last_cycle_sources_ok"
KEY_LAST_CYCLE_SOURCES_FAILED = "last_cycle_sources_failed"


def get_metadata(connection: sqlite3.Connection, key: str) -> str | None:
    """Return a metadata value by key."""
    row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return str(row["value"])


def set_metadata(connection: sqlite3.Connection, key: str, value: str) -> None:
    """Upsert a metadata key/value pair."""
    now = utc_now().isoformat()
    connection.execute(
        """
        INSERT INTO metadata (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, now),
    )


def record_ingestion_cycle(
    connection: sqlite3.Connection,
    *,
    sources_ok: int,
    sources_failed: int,
) -> None:
    """Persist ingestion cycle timestamps and source health counters."""
    set_metadata(connection, KEY_INGESTION_LAST_RUN, utc_now().isoformat())
    set_metadata(connection, KEY_LAST_CYCLE_SOURCES_OK, str(sources_ok))
    set_metadata(connection, KEY_LAST_CYCLE_SOURCES_FAILED, str(sources_failed))
    connection.commit()
