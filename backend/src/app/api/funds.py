"""MUFAP mutual funds endpoints.

Thin HTTP layer over the ``psx_mutual_funds`` and ``psx_fund_nav_history``
tables populated by the MUFAP scraper.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from app.middleware.rate_limit import limiter

router = APIRouter(tags=["funds"])


@router.get("/funds")
@limiter.limit("30/minute")
async def list_funds(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
):
    """List all mutual funds. Optionally filter by category."""
    from app.db.supabase import async_execute

    def _q(c):
        q = c.table("psx_mutual_funds").select("*").order("name", desc=False).range(offset, offset + limit - 1)
        if category:
            q = q.eq("category", category)
        return q

    result = await async_execute(_q)
    return result.data or []


@router.get("/funds/{fund_code}")
@limiter.limit("30/minute")
async def get_fund(
    request: Request,
    fund_code: str,
):
    """Single fund details by fund code."""
    from app.db.supabase import async_execute

    result = await async_execute(
        lambda c: c.table("psx_mutual_funds")
        .select("*")
        .eq("fund_code", fund_code)
        .limit(1)
    )
    rows = result.data or []
    if not rows:
        return {}
    return rows[0]


@router.get("/funds/{fund_code}/nav")
@limiter.limit("30/minute")
async def get_fund_nav(
    request: Request,
    fund_code: str,
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
):
    """NAV history for a fund. Optionally filter by days."""
    from app.db.supabase import async_execute

    def _q(c):
        q = c.table("psx_fund_nav_history").select("*").eq("fund_code", fund_code).order("date", desc=True).limit(limit)
        if days:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            q = q.gte("date", cutoff)
        return q

    result = await async_execute(_q)
    return result.data or []
