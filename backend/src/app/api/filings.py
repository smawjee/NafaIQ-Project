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
    """List filings for ``symbol`` (most recent first), without the PDF body —
    up to 200 full texts per response is megabytes of payload the list view has
    no use for. ``get_filing`` serves the body for the one filing being read."""
    from app.db.supabase import async_execute

    sym = symbol.upper()
    result = await async_execute(
        lambda c: c.table("filings")
        .select("announcement_id,symbol,type,filed_at,pdf_url,page_count,refreshed_at")
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
    from app.db.supabase import async_execute

    sym = symbol.upper()
    # ``type="web_search"`` maps to websearch_to_tsquery, which parses arbitrary
    # free text safely (never raises on user input) and needs no sanitizing.
    # The previous regex both under- and over-shot: it left `<`, `>`, `-` and `'`
    # (so query semantics were still reachable) while the default `to_tsquery`
    # backend 500'd on any multi-word query like "annual report", since
    # to_tsquery requires explicit operators between lexemes.
    # NOTE: postgrest maps only the exact token "web_search" to `wfts` — the
    # spelling "websearch" silently falls back to plain `fts` (to_tsquery).
    #
    # This was never SQL injection: the value is a PostgREST filter argument,
    # passed to websearch_to_tsquery(), never concatenated into SQL.
    #
    # Postgres FTS via ``textsearch`` filter. The GIN index on
    # ``to_tsvector('english', text_content)`` is what makes this fast.
    result = await async_execute(
        lambda c: c.table("filings")
        .select("announcement_id,symbol,type,filed_at,pdf_url,page_count")
        .eq("symbol", sym)
        .text_search(
            "text_content", q.strip(), options={"type": "web_search", "config": "english"}
        )
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
