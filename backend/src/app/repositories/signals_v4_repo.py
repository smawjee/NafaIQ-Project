"""Read/write boundaries for the V4 append-only signal tables."""
from __future__ import annotations

from typing import Any

from app.db.supabase import async_execute


async def verified_bars(symbol: str, limit: int = 600) -> list[dict[str, Any]]:
    result = await async_execute(
        lambda c: c.table("psx_ohlcv_verified")
        .select("symbol,date,open,high,low,close,volume,ldcp,verification_status,verification_version")
        .eq("symbol", symbol.upper())
        .eq("verification_status", "VERIFIED")
        .order("date", desc=True)
        .limit(limit)
    )
    return list(reversed(result.data or []))


async def latest_published_forecast(symbol: str) -> dict[str, Any] | None:
    result = await async_execute(
        lambda c: c.table("psx_signal_forecasts")
        .select("*")
        .eq("symbol", symbol.upper())
        .eq("status", "PUBLISHED")
        .order("issued_at", desc=True)
        .limit(1)
    )
    return (result.data or [None])[0]


async def event(event_id: str | None) -> dict[str, Any] | None:
    if not event_id:
        return None
    result = await async_execute(
        lambda c: c.table("psx_signal_events")
        .select("event_id,symbol,event_type,title,published_at,period_end,source_url,source_hash")
        .eq("event_id", event_id)
        .limit(1)
    )
    return (result.data or [None])[0]

