"""Telegram notification client."""

from __future__ import annotations

import os
from dataclasses import dataclass

import aiohttp

from auto_cyber_news.notifications.formatting import escape_telegram_markdown


class TelegramConfigurationError(ValueError):
    """Raised when Telegram credentials are missing or invalid."""


@dataclass(frozen=True)
class TelegramSettings:
    """Telegram bot credentials loaded from the environment."""

    bot_token: str
    chat_id: str


def load_telegram_settings() -> TelegramSettings:
    """Load Telegram credentials from environment variables."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token:
        raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured.")
    if not chat_id:
        raise TelegramConfigurationError("TELEGRAM_CHAT_ID is not configured.")
    return TelegramSettings(bot_token=bot_token, chat_id=chat_id)


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
        """Send a Telegram message."""
        safe_message = message if parse_mode else escape_telegram_markdown(message)
        url = f"https://api.telegram.org/bot{self._settings.bot_token}/sendMessage"
        payload = {
            "chat_id": self._settings.chat_id,
            "text": safe_message,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=20)
        async with session.post(url, json=payload, timeout=timeout) as response:
            body = await response.text()
            if response.status >= 400:
                raise RuntimeError(
                    f"Telegram API request failed ({response.status}): {body[:500]}",
                )

    async def close(self) -> None:
        """Close the owned HTTP session."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
