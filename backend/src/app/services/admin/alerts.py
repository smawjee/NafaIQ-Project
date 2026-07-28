"""Alert oversight for the admin console.

Follows the same honesty contract as the other monitoring services: each block
is fetched independently and marked `available=False` on failure, so a partial
outage degrades one card rather than blanking the page or inventing zeros.
"""
from __future__ import annotations

import logging

from app.repositories.admin import alerts_repo
from app.repositories.base import connect
from app.schemas.admin import MetricBlock

log = logging.getLogger(__name__)


async def _block(conn, fn) -> MetricBlock:
    try:
        data = await fn(conn)
        return MetricBlock(available=True, data=data if isinstance(data, dict) else {"items": data})
    except Exception:
        log.warning("alerts metric failed: %s", getattr(fn, "__name__", fn), exc_info=True)
        return MetricBlock(available=False, data={})


async def overview() -> dict[str, MetricBlock]:
    async with connect() as conn:
        return {
            "price_alerts": await _block(conn, alerts_repo.price_alert_summary),
            "app_alerts": await _block(conn, alerts_repo.app_alert_summary),
            "delivery": await _block(conn, alerts_repo.delivery_health),
            "events_by_day": await _block(conn, alerts_repo.events_by_day),
            "top_symbols": await _block(conn, alerts_repo.top_symbols),
        }
