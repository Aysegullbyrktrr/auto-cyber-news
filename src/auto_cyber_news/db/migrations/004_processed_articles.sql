-- Cross-cycle article deduplication and processed-state tracking.
-- Lets the scheduler skip already-seen articles before enrichment so the
-- pipeline never re-summarizes (re-bills the summarizer API) or re-alerts old news.

CREATE TABLE IF NOT EXISTS processed_articles (
    content_hash TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT,
    risk_score INTEGER,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_processed_articles_canonical_url
    ON processed_articles(canonical_url);
CREATE INDEX IF NOT EXISTS idx_processed_articles_last_seen_at
    ON processed_articles(last_seen_at);
