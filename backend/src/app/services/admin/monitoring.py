"""Read-only operational monitoring. Each block degrades to available=False on
failure so a partial outage never fabricates green status."""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.repositories.admin import monitoring_repo
from app.repositories.base import connect
from app.schemas.admin import MetricBlock

log = logging.getLogger(__name__)


async def _block(conn, fn) -> MetricBlock:
    try:
        data = await fn(conn)
        payload = data if isinstance(data, dict) else {"items": data}
        return MetricBlock(available=True, data=payload)
    except Exception:
        log.warning("monitoring block failed: %s", getattr(fn, "__name__", fn), exc_info=True)
        return MetricBlock(available=False, data={})


async def market_data() -> dict[str, MetricBlock]:
    async with connect() as conn:
        return {
            "sources": await _block(conn, monitoring_repo.data_source_health),
            "index_snapshot": await _block(conn, monitoring_repo.index_snapshot_summary),
            "market_snapshot": await _block(conn, monitoring_repo.market_snapshot_summary),
        }


async def signals() -> dict[str, MetricBlock]:
    async with connect() as conn:
        return {
            "registry": await _block(conn, monitoring_repo.signal_registry),
            "counts": await _block(conn, monitoring_repo.signal_table_counts),
        }


async def ai_ops() -> dict[str, MetricBlock]:
    async with connect() as conn:
        return {"usage": await _block(conn, monitoring_repo.ai_usage_summary)}


async def system() -> dict[str, Any]:
    """System health: DB connectivity + deployment metadata. No secrets."""
    db_ok = False
    try:
        async with connect() as conn:
            db_ok = await monitoring_repo.db_ping(conn)
    except Exception:
        log.warning("system db_ping failed", exc_info=True)
    return {
        "database": {"available": db_ok},
        "deployment": {
            "process_role": settings.process_role,
            "scheduler_enabled": settings.runs_scheduler,
            "environment": "production" if settings.cors_origins != "*" else "local",
        },
    }
