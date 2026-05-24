"""SQLite migration runner."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from auto_cyber_news.db.connection import connect
from auto_cyber_news.utils.time import utc_now

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class MigrationRecord:
    """Applied database migration metadata."""

    version: str
    applied_at: str


@dataclass(frozen=True)
class MigrationResult:
    """Result of one migration run."""

    applied: tuple[str, ...]
    skipped: tuple[str, ...]


def run_migrations(sqlite_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> MigrationResult:
    """Run all unapplied migrations against the configured SQLite database."""
    connection = connect(sqlite_path)
    try:
        _ensure_migration_table(connection)
        applied_versions = _applied_versions(connection)
        applied: list[str] = []
        skipped: list[str] = []

        for migration_path in _migration_files(migrations_dir):
            version = migration_path.name
            if version in applied_versions:
                skipped.append(version)
                continue
            sql = migration_path.read_text(encoding="utf-8")
            if _apply_migration(connection, version, sql):
                applied.append(version)
                applied_versions.add(version)
            else:
                skipped.append(version)

        return MigrationResult(applied=tuple(applied), skipped=tuple(skipped))
    finally:
        connection.close()


def get_applied_migrations(sqlite_path: Path) -> tuple[MigrationRecord, ...]:
    """Return applied migration records ordered by version."""
    connection = connect(sqlite_path)
    try:
        _ensure_migration_table(connection)
        rows = connection.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version",
        ).fetchall()
    finally:
        connection.close()
    return tuple(
        MigrationRecord(version=row["version"], applied_at=row["applied_at"]) for row in rows
    )


def get_table_counts(sqlite_path: Path, tables: tuple[str, ...] | None = None) -> dict[str, int]:
    """Return row counts for known database tables."""
    connection = connect(sqlite_path)
    try:
        existing_tables = _existing_tables(connection)
        selected_tables = tables or tuple(sorted(existing_tables))
        counts: dict[str, int] = {}
        for table in selected_tables:
            if table not in existing_tables:
                counts[table] = 0
                continue
            row = connection.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
            counts[table] = int(row["count"])
    finally:
        connection.close()
    return counts


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    """Create the migration tracking table when absent."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """,
    )
    connection.commit()


def _apply_migration(connection: sqlite3.Connection, version: str, sql: str) -> bool:
    """Apply a migration and return whether this process recorded it."""
    try:
        with connection:
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, utc_now().isoformat()),
            )
    except sqlite3.IntegrityError as exc:
        if "schema_migrations.version" not in str(exc):
            raise
        connection.rollback()
        return False
    return True


def _applied_versions(connection: sqlite3.Connection) -> set[str]:
    """Return the set of already applied migration versions."""
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {str(row["version"]) for row in rows}


def _migration_files(migrations_dir: Path) -> tuple[Path, ...]:
    """Return migration files in deterministic order."""
    if not migrations_dir.exists():
        raise FileNotFoundError(f"Migrations directory does not exist: {migrations_dir}")
    return tuple(sorted(migrations_dir.glob("*.sql")))


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    """Return user-defined table names in the database."""
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """,
    ).fetchall()
    return {str(row["name"]) for row in rows}
