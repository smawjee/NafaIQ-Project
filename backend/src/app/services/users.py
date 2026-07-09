"""User profile lookups: plan + plan_features for a user.

Separated from token verification (services.auth) so auth stays a pure JWT
concern. DB access is delegated to app.repositories.user_repo.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories import user_repo as repo
from app.repositories.base import connect

log = logging.getLogger(__name__)


async def get_user_plan_features(user_id: str) -> tuple[Optional[str], dict[str, Any]]:
    """Return (plan, features) for a user. (None, {}) when the profile row is
    missing or the lookup fails; callers decide the fallback plan."""
    try:
        async with connect() as conn:
            row = await repo.get_plan_features(conn, user_id)
        if row:
            plan = row["plan"]
            return plan, {k: v for k, v in row.items() if k != "plan"}
    except Exception:
        log.warning("plan/features lookup failed for %s", user_id, exc_info=True)
    return None, {}
