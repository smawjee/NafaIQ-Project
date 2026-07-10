"""In-app notification feed + per-user preferences (business logic).

All SQL is delegated to app.repositories.notifications_repo.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import notifications_repo as repo
from app.repositories.base import begin, connect
from app.schemas.notifications import NotifPrefsUpdate

_DEFAULT_PREFS = {"email_alerts": False, "push_alerts": False, "in_app_alerts": True}


async def list_notifications(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_notifications(conn, user_id, limit)


async def mark_read(user_id: str, notification_id: int) -> dict[str, Any]:
    async with begin() as conn:
        updated = await repo.mark_read(conn, user_id, notification_id)
    if updated is None:
        raise HTTPException(404, "Notification not found")
    return {"id": notification_id, "read": True}


async def get_prefs(user_id: str) -> dict[str, Any]:
    async with connect() as conn:
        row = await repo.get_prefs(conn, user_id)
    return row if row else dict(_DEFAULT_PREFS)


async def update_prefs(user_id: str, body: NotifPrefsUpdate) -> dict[str, Any]:
    async with begin() as conn:
        await repo.upsert_prefs(
            conn,
            user_id,
            email_alerts=body.email_alerts,
            push_alerts=body.push_alerts,
            in_app_alerts=body.in_app_alerts,
        )
    return {"ok": True}
