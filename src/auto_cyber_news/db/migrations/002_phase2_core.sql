-- Phase 2 persistence tables.

CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    summary TEXT,
    category TEXT,
    severity TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_source ON news(source);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at);
CREATE INDEX IF NOT EXISTS idx_news_severity ON news(severity);

CREATE TABLE IF NOT EXISTS sent_digest (
    id TEXT PRIMARY KEY,
    digest_date TEXT NOT NULL UNIQUE,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_sent_digest_sent_at ON sent_digest(sent_at);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
