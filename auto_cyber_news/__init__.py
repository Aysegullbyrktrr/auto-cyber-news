"""Checkout runner shim for the src-layout package.

This lets ``python -m auto_cyber_news`` work from an uninstalled repository
checkout while production packaging continues to use ``src/auto_cyber_news``.
"""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "auto_cyber_news"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
