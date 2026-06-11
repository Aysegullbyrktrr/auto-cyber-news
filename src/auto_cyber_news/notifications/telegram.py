"""Telegram notification client."""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass

import aiohttp

from auto_cyber_news.notifications.formatting import escape_telegram_markdown

MAX_SEND_ATTEMPTS = 4
MAX_RETRY_DELAY_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 20


class TelegramConfigurationError(ValueError):
    """Raised when Telegram credentials are missing or invalid."""


class TelegramApiError(RuntimeError):
    """Raised when the Telegram API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class TelegramSettings:
    """Telegram bot credentials loaded from the environment."""

    bot_token: str
    chat_ids: tuple[str, ...]


def load_telegram_settings() -> TelegramSettings:
    """Load Telegram credentials from environment variables."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = _parse_chat_ids(os.getenv("TELEGRAM_CHAT_ID", ""))
    if not bot_token:
        raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured.")
    if not chat_ids:
        raise TelegramConfigurationError("TELEGRAM_CHAT_ID is not configured.")
    return TelegramSettings(bot_token=bot_token, chat_ids=chat_ids)


def _parse_chat_ids(raw: str) -> tuple[str, ...]:
    """Parse one or more chat IDs separated by commas, spaces, or newlines."""
    return tuple(part for part in re.split(r"[,\s]+", raw.strip()) if part)


def is_telegram_configured() -> bool:
    """Return whether Telegram credentials are present."""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()) and bool(
        os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    )


class TelegramNotifier:
    """Async Telegram notification client."""

    def __init__(
        self,
        settings: TelegramSettings,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the notifier with bot credentials."""
        self._settings = settings
        self._session = session
        self._owns_session = session is None

    @classmethod
    def from_env(cls, *, session: aiohttp.ClientSession | None = None) -> TelegramNotifier:
        """Create a notifier using environment credentials."""
        return cls(load_telegram_settings(), session=session)

    async def send_message(
        self,
        message: str,
        *,
        parse_mode: str = "MarkdownV2",
        disable_web_page_preview: bool = False,
    ) -> None:
        """Send a Telegram message to every configured chat.

        Each recipient is delivered independently, so one failing chat (e.g. a
        user who blocked the bot) does not prevent delivery to the others. Raises
        only if no recipient could be reached.
        """
        safe_message = message if parse_mode else escape_telegram_markdown(message)
        url = f"https://api.telegram.org/bot{self._settings.bot_token}/sendMessage"

        delivered = 0
        last_error: RuntimeError | None = None
        for chat_id in self._settings.chat_ids:
            payload: dict[str, object] = {
                "chat_id": chat_id,
                "text": safe_message,
                "disable_web_page_preview": disable_web_page_preview,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                await self._send_with_retries(url, payload)
                delivered += 1
            except TelegramApiError as exc:
                last_error = exc

        if delivered == 0 and last_error is not None:
            raise last_error

    async def _send_with_retries(self, url: str, payload: dict[str, object]) -> None:
        """Deliver one payload with retry/backoff; raise on terminal failure."""
        last_error: RuntimeError | None = None
        for attempt in range(MAX_SEND_ATTEMPTS):
            try:
                await self._post_message(url, payload)
                return
            except TelegramApiError as exc:
                last_error = exc
                # Permanent client errors (e.g. malformed MarkdownV2 → 400) will
                # never succeed on retry; fail fast instead of hammering the API.
                if exc.status is not None and 400 <= exc.status < 500 and exc.status != 429:
                    raise
                delay = self._retry_delay(exc, attempt)
            except (aiohttp.ClientError, TimeoutError) as exc:
                last_error = TelegramApiError(f"Telegram request error: {exc}")
                delay = min(2**attempt, MAX_RETRY_DELAY_SECONDS)

            if attempt == MAX_SEND_ATTEMPTS - 1:
                break
            await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error

    @staticmethod
    def _retry_delay(error: TelegramApiError, attempt: int) -> float:
        """Respect Telegram's ``retry_after`` on 429, else exponential backoff."""
        if error.status == 429 and error.retry_after is not None:
            return float(min(error.retry_after, MAX_RETRY_DELAY_SECONDS))
        return float(min(2**attempt, MAX_RETRY_DELAY_SECONDS))

    async def close(self) -> None:
        """Close the owned HTTP session."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _post_message(self, url: str, payload: dict[str, object]) -> None:
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with session.post(url, json=payload, timeout=timeout) as response:
            body = await response.text()
            if response.status >= 400:
                retry_after = (
                    _parse_retry_after(response.headers, body) if response.status == 429 else None
                )
                raise TelegramApiError(
                    f"Telegram API request failed ({response.status}): {body[:500]}",
                    status=response.status,
                    retry_after=retry_after,
                )


def _parse_retry_after(headers: object, body: str) -> int | None:
    """Extract a retry-after hint from Telegram's 429 response."""
    header_value = None
    if isinstance(headers, dict):
        header_value = headers.get("Retry-After")
    else:
        getter = getattr(headers, "get", None)
        if callable(getter):
            header_value = getter("Retry-After")
    if header_value is not None:
        try:
            return max(1, int(str(header_value).strip()))
        except (TypeError, ValueError):
            pass

    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, dict):
        parameters = parsed.get("parameters")
        if isinstance(parameters, dict):
            retry_after = parameters.get("retry_after")
            if isinstance(retry_after, int):
                return max(1, retry_after)
    return None
