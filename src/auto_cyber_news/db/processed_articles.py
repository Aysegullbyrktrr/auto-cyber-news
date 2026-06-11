"""Cross-cycle article deduplication state.

The ingestion pipeline only deduplicates within a single cycle. For autonomous
24/7 operation the scheduler must also skip articles seen in *previous* cycles,
otherwise every run re-enriches (and re-bills the summarizer API for) and
potentially re-alerts the same news. This repository persists a compact fingerprint of
every processed article and answers "have we seen this before?".
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence

from auto_cyber_news.models.article import EnrichedArticle, NormalizedArticle
from auto_cyber_news.utils.time import utc_now

# SQLite limits a statement to 999 bound variables by default; stay well under.
_SQL_VARIABLE_CHUNK = 400


class ProcessedArticleRepository:
    """Repository tracking which articles have already been processed."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def filter_new(
        self,
        articles: Sequence[NormalizedArticle],
    ) -> tuple[NormalizedArticle, ...]:
        """Return only articles not seen before, touching ``last_seen_at`` for the rest.

        An article counts as "seen" if either its content hash or its canonical
        URL already exists, so trivially-rewritten URLs do not slip through.
        """
        if not articles:
            return ()

        hashes = [article.content_hash for article in articles if article.content_hash]
        urls = [article.canonical_url for article in articles if article.canonical_url]
        seen_hashes = self._existing_values("content_hash", hashes)
        seen_urls = self._existing_values("canonical_url", urls)

        new_articles: list[NormalizedArticle] = []
        seen_hash_keys: list[str] = []
        for article in articles:
            if article.content_hash in seen_hashes or article.canonical_url in seen_urls:
                if article.content_hash:
                    seen_hash_keys.append(article.content_hash)
                continue
            new_articles.append(article)

        if seen_hash_keys:
            self._touch(seen_hash_keys)
        return tuple(new_articles)

    def record(self, article: EnrichedArticle) -> None:
        """Persist a freshly processed article fingerprint (idempotent)."""
        now = utc_now().isoformat()
        self._connection.execute(
            """
            INSERT INTO processed_articles (
                content_hash, canonical_url, source_id, title,
                severity, risk_score, first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_hash) DO UPDATE SET
                severity = excluded.severity,
                risk_score = excluded.risk_score,
                last_seen_at = excluded.last_seen_at
            """,
            (
                article.article.content_hash,
                article.article.canonical_url,
                article.article.source_id,
                article.article.title,
                article.severity.value,
                article.risk_score,
                now,
                now,
            ),
        )

    def record_all(self, articles: Iterable[EnrichedArticle]) -> None:
        """Persist many processed articles."""
        for article in articles:
            self.record(article)

    def prune_older_than(self, cutoff_iso: str) -> int:
        """Delete processed rows whose ``last_seen_at`` is older than the cutoff."""
        cursor = self._connection.execute(
            "DELETE FROM processed_articles WHERE last_seen_at < ?",
            (cutoff_iso,),
        )
        return max(0, cursor.rowcount)

    def count(self) -> int:
        """Return the number of tracked processed articles."""
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM processed_articles",
        ).fetchone()
        return int(row["count"])

    def _existing_values(self, column: str, values: Sequence[str]) -> set[str]:
        """Return the subset of ``values`` already present in ``column``."""
        found: set[str] = set()
        unique_values = list(dict.fromkeys(value for value in values if value))
        for start in range(0, len(unique_values), _SQL_VARIABLE_CHUNK):
            chunk = unique_values[start : start + _SQL_VARIABLE_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._connection.execute(
                f"SELECT {column} AS value FROM processed_articles "  # noqa: S608
                f"WHERE {column} IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
            found.update(str(row["value"]) for row in rows)
        return found

    def _touch(self, content_hashes: Sequence[str]) -> None:
        """Update ``last_seen_at`` for previously-seen articles."""
        now = utc_now().isoformat()
        unique_hashes = list(dict.fromkeys(content_hashes))
        for start in range(0, len(unique_hashes), _SQL_VARIABLE_CHUNK):
            chunk = unique_hashes[start : start + _SQL_VARIABLE_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            self._connection.execute(
                f"UPDATE processed_articles SET last_seen_at = ? "  # noqa: S608
                f"WHERE content_hash IN ({placeholders})",
                (now, *chunk),
            )
