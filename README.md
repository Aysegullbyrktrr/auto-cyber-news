# auto-cyber-news

Automated cybersecurity news aggregation and alerting platform.

## Overview

`auto-cyber-news` is designed to collect cybersecurity news from trusted RSS feeds and websites, deduplicate articles, categorize and score severity, store results in SQLite, send critical Telegram alerts, and generate a daily HTML email digest.

This repository currently contains the production-ready implementation skeleton. Business logic will be added incrementally by milestone.

## Stack

- Python 3.12+
- SQLite
- feedparser
- aiohttp
- BeautifulSoup4
- Jinja2
- python-telegram-bot
- python-dotenv
- Docker
- GitHub Actions

## Quick Start

```bash
make setup
make validate
```

## Planned Commands

```bash
python -m auto_cyber_news --help
python -m auto_cyber_news validate-config
python -m auto_cyber_news init-db
python -m auto_cyber_news run-once
python -m auto_cyber_news digest
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Execution Plan](docs/EXECUTION_PLAN.md)

## Status

Bootstrap skeleton only. No production business logic has been implemented yet.

