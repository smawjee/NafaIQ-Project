"""Market quote/reference reads: snapshot, quote, symbols, fundamentals,
profile, announcements, dividends, index EOD/cards, sectors. Thin cache
passthroughs (memory TTL -> Supabase -> scrape)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services.market._base import (
    INDEX_CARD_CODES,
    TTL_FUNDAMENTALS,
    TTL_INDEX,
    TTL_PROFILE,
    TTL_SECTORS,
    TTL_SYMBOLS,
    get_cache,
    snapshot_rows,
)
from app.services.memcache import mem_cache


async def market_snapshot() -> list[dict[str, Any]]:
    return await snapshot_rows()


async def quote(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    # In-memory scan of the cached snapshot — no per-quote network fetch.
    for row in await snapshot_rows():
        if row["symbol"] == sym:
            return row
    raise HTTPException(404, f"Symbol {symbol} not found in market snapshot")


async def symbols() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_symbols()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("symbols", TTL_SYMBOLS, load)


async def fundamentals(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()

    async def load() -> dict[str, Any]:
        f = await get_cache().get_fundamentals(sym)
        return f.model_dump(mode="json")

    return await mem_cache.get_or_load(f"fundamentals:{sym}", TTL_FUNDAMENTALS, load)


async def profile(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()

    async def load() -> dict[str, Any] | None:
        p = await get_cache().get_profile(sym)
        return p.model_dump(mode="json") if p is not None else None

    result = await mem_cache.get_or_load(f"profile:{sym}", TTL_PROFILE, load)
    if result is None:
        raise HTTPException(404, f"Profile for {symbol} not found")
    return result


async def announcements(symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    items = await get_cache().get_announcements(symbol, limit)
    return [i.model_dump(mode="json") for i in items]


async def dividends(symbol: str) -> list[dict[str, Any]]:
    events = await get_cache().get_dividends(symbol)
    return [e.model_dump(mode="json") for e in events]


async def index_eod(code: str) -> list[dict[str, Any]]:
    c = code.upper()

    async def load() -> list[dict[str, Any]]:
        bars = await get_cache().get_index_eod(c)
        return [b.model_dump(mode="json") for b in bars]

    return await mem_cache.get_or_load(f"index:{c}", TTL_INDEX, load)


async def index_cards() -> list[dict[str, Any]]:
    """Latest + previous close per benchmark index — one light payload for
    the dashboard cards instead of four full-history downloads."""

    async def load() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for code in INDEX_CARD_CODES:
            bars = await get_cache().get_index_latest(code, bars=2)
            if not bars:
                continue
            latest = bars[0]
            prev = bars[1] if len(bars) > 1 else None
            change = (latest.close - prev.close) if prev else 0.0
            change_pct = (change / prev.close * 100) if prev and prev.close else 0.0
            out.append(
                {
                    "code": code,
                    "date": latest.date.isoformat() if latest.date else None,
                    "close": latest.close,
                    "prev_close": prev.close if prev else None,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                }
            )
        return out

    return await mem_cache.get_or_load("index_cards", TTL_INDEX, load)


async def sectors() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_sectors()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("sectors", TTL_SECTORS, load)
