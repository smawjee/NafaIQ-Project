"""Market quote/reference reads: snapshot, quote, symbols, fundamentals,
profile, announcements, dividends, index EOD/cards, sectors. Thin cache
passthroughs (memory TTL -> Supabase -> scrape)."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException

from app.models import IndexBar
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
        live = await _live_index_by_code()
        live_row = live.get(c)
        if live_row is not None:
            live_date = _parse_date(live_row.get("date"))
            latest_eod = max((b.date for b in bars if b.date is not None), default=None)
            if live_date is not None and (latest_eod is None or live_date > latest_eod):
                close = live_row.get("close")
                if close is not None:
                    bars = [
                        *bars,
                        IndexBar(
                            code=c,
                            date=live_date,
                            open=close,
                            high=close,
                            low=close,
                            close=close,
                            volume=None,
                        ),
                    ]
        return [b.model_dump(mode="json") for b in bars]

    return await mem_cache.get_or_load(f"index:{c}", TTL_INDEX, load)


async def index_cards() -> list[dict[str, Any]]:
    """Latest + previous close per benchmark index — one light payload for
    the dashboard cards instead of four full-history downloads."""

    async def load() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        live = await _live_index_by_code()
        # Same rows as `live`, but unfiltered by age. Used only to date-compare
        # against the EOD bar below: after the session ends the live tier goes
        # empty, and the day's final snapshot is still newer than the EOD table
        # until the 18:00 PKT ingest lands.
        recent = await _index_snapshot_by_code()
        for code in INDEX_CARD_CODES:
            card = _card_from_snapshot(code, live.get(code))
            if card is not None:
                out.append(card)
                continue
            bars = await get_cache().get_index_latest(code, bars=2)
            snapshot = recent.get(code)
            if not bars:
                # No EOD history at all — a snapshot of any age beats no card.
                card = _card_from_snapshot(code, snapshot)
                if card is not None:
                    out.append(card)
                continue
            latest = bars[0]
            # Prefer the snapshot only when it is strictly *newer* than the
            # newest EOD bar. Never the other way round: a stale snapshot must
            # not override a fresher official close.
            snapshot_date = _parse_date((snapshot or {}).get("date"))
            if snapshot_date is not None and (
                latest.date is None or snapshot_date > latest.date
            ):
                card = _card_from_snapshot(code, snapshot)
                if card is not None:
                    out.append(card)
                    continue
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


def _card_from_snapshot(
    code: str, row: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Shape one `psx_index_live_snapshot` row as an index card.

    Returns None when there is no row or it carries no close, so callers can
    treat "unusable" and "absent" identically and fall through to EOD.
    """
    if not row:
        return None
    close = row.get("close")
    if close is None:
        return None
    return {
        "code": code,
        "date": row.get("date"),
        "close": close,
        "prev_close": row.get("prev_close"),
        "change": round(row.get("change") or 0.0, 2),
        "change_pct": round(row.get("change_pct") or 0.0, 2),
    }


async def _live_index_by_code() -> dict[str, dict[str, Any]]:
    try:
        rows = await get_cache().get_live_index_snapshot()
    except Exception:
        return {}
    return {str(r.get("code", "")).upper(): r for r in rows if r.get("code")}


async def _index_snapshot_by_code() -> dict[str, dict[str, Any]]:
    """Snapshot rows regardless of age — for date comparison only."""
    try:
        rows = await get_cache().get_index_snapshot_any_age()
    except Exception:
        return {}
    return {str(r.get("code", "")).upper(): r for r in rows if r.get("code")}


def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (ValueError, TypeError):
        return None


async def sectors() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_sectors()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("sectors", TTL_SECTORS, load)
