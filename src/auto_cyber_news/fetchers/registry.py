"""Fetcher registry."""

from __future__ import annotations

from auto_cyber_news.fetchers.base import SourceFetcher
from auto_cyber_news.fetchers.http import AsyncHttpClient, HttpClientConfig
from auto_cyber_news.fetchers.rss import RssFetcher


def get_fetcher(source_type: str, http_client: AsyncHttpClient) -> SourceFetcher:
    """Return a fetcher for a source type."""
    if source_type == "rss":
        return RssFetcher(http_client)
    raise ValueError(f"Unsupported source type for ingestion: {source_type}")


def build_http_client(config: HttpClientConfig) -> AsyncHttpClient:
    """Build the shared async HTTP client."""
    return AsyncHttpClient(config)
