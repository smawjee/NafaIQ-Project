"""PSX DPS (Data Dissemination Portal) client — thin wrapper over app.scrapers.dps.

Workstream E: v2 used to be a parallel regex-based re-implementation of v1's
BeautifulSoup-based scraper, and the two drifted apart (different return shapes,
different retry behaviour, etc.). v2 now delegates to v1's `DPSScraper` and only
adapts signatures and return types to match what the v2 callers historically
expected.

Endpoints used (all routed through v1):
  GET  https://dps.psx.com.pk/market-watch          HTML table of all symbols
  GET  https://dps.psx.com.pk/symbols                JSON list of all symbols
  POST https://dps.psx.com.pk/historical             OHLCV history for a symbol
  GET  https://dps.psx.com.pk/company/{symbol}       Company profile/fundamentals
  POST https://dps.psx.com.pk/announcements          Corporate announcements
  POST https://dps.psx.com.pk/company/payouts        Dividend/payout history
  GET  https://dps.psx.com.pk/timeseries/eod/{code}  Index EOD (KSE100/KSE30/ALLSHR)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.scrapers.dps import DPSScraper

log = logging.getLogger(__name__)

DPS_BASE = "https://dps.psx.com.pk"
DEFAULT_TIMEOUT = 15.0


class DPSClient:
    """Async PSX DPS client. Thin adapter over :class:`app.scrapers.dps.DPSScraper`.

    Kept under the v2 name so existing imports keep working. All public methods
    return plain ``dict`` lists (JSON-serialisable, ``mode="json"``) so the v2
    callers — which were written against the regex parser — do not need to
    change. Base URL / timeout are accepted for API compatibility but ignored;
    v1's ``DPSScraper`` owns the actual configuration via ``app.config.settings``.
    """

    def __init__(self, base_url: str = DPS_BASE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._scraper = DPSScraper()

    async def close(self) -> None:
        await self._scraper.close()

    # ---------- market watch ----------

    async def fetch_market_watch(self) -> list[dict[str, Any]]:
        try:
            items = await self._scraper.fetch_market_watch()
            return [i.model_dump() for i in items]
        except Exception:
            log.exception("dps.fetch_market_watch failed")
            return []

    # ---------- symbols ----------

    async def fetch_symbols(self) -> list[dict[str, Any]]:
        try:
            items = await self._scraper.fetch_symbols()
            return [i.model_dump() for i in items]
        except Exception:
            log.exception("dps.fetch_symbols failed")
            return []

    # ---------- historical ----------

    async def fetch_historical(
        self, symbol: str, *, days: int = 365
    ) -> list[dict[str, Any]]:
        try:
            bars = await self._scraper.fetch_historical(symbol)
            return [b.to_dict() for b in bars[: int(days)]]
        except Exception:
            log.exception("dps.fetch_historical failed", extra={"symbol": symbol})
            return []

    # ---------- company (profile) ----------

    async def fetch_company(self, symbol: str) -> Optional[dict[str, Any]]:
        try:
            profile = await self._scraper.fetch_profile(symbol)
            return profile.model_dump() if profile is not None else None
        except Exception:
            log.exception("dps.fetch_company failed", extra={"symbol": symbol})
            return None

    # ---------- announcements ----------

    async def fetch_announcements(
        self, symbol: Optional[str] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        try:
            items = await self._scraper.fetch_announcements(offset=0, count=limit)
            if symbol is not None:
                target = symbol.upper()
                items = [i for i in items if (i.symbol or "").upper() == target]
            return [i.model_dump(mode="json") for i in items]
        except Exception:
            log.exception("dps.fetch_announcements failed")
            return []

    # ---------- payouts ----------

    async def fetch_payouts(self, symbol: str) -> list[dict[str, Any]]:
        try:
            items = await self._scraper.fetch_payouts(symbol)
            return [i.model_dump(mode="json") for i in items]
        except Exception:
            log.exception("dps.fetch_payouts failed", extra={"symbol": symbol})
            return []

    # ---------- index EOD ----------

    async def fetch_index_eod(
        self, code: str = "KSE100", days: int = 365
    ) -> list[dict[str, Any]]:
        try:
            bars = await self._scraper.fetch_index_eod(code)
            return [b.model_dump(mode="json") for b in bars[: int(days)]]
        except Exception:
            log.exception("dps.fetch_index_eod failed", extra={"code": code})
            return []


_dps_client: Optional[DPSClient] = None


def get_dps_client() -> DPSClient:
    global _dps_client
    if _dps_client is None:
        _dps_client = DPSClient()
    return _dps_client
