"""Run one ingestion cycle through the package pipeline."""

from __future__ import annotations

import asyncio

from auto_cyber_news.pipeline.ingest import run_ingestion


def main() -> None:
    """Execute one ingestion cycle."""
    asyncio.run(run_ingestion())


if __name__ == "__main__":
    main()

