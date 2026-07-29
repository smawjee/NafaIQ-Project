"""User profile routes: thin HTTP layer over services.profile."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.schemas.profile import PlanSelect
from app.services import profile as profile_service

router = APIRouter(tags=["profile"])


@router.post("/profile/plan")
async def select_plan(
    body: PlanSelect,
    user: Annotated[dict, Depends(require_user)],
):
    """Select/switch the user's plan and stamp plan_selected_at."""
    return await profile_service.select_plan(user["user_id"], body.plan)
