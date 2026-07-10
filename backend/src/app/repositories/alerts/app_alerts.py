"""App-alert data access (user_alerts: bill / budget / goal / stock_price rules)."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

from app.repositories.alerts._common import jsonb

Executor = Any


def _user_alert(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "type": r["type"],
        "title": r["title"],
        "meta": jsonb(r["meta"]),
        "enabled": r["enabled"],
        "triggered_at": str(r["triggered_at"]) if r["triggered_at"] else None,
        "created_at": str(r["created_at"]),
    }


async def list_user_alerts(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, type, title, meta, enabled, "
            "triggered_at, created_at "
            "FROM user_alerts WHERE user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    return [_user_alert(r) for r in rows.mappings().all()]


async def insert_user_alert(
    conn: Executor, user_id: str, alert_type: str, title: str, meta: dict[str, Any], enabled: bool
) -> dict[str, Any]:
    row = await conn.execute(
        text(
            "INSERT INTO user_alerts (user_id, type, title, meta, enabled) "
            "VALUES (:uid, :t, :title, CAST(:meta AS JSONB), :enabled) "
            "RETURNING id, user_id, type, title, meta, enabled, "
            "          triggered_at, created_at"
        ),
        {
            "uid": user_id,
            "t": alert_type,
            "title": title,
            "meta": json.dumps(meta or {}),
            "enabled": enabled,
        },
    )
    return _user_alert(row.mappings().first())


async def toggle_user_alert(
    conn: Executor, user_id: str, alert_id: int, enabled: bool
) -> Optional[int]:
    row = await conn.execute(
        text(
            "UPDATE user_alerts SET enabled = :en "
            "WHERE id = :id AND user_id = :uid RETURNING id"
        ),
        {"id": alert_id, "uid": user_id, "en": enabled},
    )
    return alert_id if row.first() else None


async def delete_user_alert(conn: Executor, user_id: str, alert_id: int) -> bool:
    row = await conn.execute(
        text("DELETE FROM user_alerts WHERE id = :id AND user_id = :uid RETURNING id"),
        {"id": alert_id, "uid": user_id},
    )
    return row.first() is not None
