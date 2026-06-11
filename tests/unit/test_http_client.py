"""Unit tests for bounded HTTP response reading."""

from __future__ import annotations

import pytest

from auto_cyber_news.fetchers.http import AsyncHttpClient, FetchError, HttpClientConfig


class _FakeContent:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self, size: int) -> bytes:
        return self._data[:size]


class _FakeResponse:
    def __init__(self, data: bytes, *, headers: dict[str, str] | None = None) -> None:
        self.content = _FakeContent(data)
        self.headers = headers or {}
        self.charset = "utf-8"


def _client(max_bytes: int) -> AsyncHttpClient:
    return AsyncHttpClient(
        HttpClientConfig(
            timeout_seconds=5,
            total_retries=0,
            user_agent="test",
            max_response_bytes=max_bytes,
        ),
    )


async def test_read_bounded_returns_text_within_cap() -> None:
    """A small body is decoded and returned normally."""
    client = _client(1000)
    response = _FakeResponse(b"hello world")
    assert await client._read_bounded(response, "https://example.com") == "hello world"


async def test_read_bounded_rejects_oversized_stream() -> None:
    """A body larger than the cap raises rather than buffering everything."""
    client = _client(10)
    response = _FakeResponse(b"x" * 5000)
    with pytest.raises(FetchError):
        await client._read_bounded(response, "https://example.com")


async def test_read_bounded_rejects_oversized_content_length() -> None:
    """An over-large declared Content-Length is rejected before reading the body."""
    client = _client(10)
    response = _FakeResponse(b"short", headers={"Content-Length": "999999"})
    with pytest.raises(FetchError):
        await client._read_bounded(response, "https://example.com")
