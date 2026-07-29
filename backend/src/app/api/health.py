"""Health routes: thin HTTP layer over services.health.

`set_market_refresh_time` is re-exported for backwards compatibility with
existing importers (e.g. the scheduler).
"""
import logging

from fastapi import APIRouter, Request

from app.middleware.rate_limit import limiter
from app.services.health import (  # noqa: F401
    db_ping,
    get_market_refresh_time,
    set_market_refresh_time,
)

log = logging.getLogger(__name__)

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
@limiter.limit("30/minute")
async def health_sources(request: Request):
    """Return last-success / last-error timestamps per data source.

    Reads from psx_data_source_health table and returns all rows ordered
    by source name. Used by the frontend observability widget.
    """
    from app.db.supabase import async_execute
    try:
        # Explicit columns, NOT select("*"): last_error_message holds the raw
        # str(e) that _record_health captured from the job, which can carry the
        # Supabase project URL, table names and connection detail. This
        # endpoint is anonymous, so the widget gets the error *timestamp* to
        # show a source as unhealthy; the text stays in the logs.
        result = await async_execute(lambda c: c.table("psx_data_source_health")
                                     .select("source,last_success,last_error,"
                                             "rows_updated,refreshed_at")
                                     .order("source"))
        rows = result.data or []
        return {"sources": rows, "healthy": True}
    except Exception:
        # This endpoint is public — never echo the exception text, it can carry
        # the project URL, table names and connection detail.
        log.exception("health_sources query failed")
        return {"sources": [], "healthy": False, "error": "health check unavailable"}
