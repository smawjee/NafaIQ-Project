"""Filings endpoints: per-symbol PSX announcements with PDF text + FTS.

Thin HTTP layer over the ``filings`` table populated by the PDF fetcher.
Provides list / search / single endpoints. The full-text search uses
Postgres ``to_tsvector`` / ``@@`` (the GIN index on
``to_tsvector('english', text_content)``).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.middleware.rate_limit import limiter

router = APIRouter(tags=["filings"])


@router.get("/filings/{symbol}")
@limiter.limit("30/minute")
async def list_filings(
    request: Request,
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
):
    """List filings for ``symbol`` (most recent first)."""
    from app.db.supabase import async_execute

    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("filings")
        .select("announcement_id,symbol,type,filed_at,pdf_url,text_content,page_count,refreshed_at")
        .eq("symbol", sym)
        .order("filed_at", desc=True)
        .limit(limit)
    )
    return result.data or []


@router.get("/filings/{symbol}/search")
@limiter.limit("30/minute")
async def search_filings(
    request: Request,
    symbol: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
):
    """Full-text search the body of a symbol's filings."""
    import re
    from app.db.supabase import async_execute

    sym = symbol.upper()
    # Strip tsquery operators to prevent users from controlling query semantics
    sanitized_q = re.sub(r'[&|!:*()]', ' ', q).strip()
    # Postgres FTS via ``textsearch`` filter. The GIN index on
    # ``to_tsvector('english', text_content)`` is what makes this fast.
    result = await async_execute(
        lambda c: c.table("filings")
        .select("announcement_id,symbol,type,filed_at,pdf_url,page_count")
        .eq("symbol", sym)
        .text_search("text_content", sanitized_q, options={"config": "english"})
        .order("filed_at", desc=True)
        .limit(limit)
    )
    return result.data or []


@router.get("/filings/{symbol}/{announcement_id}")
@limiter.limit("30/minute")
async def get_filing(
    request: Request,
    symbol: str,
    announcement_id: str,
):
    """Single filing with full extracted text."""
    from app.db.supabase import async_execute

    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("filings")
        .select("announcement_id,symbol,type,filed_at,pdf_url,text_content,page_count,refreshed_at")
        .eq("symbol", sym)
        .eq("announcement_id", announcement_id)
        .limit(1)
    )
    rows = result.data or []
    if not rows:
        raise HTTPException(404, "filing not found")
    return rows[0]
