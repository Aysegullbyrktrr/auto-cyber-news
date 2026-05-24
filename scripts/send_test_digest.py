"""Render or send a test digest through the package pipeline."""

from __future__ import annotations

from auto_cyber_news.pipeline.digest import send_digest


def main() -> None:
    """Execute the digest workflow."""
    send_digest()


if __name__ == "__main__":
    main()

