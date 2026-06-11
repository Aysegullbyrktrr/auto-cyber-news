# auto-cyber-news

Automated cybersecurity news aggregation and alerting platform.

## Overview

`auto-cyber-news` continuously collects cybersecurity news from trusted RSS
feeds, deduplicates articles across runs, extracts CVEs/CVSS, categorizes
threats, scores severity with explainable rules, groups related articles into
incidents, sends conservative critical Telegram alerts, and produces a daily
HTML email digest. A scheduler runs the whole cycle unattended.

## Features

- **Ingestion** — async RSS fetching with per-source failure isolation, bounded
  concurrency, retries, and a hard response-size cap.
- **Normalization & dedup** — canonical URLs, content hashing, and
  **cross-cycle persistent deduplication** so articles are never re-processed
  or re-alerted (and AI summaries are never re-billed).
- **Intelligence** — CVE + CVSS extraction, keyword categorization, and
  explainable severity scoring (0–100, with reasons).
- **Incidents** — related articles are grouped (Union-Find) into incidents.
- **AI summaries** — optional, multi-provider: Google Gemini (free tier) or
  Anthropic Claude, with a deterministic rule-based fallback and configurable
  output language (`SUMMARY_LANGUAGE`).
- **Alerting** — Telegram incident cards with DB-backed cooldown / escalation
  (no duplicate alerts), and a once-per-day email digest.
- **Operations** — scheduler with graceful shutdown and data retention,
  health-check command, structured JSON logging, Docker, and a systemd unit.

## Stack

- Python 3.12+ · asyncio
- SQLite (WAL)
- feedparser · aiohttp · BeautifulSoup4 · Jinja2
- python-telegram-bot · python-dotenv · PyYAML
- Google Gemini (REST) / Anthropic Claude SDK — optional AI summaries
- Docker · systemd · GitHub Actions

## Quick Start

### Linux / macOS

```bash
make setup
make validate
```

### Windows (PowerShell)

`make`, `python3`, and `.venv/bin/python` are not available on a default Windows
install, so use the bundled PowerShell task runner, which mirrors every Makefile
target with Windows-native paths:

```powershell
.\make.ps1 setup        # create .venv and install deps + the package
.\make.ps1 validate     # lint + typecheck + test
.\make.ps1 run-once     # run one ingestion + analysis cycle
.\make.ps1              # list all tasks
```

If `python` resolves to the Microsoft Store stub, pass the launcher explicitly:
`.\make.ps1 setup -Python py`. Python 3.12+ is required.

## Commands

Run via the package (`PYTHONPATH=src python -m auto_cyber_news <cmd>`) or the
task runner (`make <cmd>` / `.\make.ps1 <cmd>`):

| Command | Purpose |
| --- | --- |
| `validate-config` | Validate YAML + environment configuration |
| `init-db` / `migrate` | Initialize / apply SQLite migrations |
| `db-status` | Show migration state and table counts |
| `run-ingestion` | Fetch + normalize articles (JSON, no persistence) |
| `run-analysis` | Enrich normalized articles (JSON, no persistence) |
| `run-once` | Run one full cycle: ingest → enrich → incidents → alerts |
| `run-scheduler` | Run the continuous monitoring loop |
| `digest` | Render and send the daily email digest |
| `send-test-telegram` / `send-test-email` | Verify notification credentials |
| `health-check` | Report production health status as JSON |

## Configuration

Non-secret behavior lives in `config/*.yaml`; secrets and runtime overrides come
from the environment / `.env` (see [.env.example](.env.example)). AI summaries
activate when `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) is set; without a key the
deterministic rule-based summarizer is used.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Execution Plan](docs/EXECUTION_PLAN.md)
- [Deployment (24/7 on a Linux server)](docs/DEPLOYMENT.md)

## Status

Functional and production-hardened: the full ingest → enrich → incident →
alert/digest pipeline works, with persistent dedup, idempotent delivery,
retries, retention, Docker/systemd packaging, and a green test suite
(lint + mypy strict + pytest).

Known follow-ups: richer threat-actor/vendor extraction, full-text fetch,
broader dedup (http/https, AMP), category exclusion terms, metrics/monitoring,
and CI image publishing. Production checklist: rotate the Telegram token, keep
`.env` out of synced folders, and supply notification/AI secrets via the
environment.

