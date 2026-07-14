"""Daily AI-tutor quota: plan_features.ai_tutor_daily_limit vs ai_usage.

The limit arrives on the require_user result (features dict) — no extra DB
read. Only today's used-count is queried. limit None => unlimited.
"""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import ai_repo, reports_repo
from app.repositories.base import connect


async def check_quota(user: dict[str, Any]) -> tuple[bool, int, Optional[int]]:
    limit = (user.get("features") or {}).get("ai_tutor_daily_limit")
    async with connect() as conn:
        used = await ai_repo.get_today_usage(conn, user["user_id"])
    if limit is None:
        return True, used, None
    return used < int(limit), used, int(limit)


async def check_report_quota(user: dict[str, Any]) -> tuple[bool, int, Optional[int]]:
    """Period-aware AI-report quota (day/week/month).

    Reads `ai_reports_per_period` / `ai_reports_period` off the require_user
    features dict (populated by user_repo.get_plan_features) and counts usage in
    the current period from ai_report_usage. limit None => unlimited (Premium).
    """
    features = user.get("features") or {}
    limit = features.get("ai_reports_per_period")
    period = features.get("ai_reports_period") or "month"
    async with connect() as conn:
        used = await reports_repo.get_period_usage(conn, user["user_id"], period)
    if limit is None:
        return True, used, None
    return used < int(limit), used, int(limit)


async def usage_summary(user: dict[str, Any]) -> dict[str, Any]:
    _, used, limit = await check_quota(user)
    remaining = None if limit is None else max(0, limit - used)
    return {"used": used, "limit": limit, "remaining": remaining}
