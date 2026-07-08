from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import require_user
from app.db.sqlalchemy import get_engine

router = APIRouter(tags=["notifications"])


class NotifPrefsUpdate(BaseModel):
    email_alerts: bool | None = None
    push_alerts: bool | None = None
    in_app_alerts: bool | None = None


@router.get("/notifications/list")
async def list_notifications(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 50,
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, kind, title, body, link, read, created_at
                FROM in_app_notifications
                WHERE user_id = :uid
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"uid": user_id, "lim": limit},
        )
        rows = result.mappings().all()
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "title": r["title"],
            "body": r["body"],
            "link": r["link"],
            "read": r["read"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                UPDATE in_app_notifications
                SET read = true
                WHERE id = :nid AND user_id = :uid
                RETURNING id
            """),
            {"nid": notification_id, "uid": user_id},
        )
        row = result.first()
    if not row:
        raise HTTPException(404, "Notification not found")
    return {"id": notification_id, "read": True}


@router.get("/notifications/preferences")
async def get_prefs(user: Annotated[dict, Depends(require_user)]):
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT email_alerts, push_alerts, in_app_alerts FROM user_notification_prefs WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.mappings().first()
    if not row:
        return {"email_alerts": True, "push_alerts": False, "in_app_alerts": True}
    return dict(row)


@router.patch("/notifications/preferences")
async def update_prefs(
    body: NotifPrefsUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    user_id = user["user_id"]
    sets = []
    params: dict[str, Any] = {"uid": user_id}
    if body.email_alerts is not None:
        sets.append("email_alerts = :email")
        params["email"] = body.email_alerts
    if body.push_alerts is not None:
        sets.append("push_alerts = :push")
        params["push"] = body.push_alerts
    if body.in_app_alerts is not None:
        sets.append("in_app_alerts = :inapp")
        params["inapp"] = body.in_app_alerts

    if sets:
        sets.append("updated_at = now()")
        update_clause = ", ".join(sets)
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(f"""
                    INSERT INTO user_notification_prefs (user_id, email_alerts, push_alerts, in_app_alerts)
                    VALUES (:uid, COALESCE(:email, true), COALESCE(:push, false), COALESCE(:inapp, true))
                    ON CONFLICT (user_id) DO UPDATE
                    SET {update_clause}
                """),
                params,
            )
    return {"ok": True}
