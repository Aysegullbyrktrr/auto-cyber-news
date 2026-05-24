"""Repository interfaces and SQLite implementations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from auto_cyber_news.utils.time import utc_now


@dataclass(frozen=True)
class NewsRecord:
    """Persisted news row."""

    id: str
    title: str
    url: str
    source: str
    summary: str | None = None
    category: str | None = None
    severity: str | None = None
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class DigestRecord:
    """Persisted sent digest row."""

    id: str
    digest_date: str
    recipient: str
    subject: str
    sent_at: str
    article_count: int
    metadata: dict[str, object] | None = None


class NewsRepository(Protocol):
    """Repository interface for news records."""

    def create(self, record: NewsRecord) -> NewsRecord:
        """Create a news record."""
        ...

    def get(self, news_id: str) -> NewsRecord | None:
        """Return a news record by id."""
        ...

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[NewsRecord, ...]:
        """List news records in reverse creation order."""
        ...

    def update(self, record: NewsRecord) -> NewsRecord:
        """Update an existing news record."""
        ...

    def delete(self, news_id: str) -> bool:
        """Delete a news record by id."""
        ...

    def count(self) -> int:
        """Return total news record count."""
        ...


class DigestRepository(Protocol):
    """Repository interface for sent digest records."""

    def create(self, record: DigestRecord) -> DigestRecord:
        """Create a sent digest record."""
        ...

    def get_by_date(self, digest_date: str) -> DigestRecord | None:
        """Return a sent digest record by digest date."""
        ...

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[DigestRecord, ...]:
        """List sent digest records in reverse sent order."""
        ...

    def delete(self, digest_id: str) -> bool:
        """Delete a sent digest record by id."""
        ...

    def count(self) -> int:
        """Return total sent digest count."""
        ...


@dataclass(frozen=True)
class RepositoryRegistry:
    """Collection of repositories used by infrastructure callers."""

    news: NewsRepository
    digests: DigestRepository


class SQLiteNewsRepository:
    """SQLite implementation of the news repository."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Initialize the repository with an active connection."""
        self._connection = connection

    def create(self, record: NewsRecord) -> NewsRecord:
        """Create a news record."""
        created_at = record.created_at or utc_now().isoformat()
        updated_at = record.updated_at or created_at
        stored = NewsRecord(
            id=record.id,
            title=record.title,
            url=record.url,
            source=record.source,
            summary=record.summary,
            category=record.category,
            severity=record.severity,
            published_at=record.published_at,
            created_at=created_at,
            updated_at=updated_at,
        )
        self._connection.execute(
            """
            INSERT INTO news (
                id, title, url, source, summary, category, severity,
                published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored.id,
                stored.title,
                stored.url,
                stored.source,
                stored.summary,
                stored.category,
                stored.severity,
                stored.published_at,
                stored.created_at,
                stored.updated_at,
            ),
        )
        return stored

    def get(self, news_id: str) -> NewsRecord | None:
        """Return a news record by id."""
        row = self._connection.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
        return _news_from_row(row) if row is not None else None

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[NewsRecord, ...]:
        """List news records in reverse creation order."""
        rows = self._connection.execute(
            "SELECT * FROM news ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return tuple(_news_from_row(row) for row in rows)

    def update(self, record: NewsRecord) -> NewsRecord:
        """Update an existing news record."""
        updated_at = utc_now().isoformat()
        self._connection.execute(
            """
            UPDATE news
            SET title = ?,
                url = ?,
                source = ?,
                summary = ?,
                category = ?,
                severity = ?,
                published_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                record.title,
                record.url,
                record.source,
                record.summary,
                record.category,
                record.severity,
                record.published_at,
                updated_at,
                record.id,
            ),
        )
        updated = self.get(record.id)
        if updated is None:
            raise KeyError(record.id)
        return updated

    def delete(self, news_id: str) -> bool:
        """Delete a news record by id."""
        cursor = self._connection.execute("DELETE FROM news WHERE id = ?", (news_id,))
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return total news record count."""
        row = self._connection.execute("SELECT COUNT(*) AS count FROM news").fetchone()
        return int(row["count"])


class SQLiteDigestRepository:
    """SQLite implementation of the sent digest repository."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Initialize the repository with an active connection."""
        self._connection = connection

    def create(self, record: DigestRecord) -> DigestRecord:
        """Create a sent digest record."""
        self._connection.execute(
            """
            INSERT INTO sent_digest (
                id, digest_date, recipient, subject, sent_at, article_count, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.digest_date,
                record.recipient,
                record.subject,
                record.sent_at,
                record.article_count,
                _metadata_to_json(record.metadata),
            ),
        )
        return record

    def get_by_date(self, digest_date: str) -> DigestRecord | None:
        """Return a sent digest record by digest date."""
        row = self._connection.execute(
            "SELECT * FROM sent_digest WHERE digest_date = ?",
            (digest_date,),
        ).fetchone()
        return _digest_from_row(row) if row is not None else None

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[DigestRecord, ...]:
        """List sent digest records in reverse sent order."""
        rows = self._connection.execute(
            "SELECT * FROM sent_digest ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return tuple(_digest_from_row(row) for row in rows)

    def delete(self, digest_id: str) -> bool:
        """Delete a sent digest record by id."""
        cursor = self._connection.execute("DELETE FROM sent_digest WHERE id = ?", (digest_id,))
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return total sent digest count."""
        row = self._connection.execute("SELECT COUNT(*) AS count FROM sent_digest").fetchone()
        return int(row["count"])


def create_repositories(connection: sqlite3.Connection) -> RepositoryRegistry:
    """Create concrete repositories for an active SQLite connection."""
    return RepositoryRegistry(
        news=SQLiteNewsRepository(connection),
        digests=SQLiteDigestRepository(connection),
    )


def _news_from_row(row: sqlite3.Row) -> NewsRecord:
    """Build a news record from a SQLite row."""
    return NewsRecord(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        summary=row["summary"],
        category=row["category"],
        severity=row["severity"],
        published_at=row["published_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _digest_from_row(row: sqlite3.Row) -> DigestRecord:
    """Build a digest record from a SQLite row."""
    metadata = row["metadata"]
    return DigestRecord(
        id=row["id"],
        digest_date=row["digest_date"],
        recipient=row["recipient"],
        subject=row["subject"],
        sent_at=row["sent_at"],
        article_count=row["article_count"],
        metadata=json.loads(metadata) if metadata else None,
    )


def _metadata_to_json(metadata: dict[str, object] | None) -> str | None:
    """Serialize optional digest metadata."""
    if metadata is None:
        return None
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"))
