"""Canonical URL normalization for deduplication."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAM_NAMES = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "spm",
}


def canonicalize_url(url: str) -> str:
    """Canonicalize a URL for deduplication."""
    stripped_url = url.strip()
    parsed = urlsplit(stripped_url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _is_tracking_param(name: str) -> bool:
    """Return whether a query parameter is used for tracking."""
    normalized = name.lower()
    return normalized in TRACKING_PARAM_NAMES or normalized.startswith(TRACKING_PARAM_PREFIXES)
