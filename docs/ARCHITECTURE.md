# auto-cyber-news Architecture

## 1. System Overview

`auto-cyber-news` is an automated cybersecurity news aggregation and alerting platform. It collects articles from trusted cybersecurity sources, normalizes and deduplicates them, categorizes and scores their severity, stores them in SQLite, sends critical Telegram alerts quickly, and produces a daily HTML email digest.

The system is designed as a config-driven Python 3.12+ application with an async-first ingestion pipeline, structured logging, Docker support, and GitHub Actions CI/CD.

## 2. Primary Capabilities

- Aggregate cybersecurity news from RSS feeds and selected websites.
- Normalize source-specific article metadata into a common article model.
- Deduplicate articles by canonical URL, normalized title, and content fingerprint.
- Categorize articles by cybersecurity topic.
- Score severity using deterministic rules first, with room for later ML/LLM enrichment.
- Store sources, articles, categories, severity scores, alerts, and digest history in SQLite.
- Send instant Telegram alerts for critical news.
- Send a daily HTML email digest.
- Run locally, in Docker, from cron, or from GitHub Actions.
- Support structured JSON logs for production observability.

## 3. Target Sources

Initial source set:

- The Hacker News
- BleepingComputer
- KrebsOnSecurity
- DarkReading
- SecurityWeek
- Cisco Talos
- SANS ISC

Each source should be represented in configuration with:

- `id`
- `name`
- `enabled`
- `type`: `rss`, `html`, or future adapter type
- `url`
- `homepage`
- `poll_interval_minutes`
- `category_hints`
- `reliability_weight`
- `rate_limit`
- optional parsing overrides

## 4. Proposed Directory Structure

```text
auto-cyber-news/
  README.md
  pyproject.toml
  requirements.txt
  requirements-dev.txt
  .env.example
  .gitignore
  Dockerfile
  docker-compose.yml
  config/
    sources.yml
    categories.yml
    severity.yml
    app.yml
  docs/
    ARCHITECTURE.md
    EXECUTION_PLAN.md
  src/
    auto_cyber_news/
      __init__.py
      __main__.py
      cli.py
      app.py
      config/
        __init__.py
        loader.py
        models.py
        validation.py
      logging/
        __init__.py
        setup.py
      db/
        __init__.py
        connection.py
        migrations.py
        repositories.py
        schema.sql
      models/
        __init__.py
        article.py
        source.py
        alert.py
        digest.py
      fetchers/
        __init__.py
        base.py
        rss.py
        html.py
        registry.py
      parsers/
        __init__.py
        normalizer.py
        content.py
        canonical_url.py
      pipeline/
        __init__.py
        ingest.py
        deduplicate.py
        categorize.py
        score.py
        alert.py
        digest.py
      notifications/
        __init__.py
        telegram.py
        email.py
      templates/
        email_digest.html.j2
      scheduler/
        __init__.py
        runner.py
      utils/
        __init__.py
        time.py
        hashing.py
        http.py
  tests/
    unit/
    integration/
    fixtures/
  scripts/
    init_db.py
    run_once.py
    send_test_digest.py
  .github/
    workflows/
      ci.yml
      docker.yml
      scheduled-digest.yml
      release.yml
```

## 5. Module Responsibilities

### `cli.py`

Command-line interface for operational commands:

- `run-once`: fetch, process, alert, and persist current articles.
- `digest`: generate and send daily digest.
- `init-db`: initialize SQLite schema.
- `validate-config`: validate YAML and environment configuration.
- `sources`: list configured sources and health status.

### `app.py`

Application composition root. Loads configuration, initializes logging, creates database connection, wires repositories, fetchers, pipeline services, and notification clients.

### `config/`

Loads and validates configuration from YAML files and environment variables. Configuration files define source behavior, categories, severity rules, runtime limits, and notification settings. Environment variables hold secrets and deployment-specific values.

### `logging/`

