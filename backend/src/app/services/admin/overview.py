"""Overview dashboard: real aggregate metrics only.

Each metric block is fetched independently and marked available=False on any
failure, so the overview degrades honestly (a block shows "unavailable")
instead of ever rendering fabricated numbers.
"""
from __future__ import annotations

import logging

from app.repositories.admin import audit_repo, metrics_repo
from app.repositories.base import connect
from app.schemas.admin import AuditEntry, MetricBlock, OverviewResponse

log = logging.getLogger(__name__)


async def _block(conn, fn) -> MetricBlock:
    try:
        data = await fn(conn)
        return MetricBlock(available=True, data=data)
    except Exception:
        log.warning("overview metric failed: %s", getattr(fn, "__name__", fn), exc_info=True)
        return MetricBlock(available=False, data={})


async def build_overview() -> OverviewResponse:
    async with connect() as conn:
        users = await _block(conn, metrics_repo.user_metrics)
        tiers = await _block(conn, metrics_repo.tier_distribution)
        engagement = await _block(conn, metrics_repo.engagement_metrics)
        try:
            recent = await audit_repo.recent_for_overview(conn, limit=10)
            recent_actions = [_partial_audit(r) for r in recent]
        except Exception:
            log.warning("overview recent_actions failed", exc_info=True)
            recent_actions = []
    return OverviewResponse(
        users=users,
        tiers=tiers,
        engagement=engagement,
        recent_actions=recent_actions,
    )


def _partial_audit(r: dict) -> AuditEntry:
    """recent_for_overview returns a projection; fill the rest as None."""
    return AuditEntry(
        id=r["id"],
        actor_email=r.get("actor_email"),
        action=r["action"],
        resource_type=r.get("resource_type"),
        target_user_id=(str(r["target_user_id"]) if r.get("target_user_id") else None),
        status=r.get("status", "success"),
        created_at=r["created_at"],
    )
