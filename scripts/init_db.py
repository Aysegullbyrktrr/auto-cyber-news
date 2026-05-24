"""Initialize the SQLite database through the package migration runner."""

from __future__ import annotations

from pathlib import Path

from auto_cyber_news.db.migrations import run_migrations


def main() -> None:
    """Run database initialization using the default local path."""
    run_migrations(Path("data/auto-cyber-news.db"))


if __name__ == "__main__":
    main()

