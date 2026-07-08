from __future__ import annotations

import asyncio
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

TV_SCANNER_URL = "https://scanner.tradingview.com/pakistan/scan"

SCAN_PAYLOAD = {
    "filter": [{"left": "type", "operation": "equal", "right": "stock"}],
    "columns": ["name", "close", "change", "change_abs", "volume", "sector", "market_cap_basic"],
    "sort": {"sortBy": "volume", "sortOrder": "desc"},
    "range": [0, 500],
}

TV_SECTOR_MAP: dict[str, str] = {
    "Finance": "BANKING & FINANCE",
    "Process Industries": "CHEMICALS & PROCESS",
    "Distribution Services": "DISTRIBUTION & SERVICES",
    "Producer Manufacturing": "MANUFACTURING",
    "Non-Energy Minerals": "MINERALS & MATERIALS",
    "Electronic Technology": "TECHNOLOGY",
    "Utilities": "POWER & UTILITIES",
    "Retail Trade": "RETAIL TRADE",
    "Consumer Non-Durables": "FOOD & CONSUMER GOODS",
    "Consumer Durables": "CONSUMER DURABLES",
    "Energy Minerals": "OIL & GAS",
    "Health Technology": "PHARMA & HEALTHCARE",
    "Health Services": "PHARMA & HEALTHCARE",
    "Transportation": "TRANSPORT",
    "Commercial Services": "SERVICES",
    "Industrial Services": "INDUSTRIAL",
    "Communications": "TELECOM",
    "Technology Services": "TECHNOLOGY",
}


class TradingViewScraper:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                headers={
                    "User-Agent": "Mozilla/5.0 NafaIQ-PSX/0.1",
                    "Accept": "application/json",
                    "Origin": "https://www.tradingview.com",
                },
                timeout=15.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_market_data(self) -> list[dict]:
        """Fetch all PSX stocks with price, change, volume, sector, market cap."""
        client = await self._get_client()
        try:
            r = await client.post(TV_SCANNER_URL, json=SCAN_PAYLOAD)
            r.raise_for_status()
            data = r.json()
            items = data.get("data", [])
            results = []
            for item in items:
                d = item.get("d", [])
                if not d or len(d) < 7:
                    continue
                symbol = item["s"].replace("PSX:", "")
                tv_sector = d[5] if d[5] else "Other"
                results.append({
                    "symbol": symbol,
                    "name": d[0],
                    "close": d[1],
                    "change_pct": d[2],
                    "change_abs": d[3],
                    "volume": d[4],
                    "sector": tv_sector,
                    "market_cap": d[6],
                })
            return results
        except Exception:
            log.warning("tv_scanner_failed", exc_info=True)
            return []
