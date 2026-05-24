"""HTML fetcher placeholder."""

from __future__ import annotations

from auto_cyber_news.models.source import Source


class HtmlFetcher:
    """Async-ready HTML fetcher."""

    async def fetch(self, source: Source) -> list[dict[str, object]]:
        """Fetch HTML items from a source."""
        raise NotImplementedError(f"HTML fetching is not implemented yet: {source.id}")
