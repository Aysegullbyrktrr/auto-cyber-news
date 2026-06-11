"""Async HTTP client helpers for source fetching."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp

from auto_cyber_news.logging import get_logger

LOGGER = get_logger(__name__)


class FetchError(RuntimeError):
    """Raised when an HTTP fetch fails after retries."""


@dataclass(frozen=True)
class HttpClientConfig:
    """Runtime settings for HTTP fetches."""

    timeout_seconds: int
    total_retries: int
    user_agent: str
    max_response_bytes: int = 8_000_000


class AsyncHttpClient:
    """Small aiohttp wrapper with timeout, retry, and backoff handling."""

    def __init__(self, config: HttpClientConfig) -> None:
        """Initialize the HTTP client wrapper."""
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    async def get_text(self, url: str) -> str:
        """Fetch a URL and return response text."""
        headers = {"User-Agent": self._config.user_agent}
        last_error: BaseException | None = None
        session = await self._get_session()

        for attempt in range(self._config.total_retries + 1):
            try:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await self._read_bounded(response, url)
            except (aiohttp.ClientError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self._config.total_retries:
                    break
                delay_seconds = 2**attempt
                LOGGER.warning(
                    "HTTP fetch failed; retrying",
                    extra={"url": url, "attempt": attempt + 1, "delay_seconds": delay_seconds},
                )
                await asyncio.sleep(delay_seconds)

        raise FetchError(f"Failed to fetch URL after retries: {url}") from last_error

    async def _read_bounded(self, response: aiohttp.ClientResponse, url: str) -> str:
        """Read a response body, rejecting payloads larger than the configured cap.

        A hostile or broken feed can return a multi-gigabyte (or unbounded
        streaming) body; ``response.text()`` would buffer all of it and exhaust
        memory. We refuse early on a too-large ``Content-Length`` and otherwise
        read at most ``max_response_bytes + 1`` to detect overflow.
        """
        max_bytes = self._config.max_response_bytes
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                if int(declared) > max_bytes:
                    raise FetchError(
                        f"Response Content-Length {declared} exceeds cap for URL: {url}",
                    )
            except ValueError:
                pass

        body = await response.content.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise FetchError(f"Response exceeded {max_bytes} bytes for URL: {url}")
        return body.decode(response.charset or "utf-8", errors="replace")

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self._config.user_agent},
            )
        return self._session