Central structured logging setup. Production logs should be JSON. Local development can use human-readable console output.

### `db/`

SQLite connection management, schema initialization, migration runner, and repository classes. Repositories should hide SQL details from pipeline logic.

### `models/`

Internal domain models for source definitions, raw fetched items, normalized articles, scoring results, alert events, and digest records.

### `fetchers/`

Async source fetching. RSS sources use `feedparser`; HTML sources use `aiohttp` plus BeautifulSoup4. Fetchers return raw source items and do not own business logic.

### `parsers/`

Article normalization:

- clean title
- canonicalize URL
- extract summary
- parse dates
- normalize source names
- compute content fingerprint

### `pipeline/`

Business workflow stages:

- ingestion orchestration
- deduplication
- categorization
- severity scoring
- critical alert decisioning
- digest selection

### `notifications/`

External notification integrations:

- Telegram critical alerts through `python-telegram-bot`
- HTML email digest through SMTP

Notification modules should be idempotency-aware and record sent alerts/digests.

### `scheduler/`

Runtime scheduling for container or long-running process mode. GitHub Actions can call CLI commands directly without this module.

### `templates/`

Jinja2 templates for HTML email output.

### `scripts/`

Thin operational helpers. These should call the package CLI/application code rather than duplicating logic.

## 6. Database Schema

SQLite is the source of truth. Use explicit migrations from the start, even if migration support is minimal in v1.

### `sources`

Stores configured source metadata and runtime state.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | Stable source id, e.g. `the_hacker_news` |
| `name` | TEXT NOT NULL | Human-readable name |
| `type` | TEXT NOT NULL | `rss` or `html` |
| `url` | TEXT NOT NULL | Feed or page URL |
| `homepage` | TEXT | Source homepage |
| `enabled` | INTEGER NOT NULL DEFAULT 1 | Boolean |
| `reliability_weight` | REAL NOT NULL DEFAULT 1.0 | Used in scoring |
| `last_fetched_at` | TEXT | ISO-8601 UTC timestamp |
| `last_success_at` | TEXT | ISO-8601 UTC timestamp |
| `last_error` | TEXT | Latest fetch/parse error |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |
| `updated_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Indexes:

- `idx_sources_enabled`
- `idx_sources_last_fetched_at`

### `articles`

Canonical article records after normalization and deduplication.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID or deterministic hash |
| `source_id` | TEXT NOT NULL | FK to `sources.id` |
| `title` | TEXT NOT NULL | Normalized title |
| `normalized_title` | TEXT NOT NULL | Deduplication key material |
| `url` | TEXT NOT NULL | Original URL |
| `canonical_url` | TEXT NOT NULL | Canonical URL without tracking params |
| `summary` | TEXT | Source summary or extracted excerpt |
| `content_hash` | TEXT | Hash from title, URL, and summary/content |
| `published_at` | TEXT | Source published timestamp |
| `fetched_at` | TEXT NOT NULL | Fetch timestamp |
| `first_seen_at` | TEXT NOT NULL | First observed timestamp |
| `last_seen_at` | TEXT NOT NULL | Last observed timestamp |
| `status` | TEXT NOT NULL DEFAULT 'new' | `new`, `processed`, `archived`, `ignored` |
| `raw_payload` | TEXT | JSON payload for debugging |

Constraints and indexes:

- `UNIQUE(canonical_url)`
- `UNIQUE(content_hash)` where available
- `idx_articles_published_at`
- `idx_articles_first_seen_at`
- `idx_articles_source_id`
- `idx_articles_status`

### `article_duplicates`

Tracks duplicate observations mapped to canonical articles.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Internal id |
| `article_id` | TEXT NOT NULL | Canonical article id |
| `source_id` | TEXT NOT NULL | Source where duplicate appeared |
| `url` | TEXT NOT NULL | Duplicate URL |
| `title` | TEXT NOT NULL | Duplicate title |
| `matched_by` | TEXT NOT NULL | `canonical_url`, `content_hash`, `title_similarity` |
| `seen_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Indexes:

