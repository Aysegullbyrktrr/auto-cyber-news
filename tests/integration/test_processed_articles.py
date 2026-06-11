"""Integration tests for cross-cycle article deduplication state."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.db.connection import session
from auto_cyber_news.db.migrations import run_migrations
from auto_cyber_news.db.processed_articles import ProcessedArticleRepository
from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle, SeverityLevel


def _article(
    index: int, *, canonical: str | None = None, content_hash: str | None = None
) -> NormalizedArticle:
    url = f"https://example.com/{index}"
    return NormalizedArticle(
        title=f"Story {index}",
        url=url,
        canonical_url=canonical or url,
        content_hash=content_hash or f"hash-{index}",
        published_at=None,
        source="Example",
        source_id="example",
        raw_content=None,
        summary_placeholder="",
        category_placeholder="uncategorized",
    )


def _enriched(article: NormalizedArticle) -> EnrichedArticle:
    return EnrichedArticle(
        article=article,
        severity=SeverityLevel.LOW,
        detected_cves=(),
        categories=(),
        risk_score=10,
        ai_summary="summary",
        is_critical=False,
        should_alert_telegram=False,
        should_include_in_email_digest=False,
        severity_reasons=(),
    )


def test_filter_new_skips_articles_seen_in_earlier_cycles(tmp_path: Path) -> None:
    """Articles recorded in one cycle must not be re-processed in the next."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    with session(sqlite_path) as connection:
        repository = ProcessedArticleRepository(connection)
        first_batch = (_article(1), _article(2))
        new_first = repository.filter_new(first_batch)
        assert {article.content_hash for article in new_first} == {"hash-1", "hash-2"}
        repository.record_all(_enriched(article) for article in new_first)

    with session(sqlite_path) as connection:
        repository = ProcessedArticleRepository(connection)
        second_batch = (_article(1), _article(2), _article(3))
        new_second = repository.filter_new(second_batch)
        assert tuple(article.content_hash for article in new_second) == ("hash-3",)
        assert repository.count() == 2


def test_filter_new_treats_known_canonical_url_as_seen(tmp_path: Path) -> None:
    """A new content hash on an already-seen canonical URL is still a duplicate."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    with session(sqlite_path) as connection:
        repository = ProcessedArticleRepository(connection)
        original = _article(1, canonical="https://example.com/a", content_hash="hash-a")
        repository.record(_enriched(original))

    with session(sqlite_path) as connection:
        repository = ProcessedArticleRepository(connection)
        rewritten = _article(1, canonical="https://example.com/a", content_hash="hash-a-edited")
        assert repository.filter_new((rewritten,)) == ()


def test_prune_older_than_removes_stale_rows(tmp_path: Path) -> None:
    """Pruning with a future cutoff clears all processed rows."""
    sqlite_path = tmp_path / "app.db"
    run_migrations(sqlite_path)

    with session(sqlite_path) as connection:
        repository = ProcessedArticleRepository(connection)
        repository.record(_enriched(_article(1)))
        repository.record(_enriched(_article(2)))
        assert repository.count() == 2

        removed = repository.prune_older_than("9999-01-01T00:00:00+00:00")
        assert removed == 2
        assert repository.count() == 0
