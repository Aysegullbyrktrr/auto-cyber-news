# auto-cyber-news Execution Plan

## 1. Development Phases

### Phase 0: Repository Foundation

Goal: establish a clean, production-oriented project baseline.

Deliverables:

- Git repository initialized.
- Python package skeleton under `src/auto_cyber_news`.
- `pyproject.toml` with Python 3.12+ settings.
- Runtime and development dependencies declared.
- `.env.example`.
- `.gitignore`.
- Basic README.
- Initial documentation committed.

Exit criteria:

- `python -m auto_cyber_news --help` is planned and package layout is importable once code begins.
- CI skeleton exists.

### Phase 1: Configuration and Logging

Goal: create the configuration and observability foundation before business logic.

Deliverables:

- YAML config files for app, sources, categories, and severity rules.
- Config loader and validator.
- Environment variable overlay.
- Structured logging setup.
- CLI command for config validation.

Exit criteria:

- Invalid config fails clearly.
- Secrets are loaded only from environment or `.env`.
- Logs include environment, command, and correlation fields.

### Phase 2: SQLite Persistence

Goal: make storage explicit, testable, and migration-ready.

Deliverables:

- Initial SQLite schema.
- Database initialization command.
- Repository layer for sources, articles, categories, scores, alerts, digests, and fetch runs.
- Migration mechanism.
- Repository tests.

Exit criteria:

- Fresh database can be initialized.
- Schema can be validated in CI.
- Article, score, alert, and digest records are idempotent.

### Phase 3: Source Fetching and Normalization

Goal: fetch and normalize articles from all configured RSS sources first.

Deliverables:

- Async HTTP client wrapper.
- RSS fetcher using `feedparser`.
- Source registry.
- URL canonicalization.
- Title normalization.
- Article candidate model.
- Fixtures for representative RSS feeds.

Exit criteria:

- Each initial source can be fetched in a dry run.
- Fetch failures are isolated per source.
- Normalized output is source-agnostic.

### Phase 4: Deduplication

Goal: prevent duplicate articles from polluting storage and alerts.

Deliverables:

- Canonical URL deduplication.
- Content hash deduplication.
- Normalized title fallback matching.
- Duplicate observation storage.
- Tests for common URL tracking parameters and syndicated articles.

Exit criteria:

- Re-running ingestion does not duplicate articles.
- Duplicate records explain how the match happened.

### Phase 5: Categorization and Severity

Goal: classify articles and rank operational importance.

Deliverables:

- Keyword-based category engine.
- Weighted severity scoring engine.
- Explainable scoring reasons.
- Configurable severity thresholds.
- Tests for representative high-risk and low-risk stories.

Exit criteria:

- Every processed article has category and severity outputs.
- Critical classification can be traced to rules.

### Phase 6: Telegram Alerts

Goal: send fast, idempotent alerts for critical news.

Deliverables:

- Telegram notification client.
- Alert policy engine.
- Alert record persistence.
- Message template.
- Dry-run mode.
- Tests with mocked Telegram calls.

Exit criteria:

- Critical articles trigger one alert only.
- Failed sends are recorded and retryable.

### Phase 7: Email Digest

Goal: produce a useful daily HTML digest.

Deliverables:

- Digest article query.
- Jinja2 HTML template.
- Email notification client.
- Digest send records.
- Render-only mode.
- Tests for template rendering and digest idempotency.

Exit criteria:

- One digest per date is sent unless explicitly forced.
- Digest contains severity, categories, source, summary, and links.

### Phase 8: Docker and Operations

Goal: make local and production operation repeatable.

Deliverables:

- Dockerfile.
- docker-compose.yml.
- Mounted SQLite data volume.
- Container smoke command.
- Runtime documentation.
- Log and secret handling documentation.

Exit criteria:

- Application runs in Docker with mounted config and data.
- Container can run both one-shot and scheduled modes.

### Phase 9: CI/CD and Release Automation

Goal: automate quality gates and release packaging.

Deliverables:

- CI workflow.
- Docker build workflow.
- Optional scheduled workflow.
- Release workflow.
- Dependabot configuration if adopted.

Exit criteria:

- Pull requests run tests and config validation.
- Main branch builds a Docker image.
- Tags can produce releases.

### Phase 10: Hardening and Production Readiness

Goal: reduce operational risk before relying on alerts.

Deliverables:

- Backoff and retry tuning.
- Source health reporting.
- More realistic fixtures.
- Alert fatigue review.
- Data retention policy.
- Basic backup procedure for SQLite.
- Runbook.

Exit criteria:

- Known failure modes have clear logs.
- Database can be backed up and restored.
- Alert criteria are conservative enough for production.

## 2. Small Actionable Tasks

### Repository Setup

- Initialize Git repository.
- Add `.gitignore`.
- Add `README.md`.
- Add `pyproject.toml`.
- Add package skeleton under `src/auto_cyber_news`.
- Add `tests/` layout.
- Add `.env.example`.
- Add first CI workflow skeleton.

### Configuration

- Define `config/app.yml`.
- Define `config/sources.yml`.
- Define `config/categories.yml`.
- Define `config/severity.yml`.
- Implement config models.
- Implement config loader.
- Implement environment overlay.
- Add config validation CLI command.
- Add tests for missing required fields.

### Logging

- Add structured logging setup.
- Add JSON logging option.
- Add local pretty logging option.
- Redact secret-like values.
- Add log correlation fields.

### Database

