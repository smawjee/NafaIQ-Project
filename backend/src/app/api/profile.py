"""User profile endpoints: onboarding plan selection.

Plan changes go through this endpoint (service connection) — the
prevent_profile_plan_self_update DB trigger still blocks direct client-side
plan tampering via Supabase. When payments land, Pro/Premium selection should
route through checkout before hitting this.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine

router = APIRouter(tags=["profile"])


class PlanSelect(BaseModel):
    plan: str = Field(..., min_length=1, max_length=20)


@router.post("/profile/plan")
async def select_plan(
    body: PlanSelect,
    user: Annotated[dict, Depends(require_user)],
):
    """Select/switch the user's plan and stamp plan_selected_at."""
    plan = body.plan.strip().title()
    engine = get_engine()
    async with engine.begin() as conn:
        known = await conn.execute(
            text("SELECT 1 FROM plan_features WHERE plan = :p"), {"p": plan}
        )
        if not known.first():
            raise HTTPException(400, f"Unknown plan '{body.plan}'")
        row = await conn.execute(
            text(
                "UPDATE profiles SET plan = :p, plan_selected_at = now() "
                "WHERE id = :uid RETURNING plan, plan_selected_at"
            ),
            {"p": plan, "uid": user["user_id"]},
        )
        r = row.mappings().first()
    if not r:
        raise HTTPException(404, "Profile not found")
    return {"plan": r["plan"], "plan_selected_at": str(r["plan_selected_at"])}
