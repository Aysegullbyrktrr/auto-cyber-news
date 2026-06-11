"""Regex-based CVE and CVSS extraction."""

from __future__ import annotations

import re

# Year is bounded to 1999-2099 so junk like ``CVE-0000-1`` / ``CVE-9999-1`` is
# rejected (the CVE program started in 1999).
CVE_PATTERN = re.compile(r"\bCVE-(199\d|20\d{2})-(\d{4,})\b", re.IGNORECASE)

# CVSS base scores live in 0.0-10.0. We scan a short window after each "cvss"
# mention and take the largest plausible score, which skips version numbers like
# "CVSS:3.1" in favour of the actual base score that follows.
_CVSS_WINDOW = 48
_CVSS_NUMBER = re.compile(r"\d{1,2}(?:\.\d)?")


def extract_cves(*texts: str | None) -> tuple[str, ...]:
    """Extract normalized, deduplicated CVE identifiers from text values."""
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in CVE_PATTERN.finditer(text):
            found.add(f"CVE-{match.group(1)}-{match.group(2)}".upper())
    return tuple(sorted(found))


def extract_cvss_score(*texts: str | None) -> float | None:
    """Return the highest plausible CVSS base score (0.0-10.0) found, if any."""
    best: float | None = None
    for text in texts:
        if not text:
            continue
        lowered = text.casefold()
        start = 0
        while True:
            index = lowered.find("cvss", start)
            if index == -1:
                break
            window = lowered[index + 4 : index + 4 + _CVSS_WINDOW]
            for number in _CVSS_NUMBER.finditer(window):
                value = float(number.group())
                if 0.0 <= value <= 10.0 and (best is None or value > best):
                    best = value
            start = index + 4
    return best
