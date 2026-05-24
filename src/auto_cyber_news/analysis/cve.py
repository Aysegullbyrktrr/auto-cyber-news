"""Regex-based CVE extraction."""

from __future__ import annotations

import re

CVE_PATTERN = re.compile(r"\bCVE-(\d{4})-(\d{4,})\b", re.IGNORECASE)


def extract_cves(*texts: str | None) -> tuple[str, ...]:
    """Extract normalized, deduplicated CVE identifiers from text values."""
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in CVE_PATTERN.finditer(text):
            found.add(f"CVE-{match.group(1)}-{match.group(2)}".upper())
    return tuple(sorted(found))
