"""Unusual activity endpoints: volume-spike detector output.

Thin HTTP layer over the ``psx_unusual_activity`` table populated by the
``VolumeSpikeDetector`` background job.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.middleware.rate_limit import limiter

router = APIRouter(tags=["market-unusual"])


@router.get("/market/unusual")
@limiter.limit("30/minute")
async def list_unusual(request: Request, limit: int = 20):
    """Latest volume spikes / unusual activity."""
    from app.db.supabase import async_execute

    result = await async_execute(
        lambda c: c.table("psx_unusual_activity")
        .select("*")
        .order("ts", desc=True)
        .limit(limit)
    )
    return result.data or []