- `idx_article_duplicates_article_id`
- `idx_article_duplicates_seen_at`

### `categories`

Configured categories.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | e.g. `ransomware` |
| `name` | TEXT NOT NULL | Display name |
| `description` | TEXT | Optional explanation |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

### `article_categories`

Many-to-many mapping between articles and categories.

| Column | Type | Notes |
| --- | --- | --- |
| `article_id` | TEXT NOT NULL | FK to `articles.id` |
| `category_id` | TEXT NOT NULL | FK to `categories.id` |
| `confidence` | REAL NOT NULL | Rule confidence |
| `matched_terms` | TEXT | JSON array |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Primary key:

- `(article_id, category_id)`

### `severity_scores`

Stores scoring output and explainability.

| Column | Type | Notes |
| --- | --- | --- |
| `article_id` | TEXT PRIMARY KEY | FK to `articles.id` |
| `score` | INTEGER NOT NULL | 0-100 |
| `level` | TEXT NOT NULL | `info`, `low`, `medium`, `high`, `critical` |
| `reasons` | TEXT NOT NULL | JSON array of matched rules |
| `scored_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Indexes:

- `idx_severity_scores_level`
- `idx_severity_scores_score`

### `alerts`

Records Telegram or other instant alerts.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID |
| `article_id` | TEXT NOT NULL | FK to `articles.id` |
| `channel` | TEXT NOT NULL | `telegram` |
| `status` | TEXT NOT NULL | `pending`, `sent`, `failed`, `skipped` |
| `reason` | TEXT | Alert trigger explanation |
| `sent_at` | TEXT | ISO-8601 UTC timestamp |
| `error` | TEXT | Failure detail |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Constraints and indexes:

- `UNIQUE(article_id, channel)`
- `idx_alerts_status`
- `idx_alerts_created_at`

### `digests`

Daily digest send records.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID |
| `digest_date` | TEXT NOT NULL | YYYY-MM-DD |
| `status` | TEXT NOT NULL | `pending`, `sent`, `failed` |
| `article_count` | INTEGER NOT NULL DEFAULT 0 | Included articles |
| `html_path` | TEXT | Optional rendered artifact path |
| `sent_at` | TEXT | ISO-8601 UTC timestamp |
| `error` | TEXT | Failure detail |
| `created_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |

Constraints:

- `UNIQUE(digest_date)`

### `digest_articles`

Articles included in each digest.

| Column | Type | Notes |
| --- | --- | --- |
| `digest_id` | TEXT NOT NULL | FK to `digests.id` |
| `article_id` | TEXT NOT NULL | FK to `articles.id` |
| `position` | INTEGER NOT NULL | Sort order |

Primary key:

- `(digest_id, article_id)`

### `fetch_runs`

Operational audit table for each ingestion run.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID |
| `started_at` | TEXT NOT NULL | ISO-8601 UTC timestamp |
| `finished_at` | TEXT | ISO-8601 UTC timestamp |
| `status` | TEXT NOT NULL | `running`, `success`, `partial`, `failed` |
| `sources_attempted` | INTEGER NOT NULL DEFAULT 0 | Count |
| `sources_succeeded` | INTEGER NOT NULL DEFAULT 0 | Count |
| `articles_seen` | INTEGER NOT NULL DEFAULT 0 | Raw items |
| `articles_inserted` | INTEGER NOT NULL DEFAULT 0 | New canonical articles |
| `duplicates_found` | INTEGER NOT NULL DEFAULT 0 | Duplicate observations |
| `critical_alerts_sent` | INTEGER NOT NULL DEFAULT 0 | Count |
| `error` | TEXT | Run-level failure |

## 7. Configuration Strategy

Use layered configuration:

