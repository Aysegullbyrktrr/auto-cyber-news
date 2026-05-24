"""Module entry point for ``python -m auto_cyber_news``."""

from __future__ import annotations

import sys

from auto_cyber_news.cli import main

if __name__ == "__main__":
    sys.exit(main())
