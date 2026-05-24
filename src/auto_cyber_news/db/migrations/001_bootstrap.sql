-- Bootstrap schema for auto-cyber-news.
-- Business logic is intentionally not implemented in this migration.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    url TEXT NOT NULL,
    homepage TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    reliability_weight REAL NOT NULL DEFAULT 1.0,
    last_fetched_at TEXT,
    last_success_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);
CREATE INDEX IF NOT EXISTS idx_sources_last_fetched_at ON sources(last_fetched_at);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    summary TEXT,
    content_hash TEXT UNIQUE,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    raw_payload TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_first_seen_at ON articles(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);

CREATE TABLE IF NOT EXISTS article_duplicates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    matched_by TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE INDEX IF NOT EXISTS idx_article_duplicates_article_id ON article_duplicates(article_id);
CREATE INDEX IF NOT EXISTS idx_article_duplicates_seen_at ON article_duplicates(seen_at);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_categories (
    article_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    matched_terms TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (article_id, category_id),
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS severity_scores (
    article_id TEXT PRIMARY KEY,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    reasons TEXT NOT NULL,
    scored_at TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_severity_scores_level ON severity_scores(level);
CREATE INDEX IF NOT EXISTS idx_severity_scores_score ON severity_scores(score);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    sent_at TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(article_id, channel),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);

CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    digest_date TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    html_path TEXT,
    sent_at TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digest_articles (
    digest_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (digest_id, article_id),
    FOREIGN KEY (digest_id) REFERENCES digests(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    sources_attempted INTEGER NOT NULL DEFAULT 0,
    sources_succeeded INTEGER NOT NULL DEFAULT 0,
    articles_seen INTEGER NOT NULL DEFAULT 0,
    articles_inserted INTEGER NOT NULL DEFAULT 0,
    duplicates_found INTEGER NOT NULL DEFAULT 0,
    critical_alerts_sent INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