1. Static YAML files for non-secret application behavior.
2. `.env` for local secret/runtime values.
3. Real environment variables for Docker, CI, and production.

Precedence:

```text
defaults < YAML config < .env < environment variables < CLI flags
```

### Static Config Files

`config/app.yml`

- database path
- logging format and level
- concurrency limits
- HTTP timeout and retry policy
- digest schedule defaults
- timezone

`config/sources.yml`

- source ids
- feed URLs
- enabled flags
- source weights
- rate limits
- parser type

`config/categories.yml`

- category ids
- names
- keywords
- weighted terms
- exclusion terms

`config/severity.yml`

- scoring rules
- thresholds
- critical alert criteria
- category multipliers
- source reliability multipliers

### Environment Variables

Required for production notifications:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

Runtime:

- `APP_ENV`
- `LOG_LEVEL`
- `DATABASE_URL` or `SQLITE_PATH`
- `CONFIG_DIR`
- `DIGEST_TIMEZONE`

GitHub Actions:

- repository secrets for Telegram and SMTP values
- optional artifact retention configuration

## 8. Categorization Strategy

Start deterministic and explainable.

Initial categories:

- Vulnerability
- Exploit
- Ransomware
- Malware
- Phishing
- Data Breach
- Nation-State
- Supply Chain
- Cloud Security
- Identity and Access
- Patch Tuesday
- Threat Intelligence
- Policy and Regulation

Rules should support:

- keyword match in title
- keyword match in summary
- weighted terms
- negative terms
- source category hints
- confidence score

The category engine should return all matching categories with confidence, not just one category.

## 9. Severity Scoring Strategy

Use a 0-100 score with explainable rule matches.

Suggested levels:

- `info`: 0-19
- `low`: 20-39
- `medium`: 40-59
- `high`: 60-79
- `critical`: 80-100

Example scoring signals:

- Active exploitation: high positive weight.
- Known ransomware campaign: high positive weight.
- Widespread product impact: positive weight.
- Critical CVE/CVSS terms: positive weight.
- Emergency patch / out-of-band fix: positive weight.
- Data breach with large affected population: positive weight.
- Nation-state attribution: positive weight.
- Source reliability: multiplier or small adjustment.
- Repeated source coverage: positive adjustment when multiple sources report similar item.
- Opinion, recap, podcast, or sponsored content: negative adjustment.

Critical Telegram alert criteria:

- severity level is `critical`
- article has not already been alerted
- source is trusted and enabled
- article is not older than configured freshness threshold

## 10. Async Workflow

The ingestion path should be async-first, with synchronous libraries isolated where necessary.

### Run Once Workflow

1. Load and validate configuration.
2. Initialize structured logging.
3. Open SQLite connection.
4. Create `fetch_runs` record.
5. Select enabled sources due for polling.
6. Fetch sources concurrently with bounded concurrency.
7. Parse RSS/HTML results into raw source items.
8. Normalize raw items into article candidates.
9. Canonicalize URLs and compute fingerprints.
10. Deduplicate candidates against existing SQLite records.
11. Insert new articles and duplicate observations.
12. Categorize new articles.
13. Score severity for new articles.
14. Send Telegram alerts for critical unalerted articles.
15. Update source health and fetch run metrics.
16. Close resources cleanly.

### Digest Workflow

1. Load configuration.
2. Query articles from the digest window.
3. Join severity and category data.
4. Sort by severity, published time, and source weight.
5. Render HTML with Jinja2.
6. Send email through SMTP.
7. Record digest status and included articles.
8. Store rendered digest artifact if configured.

### Async Boundaries

Async:

- HTTP fetches with `aiohttp`
- Telegram API calls
- concurrent source orchestration

Sync:

- `feedparser` parsing
- BeautifulSoup parsing
- SQLite writes unless using an async wrapper
- Jinja2 rendering
- SMTP unless an async mail library is later introduced

SQLite writes should be serialized through repository methods to avoid lock contention.

