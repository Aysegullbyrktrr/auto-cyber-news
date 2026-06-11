"""Email notification client."""

from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from auto_cyber_news.notifications.formatting import format_digest_subject


class EmailConfigurationError(ValueError):
    """Raised when SMTP credentials are missing or invalid."""


@dataclass(frozen=True)
class EmailSettings:
    """SMTP credentials loaded from the environment."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_from: str
    email_to: str


@dataclass(frozen=True)
class DigestArticlePayload:
    """Plain article payload for digest rendering."""

    title: str
    url: str
    severity: str
    risk_score: int
    categories: tuple[str, ...]
    detected_cves: tuple[str, ...]
    ai_summary: str = ""


def _env_first(*names: str) -> str:
    """Return the first non-empty environment value among ``names``."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def load_email_settings() -> EmailSettings:
    """Load SMTP credentials from environment variables.

    Canonical names are ``SMTP_USERNAME``/``SMTP_PASSWORD`` (matching
    ``.env.example`` and the architecture docs); the legacy ``SMTP_USER``/
    ``SMTP_PASS`` names are accepted as fallbacks for backwards compatibility.
    """
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "587").strip()
    smtp_user = _env_first("SMTP_USERNAME", "SMTP_USER")
    smtp_pass = _env_first("SMTP_PASSWORD", "SMTP_PASS")
    email_to = os.getenv("EMAIL_TO", "").strip()
    email_from = os.getenv("EMAIL_FROM", "").strip() or smtp_user

    if not smtp_host:
        raise EmailConfigurationError("SMTP_HOST is not configured.")
    if not smtp_user:
        raise EmailConfigurationError("SMTP_USERNAME is not configured.")
    if not smtp_pass:
        raise EmailConfigurationError("SMTP_PASSWORD is not configured.")
    if not email_to:
        raise EmailConfigurationError("EMAIL_TO is not configured.")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise EmailConfigurationError("SMTP_PORT must be an integer.") from exc

    return EmailSettings(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        email_from=email_from,
        email_to=email_to,
    )


def is_email_configured() -> bool:
    """Return whether SMTP credentials are present."""
    if not os.getenv("SMTP_HOST", "").strip():
        return False
    if not _env_first("SMTP_USERNAME", "SMTP_USER"):
        return False
    if not _env_first("SMTP_PASSWORD", "SMTP_PASS"):
        return False
    return bool(os.getenv("EMAIL_TO", "").strip())


class EmailNotifier:
    """Async-friendly email notification client."""

    def __init__(self, settings: EmailSettings) -> None:
        """Initialize the notifier with SMTP credentials."""
        self._settings = settings

    @classmethod
    def from_env(cls) -> EmailNotifier:
        """Create a notifier using environment credentials."""
        return cls(load_email_settings())

    @property
    def recipient(self) -> str:
        """Return the configured digest recipient address."""
        return self._settings.email_to

    async def send_html(self, subject: str, html: str) -> None:
        """Send an HTML email using SMTP in a worker thread."""
        await asyncio.to_thread(self._send_html_sync, subject, html)

    def render_digest_html(
        self,
        *,
        subject: str,
        digest_date: str,
        articles: tuple[DigestArticlePayload, ...],
    ) -> str:
        """Render the daily digest HTML email."""
        environment = _jinja_environment()
        template = environment.get_template("email_digest.html.j2")
        return template.render(
            subject=subject,
            digest_date=escape(digest_date),
            article_count=len(articles),
            articles=articles,
        )

    async def send_daily_digest(
        self,
        *,
        subject_prefix: str,
        digest_date: str,
        articles: tuple[DigestArticlePayload, ...],
    ) -> str:
        """Render and send a daily digest email."""
        subject = format_digest_subject(subject_prefix=subject_prefix, digest_date=digest_date)
        html = self.render_digest_html(subject=subject, digest_date=digest_date, articles=articles)
        await self.send_html(subject, html)
        return subject

    def _send_html_sync(self, subject: str, html: str) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self._settings.email_from
        message["To"] = self._settings.email_to
        message.attach(MIMEText(html, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=30) as client:
            client.starttls(context=context)
            client.login(self._settings.smtp_user, self._settings.smtp_pass)
            client.sendmail(
                self._settings.email_from,
                [self._settings.email_to],
                message.as_string(),
            )


def _jinja_environment() -> Environment:
    template_dir = Path(str(files("auto_cyber_news") / "templates"))
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
