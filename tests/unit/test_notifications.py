"""Tests for notification formatting and configuration helpers."""

from __future__ import annotations

from auto_cyber_news.notifications.formatting import (
    escape_telegram_markdown,
    format_telegram_alert,
)
from auto_cyber_news.notifications.telegram import escape_telegram_markdown as telegram_escape


def test_escape_telegram_markdown_escapes_special_characters() -> None:
    """MarkdownV2 escaping should protect reserved characters."""
    assert escape_telegram_markdown("CVE-2026-1234 (critical!)") == (
        "CVE\\-2026\\-1234 \\(critical\\!\\)"
    )
    assert telegram_escape("test") == escape_telegram_markdown("test")


def test_format_telegram_alert_includes_core_fields() -> None:
    """Telegram alert formatting should include severity and article metadata."""
    message = format_telegram_alert(
        title="Active ransomware exploit",
        url="https://example.com/story",
        severity="critical",
        risk_score=95,
        categories=("ransomware", "exploit"),
        detected_cves=("CVE-2026-1234",),
        reasons=("category:ransomware(+12)", "final_score:95"),
    )

    assert "CRITICAL" in message
    assert "95/100" in message
    assert "CVE\\-2026\\-1234" in message
    assert "example\\.com/story" in message
