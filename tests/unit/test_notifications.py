"""Tests for notification formatting and configuration helpers."""

from __future__ import annotations

import json
from datetime import UTC

import pytest

from auto_cyber_news.notifications.email import load_email_settings
from auto_cyber_news.notifications.formatting import (
    TELEGRAM_MAX_CHARS,
    escape_telegram_markdown,
    format_telegram_alert,
    format_telegram_incident_alert,
)
from auto_cyber_news.notifications.telegram import (
    MAX_RETRY_DELAY_SECONDS,
    TelegramApiError,
    TelegramNotifier,
    TelegramSettings,
    _parse_chat_ids,
    _parse_retry_after,
)
from auto_cyber_news.notifications.telegram import escape_telegram_markdown as telegram_escape

_SMTP_ENV_VARS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USER",
    "SMTP_PASS",
    "EMAIL_FROM",
    "EMAIL_TO",
)


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


def _incident_card(**overrides: object) -> str:
    params: dict[str, object] = {
        "title": "Active ransomware exploit",
        "severity": "critical",
        "risk_score": 95,
        "sources": ("The Hacker News",),
        "categories": ("ransomware", "exploit"),
        "detected_cves": ("CVE-2026-1234",),
        "related_articles": (
            ("Active ransomware exploit", "https://example.com/story", "The Hacker News"),
        ),
        "ai_summary": "Attackers are actively exploiting the flaw to deploy ransomware.",
    }
    params.update(overrides)
    return format_telegram_incident_alert(**params)  # type: ignore[arg-type]


def test_incident_card_has_clean_sections_without_dividers() -> None:
    """The incident card uses a colour header, bold title, and emoji sections."""
    message = _incident_card()

    assert "─" not in message  # no divider lines
    assert message.startswith("🔴 *CRITICAL* · Risk 95/100")
    assert "*Active ransomware exploit*" in message  # bold headline
    assert "🧠 " in message  # summary
    assert "🏷 " in message  # categories
    assert "⚠️ " in message  # CVEs
    assert "📰 *Sources*" in message


def test_incident_card_renders_detected_at_timestamp() -> None:
    """A provided detection time appears as a UTC timestamp under the header."""
    from datetime import datetime

    message = _incident_card(detected_at=datetime(2026, 6, 11, 11, 30, tzinfo=UTC))

    assert "🕐 2026\\-06\\-11 11:30 UTC" in message


def test_incident_card_omits_timestamp_when_absent() -> None:
    """Without a detection time, no clock line is rendered."""
    assert "🕐" not in _incident_card()


def test_incident_card_omits_summary_when_ai_missing() -> None:
    """With no AI summary, the brain line is omitted (the bold title carries it)."""
    message = _incident_card(ai_summary="", title="Critical zero-day in widget")

    assert "🧠" not in message
    assert "*Critical zero\\-day in widget*" in message


def test_incident_card_truncates_cves_with_remainder() -> None:
    """CVE lists must be truncated to 10 with a '+N more' remainder marker."""
    cves = tuple(f"CVE-2026-{number:04d}" for number in range(15))
    message = _incident_card(detected_cves=cves)

    assert "CVE\\-2026\\-0009" in message
    assert "CVE\\-2026\\-0010" not in message
    assert escape_telegram_markdown("... +5 more") in message


def test_incident_card_deduplicates_sources() -> None:
    """Repeated article rows (same URL) should appear once in the source list."""
    rows = (
        ("Ransomware hits hospital", "https://a.example/story", "Site A"),
        ("Ransomware hits hospital", "https://a.example/story", "Site A"),
        ("Different angle", "https://b.example/story", "Site B"),
    )
    message = _incident_card(related_articles=rows)

    assert message.count(escape_telegram_markdown("https://a.example/story")) == 1


def test_incident_card_lists_overflow_under_related() -> None:
    """Articles beyond the source cap should move to the Related section."""
    rows = tuple((f"Story {index}", f"https://example.com/{index}", "Site") for index in range(8))
    message = _incident_card(related_articles=rows, max_related_articles=5)

    assert "🔗 *Related*" in message
    assert "Story 7" in message


