"""Alerts data access: price alerts, app alerts, alert events, and the reads
that evaluators run over. All alerts-domain SQL lives here.

Functions take an executor and return plain Python data. Evaluator business
logic (condition checks, thresholds, idempotency decisions) stays in the
service.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

Executor = Any


def _jsonb(value: Any) -> dict[str, Any]:
    """JSONB comes back as dict (asyncpg) or str (other drivers); accept both."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _price_alert(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "type": "stock_price",
        "symbol": r["symbol"],
        "condition": r["condition"],
        "price": float(r["price"]),
        "enabled": r["enabled"],
        "triggered_at": str(r["triggered_at"]) if r["triggered_at"] else None,
        "last_triggered_at": str(r["last_triggered_at"]) if r["last_triggered_at"] else None,
        "one_time": r["one_time"],
        "notify_push": r["notify_push"],
        "notify_email": r["notify_email"],
        "notes": r["notes"],
        "created_at": str(r["created_at"]),
    }


def _user_alert(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "type": r["type"],
        "title": r["title"],
        "meta": _jsonb(r["meta"]),
        "enabled": r["enabled"],
        "triggered_at": str(r["triggered_at"]) if r["triggered_at"] else None,
        "created_at": str(r["created_at"]),
    }


# ---------- price alerts ----------


async def list_price_alerts(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, symbol, condition, price, enabled, "
            "triggered_at, created_at, one_time, last_triggered_at, "
            "notify_push, notify_email, notes "
            "FROM price_alerts WHERE user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    return [_price_alert(r) for r in rows.mappings().all()]


async def insert_price_alert(
    conn: Executor,
    user_id: str,
    symbol: str,
    condition: str,
    price: float,
    one_time: bool,
    notify_push: bool,
    notify_email: bool,
    notes: Optional[str],
) -> dict[str, Any]:
    row = await conn.execute(
        text(
            "INSERT INTO price_alerts "
            "(user_id, symbol, condition, price, enabled, one_time, "
            " notify_push, notify_email, notes) "
            "VALUES (:uid, :sym, :cond, :price, true, :ot, :np, :ne, :notes) "
            "RETURNING id, user_id, symbol, condition, price, enabled, "
            "          triggered_at, created_at, one_time, last_triggered_at, "
            "          notify_push, notify_email, notes"
        ),
        {
            "uid": user_id,
            "sym": symbol.upper(),
            "cond": condition,
            "price": price,
            "ot": one_time,
            "np": notify_push,
            "ne": notify_email,
            "notes": notes,
        },
    )
    return _price_alert(row.mappings().first())


async def count_price_alerts(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text("SELECT COUNT(*) FROM price_alerts WHERE user_id = :uid"),
        {"uid": user_id},
    )
    return int(result.scalar() or 0)


async def fetch_enabled_price_alerts(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, symbol, condition, price, one_time, "
            "last_triggered_at, notify_push, notify_email "
            "FROM price_alerts WHERE enabled = TRUE"
        )
    )
    return [dict(r) for r in rows.mappings().all()]


async def mark_price_alert_triggered(
    conn: Executor, alert_id: int, disable: bool
) -> None:
    sql = (
        "UPDATE price_alerts SET last_triggered_at = now(), "
        "triggered_at = COALESCE(triggered_at, now())"
    )
    if disable:
        sql += ", enabled = FALSE"
    sql += " WHERE id = :id"
    await conn.execute(text(sql), {"id": alert_id})


# ---------- app alerts (bill / budget / goal / stock_price) ----------


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


# ---------- events ----------


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
            "payload": _jsonb(r["payload"]),
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
    conn: Executor, user_id: str, alert_type: str, key_field: str, key_value: str, threshold: str
) -> bool:
    """24h idempotency check for budget/goal threshold events. `key_field` is a
    fixed payload key name ('budget_id' or 'goal_id'), not user input."""
    row = await conn.execute(
        text(
            "SELECT id FROM alert_events "
            "WHERE user_id = :uid AND alert_type = :at "
            "AND created_at > now() - INTERVAL '24 hours' "
            f"AND payload->>'{key_field}' = :kv "
            "AND payload->>'threshold' = :th"
        ),
        {"uid": user_id, "at": alert_type, "kv": key_value, "th": threshold},
    )
    return row.first() is not None


# ---------- evaluator source reads ----------


async def fetch_due_bills(conn: Executor, days_ahead: int) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT id, user_id, name, amount, due_date "
            "FROM user_bills "
            "WHERE status IN ('UPCOMING','DUE_SOON','DUE SOON') "
            "AND due_date IS NOT NULL "
            "AND due_date <= CURRENT_DATE + (:n * INTERVAL '1 day') "
            "AND due_date >= CURRENT_DATE - INTERVAL '7 days'"
        ),
        {"n": int(days_ahead)},
    )
    return [dict(r) for r in rows.mappings().all()]


async def fetch_all_budgets(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text(
            "SELECT b.id, b.user_id, b.category, b.spent, b.limit_amount, "
            "b.period, b.tip FROM user_budgets b"
        )
    )
    return [dict(r) for r in rows.mappings().all()]


async def fetch_all_goals(conn: Executor) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text("SELECT id, user_id, name, target, saved FROM user_goals")
    )
    return [dict(r) for r in rows.mappings().all()]
