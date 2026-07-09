"""TradingView Pakistan scanner client.

Endpoint:
  POST https://scanner.tradingview.com/pakistan/scan?api_key=widget_user_token&label-product=heatmap-stock

Used for:
- broad market scanning
- sector heatmap data
- screener
- market overview snapshot
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

TV_URL = (
    "https://scanner.tradingview.com/pakistan/scan"
    "?api_key=widget_user_token&label-product=heatmap-stock"
)


class TradingViewScanner:
    def __init__(self, url: str = TV_URL, timeout: float = 15.0) -> None:
        self.url = url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; NafaIQ/1.0; "
                        "+https://nafaiq.app)"
                    ),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def scan(
        self,
        columns: Optional[list[str]] = None,
        range_pct: tuple[float, float] = (-100, 100),
        sort_by: Optional[str] = None,
        sort_dir: str = "desc",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Run a TradingView scan and return list of result rows.

        Returns the parsed `data` array. The exact shape depends on the
        columns selected; we leave interpretation to the caller.
        """
        if columns is None:
            columns = [
                "name",
                "close",
                "change",
                "change_pct",
                "volume",
                "sector",
                "market_cap_basic",
            ]
        payload = {
            "columns": columns,
            "range": [list(range_pct)],
            "sort": {"sortBy": sort_by, "sortOrder": sort_dir} if sort_by else None,
            "limit": limit,
            "markets": ["pakistan"],
        }
        try:
            client = await self._get_client()
            r = await client.post(self.url, content=json.dumps(payload))
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []
        except Exception:
            log.exception("tradingview.scan failed")
            return []


_scanner: Optional[TradingViewScanner] = None


def get_scanner() -> TradingViewScanner:
    global _scanner
    if _scanner is None:
        _scanner = TradingViewScanner()
    return _scanner
