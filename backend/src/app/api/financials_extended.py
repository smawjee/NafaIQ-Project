"""Financials endpoints: 5y annual + quarterly per symbol.

Thin HTTP layer over the ``psx_financials_annual`` and
``psx_financials_quarterly`` tables populated by the FinancialsPSXScraper.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.middleware.rate_limit import limiter

router = APIRouter(tags=["financials-extended"])


@router.get("/financials/{symbol}/annual")
@limiter.limit("30/minute")
async def annual(request: Request, symbol: str, limit: int = Query(10, ge=1, le=50)):
    """5y annual financials for a symbol, newest year first."""
    from app.db.supabase import async_execute

    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("psx_financials_annual")
        .select("*")
        .eq("symbol", sym)
        .order("year", desc=True)
        .limit(limit)
    )
    return result.data or []


@router.get("/financials/{symbol}/quarterly")
@limiter.limit("30/minute")
async def quarterly(request: Request, symbol: str, limit: int = Query(20, ge=1, le=50)):
    """Quarterly financials for a symbol, most recent first."""
    from app.db.supabase import async_execute

    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("psx_financials_quarterly")
        .select("*")
        .eq("symbol", sym)
        .order("period", desc=True)
        .limit(limit)
    )
    return result.data or []
