"""Unified latest-price and previous-close resolver.

Strategy:
1. Try AhleTrade (real-time, if enabled) for the latest tick.
2. Fall back to psx_market_snapshot DB table.
3. Fall back to DPS market-watch.
4. previous_close: psx_ohlcv last bar < today, or psx_market_snapshot.change
   derivation.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.sqlalchemy import get_session_factory

log = logging.getLogger(__name__)


async def _latest_from_snapshot(
    session: AsyncSession, symbol: str
) -> Optional[dict[str, Any]]:
    try:
        row = await session.execute(
            text(
                "SELECT symbol, price, change, change_pct, volume, "
                "day_high, day_low, refreshed_at "
                "FROM psx_market_snapshot WHERE symbol = :sym"
            ),
            {"sym": symbol.upper()},
        )
        r = row.mappings().first()
        if r:
            return {
                "symbol": r["symbol"],
                "price": float(r["price"]) if r["price"] is not None else None,
                "change": float(r["change"]) if r["change"] is not None else None,
                "change_pct": (
                    float(r["change_pct"]) if r["change_pct"] is not None else None
                ),
                "volume": int(r["volume"]) if r["volume"] is not None else 0,
                "day_high": float(r["day_high"]) if r["day_high"] is not None else None,
                "day_low": float(r["day_low"]) if r["day_low"] is not None else None,
                "refreshed_at": (
                    str(r["refreshed_at"]) if r["refreshed_at"] is not None else None
                ),
                "source": "snapshot",
            }
    except Exception:
        log.exception("latest_from_snapshot failed")
    return None


async def _previous_close_from_ohlcv(
    session: AsyncSession, symbol: str
) -> Optional[float]:
    try:
        row = await session.execute(
            text(
                "SELECT close FROM psx_ohlcv "
                "WHERE symbol = :sym AND date < CURRENT_DATE "
                "ORDER BY date DESC LIMIT 1"
            ),
            {"sym": symbol.upper()},
        )
        r = row.first()
        if r and r[0] is not None:
            return float(r[0])
    except Exception:
        log.exception("previous_close_from_ohlcv failed")
    return None


async def get_latest_price(
    symbol: str, *, allow_external: bool = True
) -> Optional[dict[str, Any]]:
    """Return latest price dict with previous_close if available.

    Returns None only if no source is reachable and no cached data exists.
    """
    factory = get_session_factory()
    async with factory() as session:
        snap = await _latest_from_snapshot(session, symbol)
        prev_close = await _previous_close_from_ohlcv(session, symbol)

    if snap is not None and prev_close is not None:
        snap["previous_close"] = prev_close
    elif snap is not None and snap.get("price") is not None and snap.get("change") is not None:
        # Derive previous_close from price - change
        snap["previous_close"] = round(
            float(snap["price"]) - float(snap["change"]), 2
        )
    elif allow_external:
        # Fall back to DPS market-watch
        try:
            from app.services.psx.dps import get_dps_client

            rows = await get_dps_client().fetch_market_watch()
            for r in rows:
                if r["symbol"] == symbol.upper():
                    if r.get("price") is not None and r.get("change") is not None:
                        r["previous_close"] = round(
                            float(r["price"]) - float(r["change"]), 2
                        )
                    r["source"] = "dps"
                    return r
        except Exception:
            log.exception("dps fallback failed")
    if snap is not None and "previous_close" not in snap:
        snap["previous_close"] = None
    return snap


async def get_latest_prices_batch(symbols: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        r = await get_latest_price(sym)
        if r is not None:
            out[sym.upper()] = r
    return out
