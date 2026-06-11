"""Integration tests for SQLite migrations."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.db.migrations import (
    get_applied_migrations,
    get_table_counts,
    run_migrations,
)


def test_run_migrations_applies_and_skips_idempotently(tmp_path: Path) -> None:
    """Migration runner should apply new migrations once and skip them later."""
    sqlite_path = tmp_path / "app.db"

    first_result = run_migrations(sqlite_path)
    second_result = run_migrations(sqlite_path)
    applied_records = get_applied_migrations(sqlite_path)

    expected_migrations = (
        "001_bootstrap.sql",
        "002_phase2_core.sql",
        "003_incidents.sql",
        "004_processed_articles.sql",
    )
    assert first_result.applied == expected_migrations
    assert first_result.skipped == ()
    assert second_result.applied == ()
    assert second_result.skipped == expected_migrations
    assert tuple(record.version for record in applied_records) == first_result.applied


def test_get_table_counts_reports_phase2_tables(tmp_path: Path) -> None:
    """Table status should include the Phase 2 persistence tables."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    counts = get_table_counts(
        sqlite_path,
        tables=("schema_migrations", "news", "sent_digest", "metadata"),
    )

    assert counts == {
        "schema_migrations": 4,
        "news": 0,
        "sent_digest": 0,
        "metadata": 0,
    }