def test_incident_card_respects_telegram_length_limit() -> None:
    """A huge incident must still produce a message under the Telegram cap."""
    rows = tuple(
        (
            f"Story number {index} with a fairly long headline",
            f"https://example.com/{index}",
            "Site",
        )
        for index in range(200)
    )
    message = _incident_card(
        related_articles=rows,
        detected_cves=tuple(f"CVE-2026-{index:05d}" for index in range(50)),
    )

    assert len(message) <= TELEGRAM_MAX_CHARS


def test_parse_chat_ids_splits_on_separators() -> None:
    """One or more chat IDs may be given, separated by commas/spaces/newlines."""
    assert _parse_chat_ids("111, 222  333\n444") == ("111", "222", "333", "444")
    assert _parse_chat_ids("  555  ") == ("555",)
    assert _parse_chat_ids("   ") == ()


async def test_telegram_sends_to_every_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A message is delivered independently to each configured chat ID."""
    notifier = TelegramNotifier(TelegramSettings(bot_token="t", chat_ids=("111", "222")))
    sent: list[str] = []

    async def fake_post(url: str, payload: dict[str, object]) -> None:
        sent.append(str(payload["chat_id"]))

    monkeypatch.setattr(notifier, "_post_message", fake_post)
    await notifier.send_message("hello", parse_mode="")

    assert sent == ["111", "222"]


async def test_telegram_one_failed_chat_does_not_block_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A permanent failure for one recipient still delivers to the rest."""
    notifier = TelegramNotifier(TelegramSettings(bot_token="t", chat_ids=("111", "222")))
    delivered: list[str] = []

    async def fake_post(url: str, payload: dict[str, object]) -> None:
        if payload["chat_id"] == "111":
            raise TelegramApiError("blocked", status=403)
        delivered.append(str(payload["chat_id"]))

    monkeypatch.setattr(notifier, "_post_message", fake_post)
    await notifier.send_message("hello", parse_mode="")

    assert delivered == ["222"]


def test_parse_retry_after_reads_header_and_body() -> None:
    """A 429 retry-after hint should be parsed from either header or JSON body."""
    assert _parse_retry_after({"Retry-After": "5"}, "") == 5
    body = json.dumps({"ok": False, "parameters": {"retry_after": 9}})
    assert _parse_retry_after({}, body) == 9
    assert _parse_retry_after({}, "not json") is None


def test_retry_delay_respects_retry_after_and_caps() -> None:
    """The 429 backoff honors retry_after but never exceeds the cap."""
    capped = TelegramNotifier._retry_delay(
        TelegramApiError("rate limited", status=429, retry_after=600),
        0,
    )
    assert capped == float(MAX_RETRY_DELAY_SECONDS)

    backoff = TelegramNotifier._retry_delay(TelegramApiError("boom", status=500), 2)
    assert backoff == 4.0


def test_load_email_settings_prefers_canonical_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """SMTP_USERNAME/PASSWORD and EMAIL_FROM are the canonical variables."""
    for name in _SMTP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "canonical-user")
    monkeypatch.setenv("SMTP_PASSWORD", "canonical-pass")
    monkeypatch.setenv("EMAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("EMAIL_TO", "soc@example.com")

    settings = load_email_settings()

    assert settings.smtp_user == "canonical-user"
    assert settings.smtp_pass == "canonical-pass"
    assert settings.email_from == "alerts@example.com"


def test_load_email_settings_falls_back_to_legacy_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy SMTP_USER/SMTP_PASS still work; EMAIL_FROM defaults to the user."""
    for name in _SMTP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "legacy-user")
    monkeypatch.setenv("SMTP_PASS", "legacy-pass")
    monkeypatch.setenv("EMAIL_TO", "soc@example.com")

    settings = load_email_settings()

    assert settings.smtp_user == "legacy-user"
    assert settings.email_from == "legacy-user"
