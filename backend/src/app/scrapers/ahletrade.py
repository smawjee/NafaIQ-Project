from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


class AhleTradePoller:
    """Polls the AhleTrade HTTP feed for real-time PSX quotes and trades."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._subscribed: set[str] = set()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=10.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def subscribe(self, symbol: str):
        self._subscribed.add(symbol.upper())

    def unsubscribe(self, symbol: str):
        self._subscribed.discard(symbol.upper())

    @property
    def subscribed_symbols(self) -> list[str]:
        return list(self._subscribed)

    async def fetch_quotes(self, symbol: str, market: str = "REG") -> list[dict]:
        """Returns L1 bid/ask snapshots.

        The AhleTrade feed identifiers were reversed here until 2026-08-07:
        ``BuySell`` is the quote tape (``time;bid;ask``) and ``PriceVolume`` is
        the trade tape (``time;price;volume``). ``fetch_quotes`` used
        PriceVolume — so "bid/ask" pairs were really price/volume rows — and
        ``fetch_trades`` parsed the BuySell quote tape as trades, storing an
        ask quote as the price and rounding the other quote into the volume
        column (observed: CNERGY volume of 11 vs a real 42.2M shares). Both
        identifiers are now on the feed they were named for.
        """
        client = await self._get_client()
        url = f"{settings.ahletrade_base_url}?action=Market&identifier=BuySell&market={market}&symbol={symbol.upper()}"
        r = await client.get(url)
        records = []
        for rec in r.text.split("|"):
            parts = rec.strip().split(";")
            if len(parts) >= 3 and parts[0]:
                try:
                    records.append({
                        "time": parts[0].strip(),
                        "bid": float(parts[1].strip()),
                        "ask": float(parts[2].strip()),
                    })
                except (ValueError, IndexError):
                    continue
        return records

    async def fetch_trades(self, symbol: str, market: str = "REG") -> list[dict]:
        """Returns trade tape (time;price;volume from the PriceVolume feed)."""
        client = await self._get_client()
        url = f"{settings.ahletrade_base_url}?action=Market&identifier=PriceVolume&market={market}&symbol={symbol.upper()}"
        r = await client.get(url)
        records = []
        for rec in r.text.split("|"):
            parts = rec.strip().split(";")
            if len(parts) >= 3 and parts[0]:
                try:
                    records.append({
                        "time": parts[0].strip(),
                        "price": float(parts[1].strip()),
                        "volume": int(round(float(parts[2].strip()))),
                    })
                except (ValueError, IndexError):
                    continue
        return records

    async def poll_all(self, callback):
        """Polls all subscribed symbols and calls callback(symbol, trades, quotes) for each."""
        for sym in self._subscribed.copy():
            try:
                trades = await self.fetch_trades(sym)
                quotes = await self.fetch_quotes(sym)
                await callback(sym, trades, quotes)
            except Exception:
                log.exception("ahletrade_poll_failed", symbol=sym)
