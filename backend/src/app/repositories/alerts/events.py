"""Alert-event + in-app notification writes/reads, plus the 24h idempotency
check the evaluators use."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

from app.repositories.alerts._common import jsonb

Executor = Any


async def list_alert_events(conn: Executor, user_id: str, limit: int) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, alert_id, alert_type, symbol, title, body, "
            "payload, channel, delivered_at, read_at, created_at "
            "FROM alert_events WHERE user_id = :uid "
            "ORDER BY created_at DESC LIMIT :lim"
        ),
        {"uid": user_id, "lim": max(1, min(limit, 500))},
    )
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "alert_id": r["alert_id"],
            "alert_type": r["alert_type"],
            "symbol": r["symbol"],
            "title": r["title"],
            "body": r["body"],
            "payload": jsonb(r["payload"]),
            "channel": r["channel"],
            "delivered_at": str(r["delivered_at"]) if r["delivered_at"] else None,
            "read_at": str(r["read_at"]) if r["read_at"] else None,
            "created_at": str(r["created_at"]),
        }
        for r in rows.mappings().all()
    ]


async def mark_event_read(conn: Executor, user_id: str, event_id: int) -> bool:
    row = await conn.execute(
        text(
            "UPDATE alert_events SET read_at = now() "
            "WHERE id = :id AND user_id = :uid AND read_at IS NULL "
            "RETURNING id"
        ),
        {"id": event_id, "uid": user_id},
    )
    return row.first() is not None


async def insert_alert_event(
    conn: Executor,
    user_id: str,
    alert_id: Optional[int],
    alert_type: str,
    symbol: Optional[str],
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        text(
            "INSERT INTO alert_events "
            "(user_id, alert_id, alert_type, symbol, title, body, payload, channel) "
            "VALUES (:uid, :aid, :at, :sym, :title, :body, "
            "        CAST(:payload AS JSONB), 'in_app')"
        ),
        {
            "uid": user_id,
            "aid": alert_id,
            "at": alert_type,
            "sym": symbol,
            "title": title,
            "body": body,
            "payload": json.dumps(payload),
        },
    )


async def insert_in_app_notification(
    conn: Executor, user_id: str, kind: str, title: str, body: str, link: Optional[str]
) -> None:
    await conn.execute(
        text(
            "INSERT INTO in_app_notifications "
            "(user_id, kind, title, body, link) "
            "VALUES (:uid, :kind, :title, :body, :link)"
        ),
        {"uid": user_id, "kind": kind, "title": title, "body": body, "link": link},
    )


async def recent_event_exists(
    conn: Executor,
    user_id: str,
    alert_type: str,
    key_field: str,
    key_value: str,
    discriminator: str,
    discriminator_field: str = "threshold",
) -> bool:
    """24h idempotency check for evaluator events. `key_field`/`discriminator_field`
    are fixed payload key names ('budget_id'+'threshold', 'goal_id'+'threshold',
    'bill_id'+'due_date'), never user input; `key_value`/`discriminator` are the
    values to match."""
    row = await conn.execute(
        text(
            "SELECT id FROM alert_events "
            "WHERE user_id = :uid AND alert_type = :at "
            "AND created_at > now() - INTERVAL '24 hours' "
            f"AND payload->>'{key_field}' = :kv "
            f"AND payload->>'{discriminator_field}' = :disc"
        ),
        {"uid": user_id, "at": alert_type, "kv": key_value, "disc": discriminator},
    )
    return row.first() is not None
