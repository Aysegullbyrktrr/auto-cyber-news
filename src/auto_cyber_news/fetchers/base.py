"""Base fetcher protocols."""

from __future__ import annotations

from typing import Protocol

from auto_cyber_news.models.article import RawFeedItem
from auto_cyber_news.models.source import Source


class SourceFetcher(Protocol):
    """Protocol implemented by source fetchers."""

    async def fetch(self, source: Source) -> list[RawFeedItem]:
        """Fetch raw items from a source."""
        ...
