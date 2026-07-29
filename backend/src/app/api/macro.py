"""Macro endpoints: KIBOR, PKRV, policy rate, FX (SBP-backed).

Thin HTTP layer over the ``macro_rates`` table populated by the SBP scraper.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.middleware.rate_limit import limiter
from app.services.macro.monetary import get_monetary_snapshot

router = APIRouter(tags=["macro"])


@router.get("/macro/rates")
@limiter.limit("30/minute")
async def get_rates(
    request: Request,
    series: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    limit: int = Query(500, ge=1, le=500),
):
    """List macro rate rows. Optional ``series`` filter; date range filter."""
    from app.db.supabase import async_execute

    def _q(c):
        q = c.table("macro_rates").select("*").order("date", desc=True).limit(limit)
        if series:
            q = q.eq("series", series)
        if date_from:
            q = q.gte("date", date_from.isoformat())
        if date_to:
            q = q.lte("date", date_to.isoformat())
        return q

    result = await async_execute(_q)
    return result.data or []


@router.get("/macro/fx")
@limiter.limit("30/minute")
async def get_fx(request: Request):
    """Latest USD/PKR, EUR/PKR, GBP/PKR rates (buying + selling)."""
    from app.db.supabase import async_execute

    result = await async_execute(
        lambda c: c.table("macro_rates")
        .select("*")
        .like("series", "FX_%")
        .order("date", desc=True)
        .limit(60)
    )
    rows = result.data or []
    by_currency: dict[str, dict] = {}
    for row in rows:
        ser = row.get("series", "")
        # series = "FX_USD_BUY" or "FX_EUR_SELL"
        parts = ser.split("_")
        if len(parts) != 3:
            continue
        _, ccy, side = parts
        entry = by_currency.setdefault(
            ccy, {"currency": ccy, "date": row.get("date"), "buy": None, "sell": None}
        )
        # Newest row first; keep first occurrence per side.
        if side.upper() == "BUY" and entry["buy"] is None:
            entry["buy"] = row.get("value")
            entry["date"] = row.get("date")
        elif side.upper() == "SELL" and entry["sell"] is None:
            entry["sell"] = row.get("value")
            entry["date"] = row.get("date")
    return sorted(by_currency.values(), key=lambda x: x["currency"])


@router.get("/macro/policy-rate")
@limiter.limit("30/minute")
async def get_policy_rate(request: Request):
    """Latest SBP policy rate."""
    from app.db.supabase import async_execute

    result = await async_execute(
        lambda c: c.table("macro_rates")
        .select("*")
        .eq("series", "POLICY_RATE")
        .order("date", desc=True)
        .limit(1)
    )
    rows = result.data or []
    if not rows:
        return {"series": "POLICY_RATE", "date": None, "value": None}
    return rows[0]


@router.get("/macro/monetary")
@limiter.limit("30/minute")
async def get_monetary(request: Request, refresh: bool = Query(False)):
    """Live currency conversion plus Pakistan gold/silver reference prices."""
    try:
        return await get_monetary_snapshot(force=refresh)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Live monetary data is unavailable right now.",
        ) from exc
