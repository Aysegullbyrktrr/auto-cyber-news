"""Integration tests for SQLite repositories."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.db.connection import session
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.repositories import DigestRecord, NewsRecord, create_repositories


def test_news_repository_crud(tmp_path: Path) -> None:
    """News repository should support basic CRUD operations."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    with session(sqlite_path) as connection:
        repositories = create_repositories(connection)
        created = repositories.news.create(
            NewsRecord(
                id="news-1",
                title="Initial title",
                url="https://example.com/news-1",
                source="example",
            ),
        )
        updated = repositories.news.update(
            NewsRecord(
                id="news-1",
                title="Updated title",
                url=created.url,
                source=created.source,
                summary="Updated summary",
            ),
        )

        assert repositories.news.count() == 1
        assert repositories.news.get("news-1") == updated
        assert repositories.news.list() == (updated,)
        assert updated.title == "Updated title"
        assert repositories.news.delete("news-1") is True
        assert repositories.news.get("news-1") is None


def test_digest_repository_tracking(tmp_path: Path) -> None:
    """Digest repository should track sent digest records by date."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    with session(sqlite_path) as connection:
        repositories = create_repositories(connection)
        record = DigestRecord(
            id="digest-1",
            digest_date="2026-05-24",
            recipient="security@example.com",
            subject="Daily Cyber Digest",
            sent_at="2026-05-24T08:00:00+00:00",
            article_count=3,
            metadata={"mode": "test"},
        )

        repositories.digests.create(record)

        assert repositories.digests.count() == 1
        assert repositories.digests.get_by_date("2026-05-24") == record
        assert repositories.digests.list() == (record,)
        assert repositories.digests.delete("digest-1") is True
        assert repositories.digests.count() == 0
