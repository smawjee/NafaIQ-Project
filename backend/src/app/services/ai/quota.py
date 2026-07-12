"""Daily AI-tutor quota: plan_features.ai_tutor_daily_limit vs ai_usage.

The limit arrives on the require_user result (features dict) — no extra DB
read. Only today's used-count is queried. limit None => unlimited.
"""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import ai_repo
from app.repositories.base import connect


async def check_quota(user: dict[str, Any]) -> tuple[bool, int, Optional[int]]:
    limit = (user.get("features") or {}).get("ai_tutor_daily_limit")
    async with connect() as conn:
        used = await ai_repo.get_today_usage(conn, user["user_id"])
    if limit is None:
        return True, used, None
    return used < int(limit), used, int(limit)


async def usage_summary(user: dict[str, Any]) -> dict[str, Any]:
    _, used, limit = await check_quota(user)
    remaining = None if limit is None else max(0, limit - used)
    return {"used": used, "limit": limit, "remaining": remaining}
