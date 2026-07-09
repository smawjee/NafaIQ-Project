"""Notification routes: thin HTTP layer over services.notifications."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.schemas.notifications import NotifPrefsUpdate
from app.services import notifications as notifications_service

router = APIRouter(tags=["notifications"])


@router.get("/notifications/list")
async def list_notifications(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 50,
):
    return await notifications_service.list_notifications(user["user_id"], limit)


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    return await notifications_service.mark_read(user["user_id"], notification_id)


@router.get("/notifications/preferences")
async def get_prefs(user: Annotated[dict, Depends(require_user)]):
    return await notifications_service.get_prefs(user["user_id"])


@router.patch("/notifications/preferences")
async def update_prefs(
    body: NotifPrefsUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    return await notifications_service.update_prefs(user["user_id"], body)