- Write `schema.sql`.
- Add database connection helper.
- Add migration runner.
- Add repository tests with temporary SQLite database.
- Add source repository.
- Add article repository.
- Add scoring repository.
- Add alert repository.
- Add digest repository.
- Add fetch run repository.

### Fetching

- Add async HTTP wrapper.
- Add timeout and retry config.
- Add RSS fetcher.
- Add HTML fetcher placeholder.
- Add fetcher registry.
- Add RSS fixtures for each source.
- Add parser tests.

### Normalization

- Implement canonical URL function.
- Strip tracking parameters.
- Normalize titles.
- Normalize published timestamps.
- Compute content hash.
- Build article candidate model.

### Deduplication

- Check canonical URL duplicates.
- Check content hash duplicates.
- Add normalized title fallback rule.
- Store duplicate observations.
- Add idempotency tests.

### Categorization

- Define initial category keywords.
- Implement category matcher.
- Store category matches.
- Add confidence calculation.
- Add tests for multi-category articles.

### Severity

- Define initial scoring rules.
- Implement score engine.
- Persist score and reasons.
- Add threshold mapping.
- Add tests for critical, high, medium, and low scenarios.

### Telegram

- Add Telegram config validation.
- Implement Telegram client wrapper.
- Add critical alert policy.
- Add alert idempotency check.
- Add dry-run mode.
- Add mocked send tests.

### Email Digest

- Define digest query.
- Build HTML template.
- Implement SMTP client.
- Add render-only command.
- Store digest records.
- Add tests for digest uniqueness.

### Docker

- Add Dockerfile.
- Add docker-compose.yml.
- Add data volume mapping.
- Add container smoke test.
- Document local Docker usage.

### GitHub Actions

- Add CI workflow.
- Add Docker build workflow.
- Add optional scheduled digest workflow.
- Add release workflow.
- Configure secrets documentation.
- Add artifact upload for logs and rendered digest previews.

## 3. Suggested Commit Strategy

Use small commits that keep the project runnable or at least structurally coherent. Prefer one concern per commit.

Suggested sequence:

1. `docs: add architecture and execution plan`
2. `chore: initialize python project structure`
3. `chore: add dependency and tooling configuration`
4. `ci: add initial validation workflow`
5. `feat(config): add config files and validation`
6. `feat(logging): add structured logging setup`
7. `feat(db): add sqlite schema and initialization`
8. `feat(db): add repositories for core entities`
9. `feat(fetch): add async rss source fetching`
10. `feat(parse): add article normalization`
11. `feat(pipeline): add deduplication workflow`
12. `feat(pipeline): add categorization rules`
13. `feat(pipeline): add severity scoring`
14. `feat(alerts): add telegram critical alerts`
15. `feat(digest): add html email digest`
16. `chore(docker): add container runtime`
17. `ci: add docker build and release workflows`
18. `docs: add production runbook`

Commit rules:

- Keep generated artifacts out of commits unless intentionally versioned.
- Do not commit `.env`, production SQLite databases, or secrets.
- Include tests in the same commit as behavior changes.
- Prefer `feat`, `fix`, `test`, `docs`, `ci`, `chore`, and `refactor` prefixes.

## 4. Suggested GitHub Issue Structure

Use milestones that match the development phases.

### Milestone: Foundation

Issues:

- Initialize repository and Python package layout.
- Add dependency and tooling configuration.
- Add README and project documentation.
- Add `.env.example` and secret handling notes.
- Add initial CI workflow.

### Milestone: Configuration and Observability

Issues:

- Add YAML configuration files.
- Implement config loader and validation.
- Add environment variable overlay.
- Add structured logging.
- Add config validation CLI command.

### Milestone: Persistence

Issues:

- Design and add SQLite schema.
- Add migration runner.
- Add repository layer.
- Add fetch run audit records.
- Add database integration tests.

### Milestone: Ingestion

Issues:

- Implement async HTTP client wrapper.
- Implement RSS fetcher.
- Add source registry.
- Add RSS fixtures.
- Normalize article candidates.
- Add ingestion orchestration.

### Milestone: Deduplication and Classification

Issues:

- Implement URL canonicalization.
- Implement content hashing.
- Add deduplication service.
- Add duplicate observation records.
- Implement category rules.
- Implement severity scoring rules.

### Milestone: Notifications

Issues:

- Implement Telegram alert client.
- Add critical alert policy.
- Add alert idempotency.
- Implement HTML digest template.
- Implement SMTP email sender.
- Add digest idempotency.

### Milestone: Packaging and Deployment

Issues:

- Add Dockerfile.
- Add docker-compose.yml.
- Add runtime documentation.
- Add Docker build workflow.
- Add release workflow.
- Add optional scheduled workflow.

### Milestone: Production Hardening

Issues:

- Add retry and backoff tuning.
- Add source health reporting.
- Add backup and restore documentation.
- Add data retention policy.
- Add production runbook.
- Review alert thresholds with sample data.

## 5. Recommended First Sprint

The first sprint should avoid external integrations and focus on stable foundations.

Scope:

- Initialize Git repository.
- Add Python project skeleton.
- Add config files.
- Add config loader and validation.
- Add structured logging.
- Add SQLite schema and initialization.
- Add CI running lint and tests.

Non-goals:

- Real Telegram sends.
- Real email sends.
- HTML scraping.
- Complex severity heuristics.

Outcome:

The project has a durable base, a validated configuration model, a database schema, and enough CI to support safe feature development.

