"""News endpoints: ticker-tagged news for the PSX.

Thin HTTP layer over the ``psx_news`` table populated by the BRecorder
scraper. Filter by ticker symbol with the ``symbol`` query param, or fetch
the latest overall.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from app.middleware.rate_limit import limiter

router = APIRouter(tags=["news"])


@router.get("/news")
@limiter.limit("30/minute")
async def list_news(
    request: Request,
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
):
    """News for a single ticker. Uses the GIN index on ``tickers`` for speed."""
    from app.db.supabase import async_execute

    if not symbol:
        return await _latest(request, limit=limit)
    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("psx_news")
        .select("id,headline,url,source,published_at,tickers,refreshed_at")
        .contains("tickers", [sym])
        .order("published_at", desc=True)
        .limit(limit)
    )
    return result.data or []


@router.get("/news/latest")
@limiter.limit("30/minute")
async def _latest(request: Request, limit: int = Query(10, ge=1, le=200)):
    from app.db.supabase import async_execute

    result = await async_execute(
        lambda c: c.table("psx_news")
        .select("id,headline,url,source,published_at,tickers,refreshed_at")
        .order("published_at", desc=True)
        .limit(limit)
    )
    return result.data or []
