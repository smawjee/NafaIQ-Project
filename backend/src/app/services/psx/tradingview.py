"""TradingView Pakistan scanner client — thin wrapper over app.scrapers.tradingview.

Workstream E: v2 used to be a parallel regex-less client with a richer URL
(``?api_key=widget_user_token&label-product=heatmap-stock``) and a different
payload shape (no forced sort, custom default limit). v2 now re-exports v1's
:class:`TradingViewScraper` under the v2 name and delegates everything to v1.

The richer v2 URL is preserved as a module-level constant for callers that want
to inspect it, but at runtime the v1 module owns the actual endpoint.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Preserved for API compat. v1's `app.scrapers.tradingview.TV_SCANNER_URL` is the
# endpoint actually used at runtime — this constant is just a hint for callers
# and tests that need the heatmap-product query string.
TV_URL = (
    "https://scanner.tradingview.com/pakistan/scan"
    "?api_key=widget_user_token&label-product=heatmap-stock"
)

from app.scrapers.tradingview import (  # noqa: E402
    TradingViewScraper as TradingViewScanner,
)

_scanner: Optional[TradingViewScanner] = None


def get_scanner() -> TradingViewScanner:
    """Return the singleton TradingViewScanner (a v1 ``TradingViewScraper``)."""
    global _scanner
    if _scanner is None:
        _scanner = TradingViewScanner()
    return _scanner
