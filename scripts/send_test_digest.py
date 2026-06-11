"""Render and send a daily digest through the package CLI."""

from __future__ import annotations

import sys

from auto_cyber_news.cli import main


def run() -> int:
    """Execute the digest workflow via the CLI entry point."""
    return main(["digest"])


if __name__ == "__main__":
    sys.exit(run())
