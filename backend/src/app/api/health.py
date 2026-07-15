"""Health routes: thin HTTP layer over services.health.

`set_market_refresh_time` is re-exported for backwards compatibility with
existing importers (e.g. the scheduler).
"""
from fastapi import APIRouter

from app.services.health import (  # noqa: F401
    db_ping,
    get_market_refresh_time,
    set_market_refresh_time,
)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "last_market_refresh": get_market_refresh_time(),
    }


@router.get("/health/db")
async def health_db():
    return await db_ping()


@router.get("/health/sources")
async def health_sources():
    """Return last-success / last-error timestamps per data source.

    Reads from psx_data_source_health table and returns all rows ordered
    by source name. Used by the frontend observability widget.
    """
    from app.db.supabase import async_execute
    try:
        result = await async_execute(lambda c: c.table("psx_data_source_health")
                                     .select("*")
                                     .order("source"))
        rows = result.data or []
        return {"sources": rows, "healthy": True}
    except Exception as e:
        return {"sources": [], "healthy": False, "error": str(e)}
