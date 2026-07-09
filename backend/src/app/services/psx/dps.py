"""PSX DPS (Data Dissemination Portal) client.

Endpoints used:
  GET  https://dps.psx.com.pk/market-watch          HTML table of all symbols
  GET  https://dps.psx.com.pk/symbols                JSON list of all symbols
  POST https://dps.psx.com.pk/historical             OHLCV history for a symbol
  GET  https://dps.psx.com.pk/company/{symbol}       Company profile/fundamentals
  POST https://dps.psx.com.pk/announcements          Corporate announcements
  POST https://dps.psx.com.pk/company/payouts        Dividend/payout history
  GET  https://dps.psx.com.pk/timeseries/eod/{code}  Index EOD (KSE100/KSE30/ALLSHR)

All methods are async, return plain dicts, and never raise on network errors
(other than HTTPException-style errors for callers that want them). They
return None on failure so the caller can fall back to a cached or alternative
source.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

DPS_BASE = "https://dps.psx.com.pk"
DEFAULT_TIMEOUT = 15.0


class DPSClient:
    """Async PSX DPS client. Use a single instance per process."""

    def __init__(self, base_url: str = DPS_BASE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self.base_url,
                        timeout=self.timeout,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (compatible; NafaIQ/1.0; "
                                "+https://nafaiq.app)"
                            ),
                            "Accept": (
                                "application/json, text/html, */*"
                            ),
                        },
                    )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ---------- market watch ----------

    async def fetch_market_watch(self) -> list[dict[str, Any]]:
        """Return a list of dicts with at least symbol/price/change_pct/volume."""
        try:
            client = await self._get_client()
            r = await client.get("/market-watch")
            r.raise_for_status()
            return self._parse_market_watch_html(r.text)
        except Exception:
            log.exception("dps.fetch_market_watch failed")
            return []

    def _parse_market_watch_html(self, html: str) -> list[dict[str, Any]]:
        """Light-weight HTML table parser.

        Avoids extra dependencies. The DPS market-watch page is a single
        <table> with rows of <td> cells. We just regex-extract the symbol
        and numeric cells.
        """
        import re

        rows: list[dict[str, Any]] = []
        tr_iter = re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
        for tr_match in tr_iter:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr_match.group(1), re.DOTALL)
            if not cells or len(cells) < 5:
                continue
            text_cells = [
                re.sub(r"<[^>]+>", "", c).strip().replace(",", "")
                for c in cells
            ]
            symbol = text_cells[0]
            if not symbol or not symbol.isalnum():
                continue
            try:
                price = float(text_cells[1]) if len(text_cells) > 1 else 0.0
                change = float(text_cells[2]) if len(text_cells) > 2 else 0.0
                change_pct = float(text_cells[3]) if len(text_cells) > 3 else 0.0
                volume = (
                    int(float(text_cells[4])) if len(text_cells) > 4 and text_cells[4] else 0
                )
            except ValueError:
                continue
            rows.append(
                {
                    "symbol": symbol.upper(),
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                }
            )
        return rows

    # ---------- symbols ----------

    async def fetch_symbols(self) -> list[dict[str, Any]]:
        """Return list of symbol metadata dicts."""
        try:
            client = await self._get_client()
            r = await client.get("/symbols")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return [
                    {
                        "symbol": (s.get("symbol") or s.get("code") or "").upper(),
                        "name": s.get("name") or "",
                        "sector": s.get("sector"),
                    }
                    for s in data
                ]
            return []
        except Exception:
            log.exception("dps.fetch_symbols failed")
            return []

    # ---------- historical ----------

    async def fetch_historical(
        self, symbol: str, *, days: int = 365
    ) -> list[dict[str, Any]]:
        """POST to /historical and return normalized OHLCV bars."""
        try:
            client = await self._get_client()
            r = await client.post(
                "/historical",
                data={"symbol": symbol.upper()},
            )
            r.raise_for_status()
            data = r.json()
            rows = data if isinstance(data, list) else data.get("data", [])
            bars: list[dict[str, Any]] = []
            for row in rows:
                date_str = row.get("date")
                if not date_str:
                    continue
                try:
                    close = float(row.get("close") or 0)
                except (TypeError, ValueError):
                    close = 0.0
                bars.append(
                    {
                        "symbol": symbol.upper(),
                        "date": str(date_str)[:10],
                        "open": float(row.get("open") or close),
                        "high": float(row.get("high") or close),
                        "low": float(row.get("low") or close),
                        "close": close,
                        "volume": int(row.get("volume") or 0),
                    }
                )
            bars.sort(key=lambda b: b["date"], reverse=True)
            return bars[: int(days)]
        except Exception:
            log.exception("dps.fetch_historical failed", extra={"symbol": symbol})
            return []

    # ---------- company ----------

    async def fetch_company(self, symbol: str) -> Optional[dict[str, Any]]:
        try:
            client = await self._get_client()
            r = await client.get(f"/company/{symbol.upper()}")
            r.raise_for_status()
            return r.json()
        except Exception:
            log.exception("dps.fetch_company failed", extra={"symbol": symbol})
            return None

    # ---------- announcements ----------

    async def fetch_announcements(
        self, symbol: Optional[str] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        try:
            client = await self._get_client()
            payload: dict[str, Any] = {"limit": limit}
            if symbol:
                payload["symbol"] = symbol.upper()
            r = await client.post("/announcements", data=payload)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        except Exception:
            log.exception("dps.fetch_announcements failed")
            return []

    # ---------- payouts ----------

    async def fetch_payouts(self, symbol: str) -> list[dict[str, Any]]:
        try:
            client = await self._get_client()
            r = await client.post("/company/payouts", data={"symbol": symbol.upper()})
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        except Exception:
            log.exception("dps.fetch_payouts failed", extra={"symbol": symbol})
            return []

    # ---------- index EOD ----------

    async def fetch_index_eod(
        self, code: str = "KSE100", days: int = 365
    ) -> list[dict[str, Any]]:
        try:
            client = await self._get_client()
            r = await client.get(f"/timeseries/eod/{code.upper()}")
            r.raise_for_status()
            data = r.json()
            rows = data if isinstance(data, list) else data.get("data", [])
            bars: list[dict[str, Any]] = []
            for row in rows:
                date_str = row.get("date")
                if not date_str:
                    continue
                close = float(row.get("close") or 0)
                bars.append(
                    {
                        "code": code.upper(),
                        "date": str(date_str)[:10],
                        "open": float(row.get("open") or close),
                        "high": float(row.get("high") or close),
                        "low": float(row.get("low") or close),
                        "close": close,
                        "volume": int(row.get("volume") or 0),
                    }
                )
            bars.sort(key=lambda b: b["date"], reverse=True)
            return bars[: int(days)]
        except Exception:
            log.exception("dps.fetch_index_eod failed", extra={"code": code})
            return []


_dps_client: Optional[DPSClient] = None


def get_dps_client() -> DPSClient:
    global _dps_client
    if _dps_client is None:
        _dps_client = DPSClient()
    return _dps_client
