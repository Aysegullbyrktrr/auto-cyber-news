"""Notification message formatting without analysis-layer dependencies."""

from __future__ import annotations

from html import escape


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
    max_related_articles: int = 5,
) -> str:
    """Build a grouped Telegram incident alert with related article links."""
    category_text = ", ".join(categories) if categories else "none"
    cve_text = ", ".join(detected_cves) if detected_cves else "none"
    source_text = ", ".join(sources) if sources else "unknown"

    lines = [
        f"*\\[INCIDENT {escape_telegram_markdown(severity.upper())}\\]* Risk {risk_score}/100",
        "",
        escape_telegram_markdown(title),
        "",
        f"*Sources:* {escape_telegram_markdown(source_text)}",
        f"*Categories:* {escape_telegram_markdown(category_text)}",
        f"*CVEs:* {escape_telegram_markdown(cve_text)}",
        f"*Related articles:* {min(len(related_articles), max_related_articles)}",
    ]

    for article_title, article_url, article_source in related_articles[:max_related_articles]:
        lines.extend(
            [
                "",
                f"• {escape_telegram_markdown(article_title)}",
                f"  _{escape_telegram_markdown(article_source)}_",
                escape_telegram_markdown(article_url),
            ],
        )

    return "\n".join(lines)


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
