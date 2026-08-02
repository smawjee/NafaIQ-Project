"""Read boundaries for the signals engine.

This domain persists to Supabase (not the SQLAlchemy pooler), so the repo wraps
the Supabase client here and keeps the service free of data-access calls.

The engine reads the same OHLCV the rest of the app reads (``psx_ohlcv``) and
applies the corporate-action adjustment at serving time, so prices agree
everywhere. There is intentionally no separate ``psx_ohlcv_verified`` copy — the
duplicate-storage design was dropped (no disk headroom for a second full copy).
"""
from __future__ import annotations

from typing import Any

from app.db.supabase import async_execute
from app.services.signals.adjustments import adjust_ohlcv, load_adjustment_events


async def top_symbols_by_volume(limit: int) -> list[str]:
    snapshot = await async_execute(
        lambda c: (
            c.table("psx_market_snapshot")
            .select("symbol")
            .order("volume", desc=True)
            .limit(limit)
        )
    )
    return [r["symbol"] for r in (snapshot.data or [])]


async def adjusted_bars(symbol: str, limit: int = 365) -> list[dict[str, Any]]:
    """Confirmed EOD bars from ``psx_ohlcv``, corporate-action adjusted.

    Recorded ``psx_dividends`` events only (mode="price"), no price-gap
    inference, latest bar stays raw. Any failure falls back to raw rows so a
    missing dividend row never blocks a setup.
    """
    sym = symbol.upper()
    history = await async_execute(
        lambda c: c.table("psx_ohlcv")
        .select("symbol,date,open,high,low,close,volume")
        .eq("symbol", sym)
        .order("date", desc=True)
        .limit(limit)
    )
    rows = list(reversed(history.data or []))
    if not rows:
        return rows
    try:
        div_res = await async_execute(
            lambda c: c.table("psx_dividends")
            .select("symbol,ex_date,payout_type,per_share,bonus_pct")
            .eq("symbol", sym)
            .not_.is_("ex_date", "null")
        )
        events = load_adjustment_events(div_res.data or []).get(sym) or []
        return adjust_ohlcv(rows, events, mode="price")
    except Exception:
        return rows


async def context_inputs(symbol: str) -> dict[str, Any]:
    """Best-effort side inputs for the honest context block (never raises)."""
    sym = symbol.upper()
    snapshot: dict[str, Any] | None = None
    fundamentals: dict[str, Any] = {}
    profile: dict[str, Any] = {}
    kse_rows: list[dict[str, Any]] = []
    try:
        snapshot_res = await async_execute(
            lambda c: c.table("psx_market_snapshot").select("*").eq("symbol", sym).limit(1)
        )
        snapshot = (snapshot_res.data or [None])[0]
    except Exception:
        pass
    try:
        fundamentals_res = await async_execute(
            lambda c: c.table("psx_fundamentals").select("*").eq("symbol", sym).limit(1)
        )
        fundamentals = (fundamentals_res.data or [{}])[0]
    except Exception:
        pass
    try:
        profile_res = await async_execute(
            lambda c: c.table("psx_profile").select("*").eq("symbol", sym).limit(1)
        )
        profile = (profile_res.data or [{}])[0]
    except Exception:
        pass
    try:
        kse_res = await async_execute(
            lambda c: c.table("psx_index_eod")
            .select("date,close")
            .eq("code", "KSE100")
            .order("date", desc=True)
            .limit(365)
        )
        kse_rows = list(reversed(kse_res.data or []))
    except Exception:
        pass
    return {"snapshot": snapshot, "fundamentals": fundamentals, "profile": profile, "kse_rows": kse_rows}


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


async def cross_section(symbol: str) -> dict[str, Any] | None:
    result = await async_execute(
        lambda c: c.table("psx_signal_cross_section")
        .select("symbol,as_of,composite_percentile,universe_size,factors")
        .eq("symbol", symbol.upper())
        .limit(1)
    )
    return (result.data or [None])[0]


async def quarterly_financials(symbol: str, limit: int = 24) -> list[dict[str, Any]]:
    result = await async_execute(
        lambda c: c.table("psx_financials_quarterly")
        .select("symbol,period,end_date,sales,net_income,eps")
        .eq("symbol", symbol.upper())
        .order("period", desc=True)
        .limit(limit)
    )
    return result.data or []


async def annual_financials(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    result = await async_execute(
        lambda c: c.table("psx_financials_annual")
        .select("symbol,year,sales,net_income,eps,gpm,npm,roe,roa")
        .eq("symbol", symbol.upper())
        .order("year", desc=True)
        .limit(limit)
    )
    return result.data or []


async def recent_events(symbol: str, limit: int = 3) -> list[dict[str, Any]]:
    """Most recent point-in-time corporate events for a symbol (honest context)."""
    result = await async_execute(
        lambda c: c.table("psx_signal_events")
        .select("event_id,symbol,event_type,title,published_at,period_end,source_url")
        .eq("symbol", symbol.upper())
        .order("published_at", desc=True)
        .limit(limit)
    )
    return result.data or []


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
