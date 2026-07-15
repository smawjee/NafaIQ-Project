"""In-app notifications data access: feed + per-user preferences."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def list_notifications(conn: Executor, user_id: str, limit: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, kind, title, body, link, read, created_at
            FROM in_app_notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :lim
            """
        ),
        {"uid": user_id, "lim": limit},
    )
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
        for r in result.mappings().all()
    ]


async def mark_read(conn: Executor, user_id: str, notification_id: int) -> Optional[int]:
    result = await conn.execute(
        text(
            """
            UPDATE in_app_notifications
            SET read = true
            WHERE id = :nid AND user_id = :uid
            RETURNING id
            """
        ),
        {"nid": notification_id, "uid": user_id},
    )
    return notification_id if result.first() else None


async def get_prefs(conn: Executor, user_id: str) -> Optional[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT email_alerts, email_activity, push_alerts, in_app_alerts "
            "FROM user_notification_prefs WHERE user_id = :uid"
        ),
        {"uid": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def upsert_prefs(
    conn: Executor,
    user_id: str,
    *,
    email_alerts: Optional[bool],
    email_activity: Optional[bool],
    push_alerts: Optional[bool],
    in_app_alerts: Optional[bool],
) -> None:
    sets = []
    # INSERT binds :email/:activity/:push/:inapp unconditionally, so all keys
    # must be present even when only one preference changes.
    params: dict[str, Any] = {
        "uid": user_id,
        "email": email_alerts,
        "activity": email_activity,
        "push": push_alerts,
        "inapp": in_app_alerts,
    }
    if email_alerts is not None:
        sets.append("email_alerts = :email")
    if email_activity is not None:
        sets.append("email_activity = :activity")
    if push_alerts is not None:
        sets.append("push_alerts = :push")
    if in_app_alerts is not None:
        sets.append("in_app_alerts = :inapp")
    if not sets:
        return
    sets.append("updated_at = now()")
    update_clause = ", ".join(sets)
    await conn.execute(
        text(
            f"""
            INSERT INTO user_notification_prefs
                (user_id, email_alerts, email_activity, push_alerts, in_app_alerts)
            -- email/activity/push are opt-in (default off); in-app is on by default.
            VALUES (:uid, COALESCE(:email, false), COALESCE(:activity, false),
                    COALESCE(:push, false), COALESCE(:inapp, true))
            ON CONFLICT (user_id) DO UPDATE
            SET {update_clause}
            """
        ),
        params,
    )