## 11. Deployment Strategy

### Local Development

- Python virtual environment.
- `.env` loaded by `python-dotenv`.
- SQLite database in `./data/auto-cyber-news.db`.
- CLI commands for `init-db`, `run-once`, and `digest`.

### Docker

Use a slim Python 3.12 base image.

Container responsibilities:

- install runtime dependencies
- copy application and config
- run CLI commands
- mount `data/` volume for SQLite persistence
- accept secrets through environment variables

Suggested services:

- `app`: long-running scheduler mode, optional
- `run-once`: one-shot ingestion command
- `digest`: one-shot digest command

### GitHub Actions Scheduled Mode

For a lightweight v1, GitHub Actions can run:

- ingestion every 30-60 minutes
- digest once daily

Important caveat:

SQLite persistence in GitHub Actions is not durable unless stored externally or committed/artifacted. Production should use a persistent host, mounted Docker volume, or a small VM. GitHub Actions is good for CI and scheduled tests; it is only acceptable for production if persistence is handled explicitly.

### Production Recommendation

Recommended production deployment:

- Docker container on a VPS, NAS, or small cloud VM.
- Persistent Docker volume for SQLite.
- Cron or container scheduler for `run-once` and `digest`.
- Logs shipped from stdout/stderr.
- Secrets passed through environment variables.

## 12. GitHub Actions Workflows

### `.github/workflows/ci.yml`

Purpose:

- validate formatting
- run linting
- run type checks
- run unit tests
- run integration tests that do not require network or real secrets
- validate config files

Triggers:

- pull request
- push to `main`

Jobs:

- setup Python 3.12
- install dependencies
- run `ruff format --check`
- run `ruff check`
- run `mypy` if adopted
- run `pytest`
- run config validation command

### `.github/workflows/docker.yml`

Purpose:

- build Docker image
- optionally push to GitHub Container Registry

Triggers:

- push to `main`
- tags
- manual dispatch

Jobs:

- build image
- run smoke test command in container
- push image on release/tag

### `.github/workflows/scheduled-digest.yml`

Purpose:

- optional scheduled ingestion and digest execution

Triggers:

- cron schedule
- manual dispatch

Jobs:

- setup Python
- restore or provision database if using artifact-based persistence
- run ingestion
- run digest at configured time
- upload logs and rendered digest artifacts

Production warning:

This workflow should not be the primary production scheduler unless database persistence is explicitly solved.

### `.github/workflows/release.yml`

Purpose:

- tag-based release automation
- changelog generation
- container publication

Triggers:

- pushed tags like `v*.*.*`

Jobs:

- run CI checks
- build Docker image
- publish image
- create GitHub release

## 13. Operational Concerns

### Idempotency

- Article insertions must be idempotent by canonical URL and content hash.
- Telegram alerts must be idempotent by `(article_id, channel)`.
- Daily digest must be idempotent by `digest_date`.

### Reliability

- Source failures should not fail the full run unless all sources fail.
- Each fetch run should record partial success.
- HTTP requests need timeout, retry, and user-agent configuration.
- HTML parsing should degrade gracefully.

### Observability

Structured logs should include:

- run id
- source id
- article id
- event name
- duration
- error class
- status

Metrics can initially be log-derived.

### Security

- Never commit `.env` or SQLite production database.
- Use GitHub repository secrets for CI/CD secrets.
- Redact tokens and SMTP credentials from logs.
- Sanitize HTML rendered from external article fields.
- Pin dependencies reasonably and scan with Dependabot or equivalent.

### Testing Strategy

Unit tests:

- URL canonicalization
- title normalization
- content hashing
- deduplication rules
- categorization rules
- severity scoring
- template rendering

Integration tests:

- SQLite schema and repositories
- RSS parsing from fixtures
- end-to-end run with mocked fetch responses
- Telegram/email clients with mocked transports

Smoke tests:

- config validation
- CLI command help
- Docker image starts

