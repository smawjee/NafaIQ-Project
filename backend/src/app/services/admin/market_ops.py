"""Operational actions on the market-data pipeline, exposed to the admin console.

Deliberately narrow: this is not a generic "run any job" endpoint. Only
idempotent, safe-to-repeat refreshes are exposed, and each one is audited with
the row count it produced so the log shows whether the run actually did
anything.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException

from app.services.admin.audit import log_action
from app.services.admin.authz import AdminContext, RequestMeta

log = logging.getLogger(__name__)


async def refresh_market_snapshot(*, actor: AdminContext, meta: RequestMeta) -> dict:
    """Run the market-watch scrape immediately and upsert psx_market_snapshot.

    This is the same work `job_refresh_market` does on its 10-second cron, minus
    the market-hours guard — an admin asking for a refresh out of hours wants
    the latest available figures, not a silent no-op.

    Safe to invoke repeatedly: the write is an upsert keyed on `symbol`.
    """
    # Imported lazily: the scheduler module pulls in every scraper, and the web
    # process should not pay that import cost unless an admin actually asks for
    # a refresh.
    from datetime import datetime, timezone

    from app.api.health import set_market_refresh_time
    from app.db.supabase import async_execute
    from app.jobs.scheduler import _market_watch_tv_fallback, _record_health
    from app.scrapers import dps

    rows_written = 0
    source = "dps"
    try:
        items = await dps.fetch_market_watch()
    except Exception:
        # DPS /market-watch drops datacenter egress connections (2026-08-06);
        # the TradingView scanner keeps working from the same host. Fall back
        # so an admin refresh can still land fresh prices.
        log.warning("admin market refresh: DPS failed, using TradingView fallback", exc_info=True)
        source = "tv"
        items = await _market_watch_tv_fallback()
    try:
        if items:
            now = datetime.now(timezone.utc).isoformat()
            rows = [
                {
                    "symbol": item.symbol,
                    "price": item.price,
                    "change": item.change,
                    "change_pct": item.change_pct,
                    "volume": item.volume,
                    "day_high": item.day_high,
                    "day_low": item.day_low,
                    "refreshed_at": now,
                }
                for item in items
            ]
            if source == "tv":
                # TV rows carry no session extremes; omitting the columns keeps
                # the last DPS-derived day_high/day_low on the upsert.
                for r in rows:
                    r.pop("day_high", None)
                    r.pop("day_low", None)
            await async_execute(
                lambda c: c.table("psx_market_snapshot").upsert(rows, on_conflict="symbol")
            )
            set_market_refresh_time()
            rows_written = len(rows)
            await _record_health("market_snapshot", success=True, rows_updated=rows_written)
    except Exception as e:  # noqa: BLE001 - reported to the admin and audited
        log.exception("admin market refresh failed")
        try:
            await _record_health("market_snapshot", success=False, error=str(e))
        except Exception:
            log.warning("could not record source health for failed refresh", exc_info=True)
        await log_action(
            actor=actor,
            action="admin.market_data.refresh",
            resource_type="psx_market_snapshot",
            status="failure",
            reason=str(e)[:500],
            meta=meta,
        )
        raise HTTPException(502, f"Market data refresh failed: {e}") from e

    await log_action(
        actor=actor,
        action="admin.market_data.refresh",
        resource_type="psx_market_snapshot",
        after={"rows_updated": rows_written},
        status="success",
        meta=meta,
    )

    if rows_written == 0:
        # Not an error: the upstream source returned nothing (common outside
        # trading hours). Say so plainly rather than reporting a fake success.
        return {
            "status": "empty",
            "detail": "Refresh ran, but the upstream source returned no rows.",
            "rows_updated": 0,
        }
    return {
        "status": "ok",
        "detail": f"Refreshed {rows_written} symbols.",
        "rows_updated": rows_written,
    }
