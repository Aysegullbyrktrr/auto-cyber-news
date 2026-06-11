"""Notification message formatting without analysis-layer dependencies."""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

TELEGRAM_MAX_CHARS = 3500
MAX_CVES_IN_CARD = 10
MAX_SOURCES_IN_CARD = 5
MAX_RELATED_IN_CARD = 5
MAX_SUMMARY_CHARS_IN_CARD = 600
CARD_DIVIDER = "─" * 28


def escape_telegram_markdown(text: str) -> str:
    """Escape text for Telegram MarkdownV2 parse mode."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{character}" if character in special else character for character in text)


def format_telegram_alert(
    *,
    title: str,
    url: str,
    severity: str,
    risk_score: int,
    categories: tuple[str, ...],
    detected_cves: tuple[str, ...],
    reasons: tuple[str, ...],
) -> str:
    """Build a Telegram alert message with safe MarkdownV2 formatting."""
    category_text = ", ".join(categories) if categories else "none"
    cve_text = ", ".join(detected_cves) if detected_cves else "none"
    lines = [
        f"*\\[{escape_telegram_markdown(severity.upper())}\\]* Risk {risk_score}/100",
        "",
        escape_telegram_markdown(title),
        "",
        escape_telegram_markdown(url),
        "",
        f"*Categories:* {escape_telegram_markdown(category_text)}",
        f"*CVEs:* {escape_telegram_markdown(cve_text)}",
    ]
    if reasons:
        reason_lines = "\n".join(f"• {escape_telegram_markdown(reason)}" for reason in reasons[:8])
        lines.extend(["", "*Scoring reasons:*", reason_lines])
    return "\n".join(lines)


def format_telegram_incident_alert(
    *,
    title: str,
    severity: str,
    risk_score: int,
    sources: tuple[str, ...],
    categories: tuple[str, ...],
    detected_cves: tuple[str, ...],
    related_articles: tuple[tuple[str, str, str], ...],
    ai_summary: str = "",
    max_related_articles: int = MAX_SOURCES_IN_CARD,
) -> str:
    """Build a compact SOC-style incident card for Telegram (MarkdownV2).

    The layout is mobile-first: a fixed set of emoji-labelled sections, an
    always-present summary, aggressively truncated CVE list, a deduplicated
    source list, and an optional "Related" overflow section. The final message
    is capped at :data:`TELEGRAM_MAX_CHARS`.
    """
    summary = _incident_summary_text(ai_summary, fallback=title)
    category_text = ", ".join(categories) if categories else "none"
    cve_text = _format_cve_list(detected_cves)

    unique_articles = _dedupe_article_rows(related_articles)
    source_rows = unique_articles[:max_related_articles]
    overflow = unique_articles[max_related_articles:]
    related_rows = overflow[:MAX_RELATED_IN_CARD]
    related_extra = len(overflow) - len(related_rows)

    esc = escape_telegram_markdown
    lines = [
        CARD_DIVIDER,
        f"🚨 *\\[INCIDENT {esc(severity.upper())}\\]* Risk: {risk_score}/100",
        f"📌 *Title:* {esc(title)}",
        "",
        "🧠 *AI Summary:*",
        esc(summary),
        "",
        "🏷 *Categories:*",
        esc(category_text),
        "",
        "⚠ *CVEs:*",
        esc(cve_text),
        "",
        "📰 *Sources:*",
    ]

    if source_rows:
        for article_title, article_url, article_source in source_rows:
            lines.append(f"\\- {esc(article_title)} \\({esc(article_source)}\\)")
            if article_url.strip():
                lines.append(f"  {esc(article_url)}")
    else:
        lines.append(esc(", ".join(sources) if sources else "unknown"))

    if related_rows or related_extra > 0:
        lines.extend(["", "🔗 *Related:*"])
        for article_title, _, article_source in related_rows:
            lines.append(f"\\- {esc(article_title)} \\({esc(article_source)}\\)")
        if related_extra > 0:
            lines.append(esc(f"... +{related_extra} more"))

    lines.extend(["", CARD_DIVIDER])
    return _truncate_to_telegram_limit("\n".join(lines))


def _incident_summary_text(ai_summary: str, *, fallback: str) -> str:
    """Return a non-empty, length-capped summary, never a placeholder."""
    summary = (ai_summary or "").strip() or fallback.strip()
    if len(summary) > MAX_SUMMARY_CHARS_IN_CARD:
        summary = summary[: MAX_SUMMARY_CHARS_IN_CARD - 1].rstrip() + "…"
    return summary


def _format_cve_list(cves: tuple[str, ...], *, limit: int = MAX_CVES_IN_CARD) -> str:
    """Render CVEs as a short list, truncating aggressively with a remainder count."""
    if not cves:
        return "none"
    shown = cves[:limit]
    text = ", ".join(shown)
    extra = len(cves) - len(shown)
    if extra > 0:
        text += f" ... +{extra} more"
    return text


def _dedupe_article_rows(
    rows: Iterable[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Deduplicate (title, url, source) rows by URL, then by title+source."""
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for article_title, article_url, article_source in rows:
        key = article_url.strip().casefold() or f"{article_title}|{article_source}".casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append((article_title, article_url, article_source))
    return unique


def _truncate_to_telegram_limit(message: str, *, limit: int = TELEGRAM_MAX_CHARS) -> str:
    """Cap a MarkdownV2 message at a line boundary without breaking escape sequences."""
    if len(message) <= limit:
        return message
    notice = "\n… \\(truncated\\)"
    budget = limit - len(notice)
    truncated = message[:budget]
    newline_index = truncated.rfind("\n")
    if newline_index > 0:
        truncated = truncated[:newline_index]
    truncated = truncated.rstrip("\\")
    return truncated + notice


def format_digest_subject(*, subject_prefix: str, digest_date: str) -> str:
    """Build a daily digest email subject line."""
    return f"{subject_prefix} — {digest_date}"


def format_digest_article_row(
    *,
    title: str,
    url: str,
    severity: str,
    risk_score: int,
    categories: tuple[str, ...],
    detected_cves: tuple[str, ...],
) -> str:
    """Build one HTML row for a digest article."""
    category_text = escape(", ".join(categories) if categories else "uncategorized")
    cve_text = escape(", ".join(detected_cves) if detected_cves else "none")
    return (
        "<tr>"
        f"<td><strong>{escape(title)}</strong><br>"
        f'<a href="{escape(url)}">{escape(url)}</a></td>'
        f"<td>{escape(severity.upper())}<br>{risk_score}/100</td>"
        f"<td>{category_text}<br>CVEs: {cve_text}</td>"
        "</tr>"
    )
