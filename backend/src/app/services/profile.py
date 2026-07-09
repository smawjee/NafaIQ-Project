"""User profile operations: onboarding plan selection.

Plan changes go through the backend service connection — the
prevent_profile_plan_self_update DB trigger still blocks direct client-side
plan tampering via Supabase. When payments land, Pro/Premium selection should
route through checkout before hitting this.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import user_repo as repo
from app.repositories.base import begin


async def select_plan(user_id: str, requested_plan: str) -> dict[str, Any]:
    """Select/switch the user's plan and stamp plan_selected_at."""
    plan = requested_plan.strip().title()
    async with begin() as conn:
        if not await repo.is_known_plan(conn, plan):
            raise HTTPException(400, f"Unknown plan '{requested_plan}'")
        result = await repo.update_plan(conn, user_id, plan)
    if result is None:
        raise HTTPException(404, "Profile not found")
    return result
