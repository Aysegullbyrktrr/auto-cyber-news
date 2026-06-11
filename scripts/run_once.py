"""Run one ingestion and analysis cycle through the package CLI."""

from __future__ import annotations

import sys

from auto_cyber_news.cli import main


def run() -> int:
    """Execute one ingestion and analysis cycle via the CLI entry point."""
    return main(["run-once"])


if __name__ == "__main__":
    sys.exit(run())
