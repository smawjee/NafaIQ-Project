"""Alerts service: CRUD and evaluators for price / bill / budget / goal alerts.

Designed to be called by an external cron / scheduler in the future. The
endpoint POST /api/alerts/evaluate lets the frontend trigger a manual run
for testing.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text

from app.db.sqlalchemy import get_session_factory
from app.services import calculations as calc
from app.services.psx.prices import get_latest_price


def _jsonb(value: Any) -> dict[str, Any]:
    """JSONB columns come back as dicts from asyncpg but as strings from other
    drivers; accept both."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}

log = logging.getLogger(__name__)


# ---------- CRUD ---------------------------------------------------------


async def list_alerts(
    user_id: str, alert_type: Optional[str] = None
) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        if alert_type == "price":
            rows = await session.execute(
                text(
                    "SELECT id, user_id, symbol, condition, price, enabled, "
                    "triggered_at, created_at, one_time, last_triggered_at, "
                    "notify_push, notify_email, notes "
                    "FROM price_alerts WHERE user_id = :uid "
                    "ORDER BY created_at DESC"
                ),
                {"uid": user_id},
            )
            return [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "type": "stock_price",
                    "symbol": r["symbol"],
                    "condition": r["condition"],
                    "price": float(r["price"]),
                    "enabled": r["enabled"],
                    "triggered_at": (
                        str(r["triggered_at"]) if r["triggered_at"] else None
                    ),
                    "last_triggered_at": (
                        str(r["last_triggered_at"])
                        if r["last_triggered_at"]
                        else None
                    ),
                    "one_time": r["one_time"],
                    "notify_push": r["notify_push"],
                    "notify_email": r["notify_email"],
                    "notes": r["notes"],
                    "created_at": str(r["created_at"]),
                }
                for r in rows.mappings().all()
            ]
        rows = await session.execute(
            text(
                "SELECT id, user_id, type, title, meta, enabled, "
                "triggered_at, created_at "
                "FROM user_alerts WHERE user_id = :uid "
                "ORDER BY created_at DESC"
            ),
            {"uid": user_id},
        )
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "type": r["type"],
                "title": r["title"],
                "meta": _jsonb(r["meta"]),
                "enabled": r["enabled"],
                "triggered_at": (
                    str(r["triggered_at"]) if r["triggered_at"] else None
                ),
                "created_at": str(r["created_at"]),
            }
            for r in rows.mappings().all()
        ]


async def create_user_alert(
    user_id: str,
    alert_type: str,
    title: str,
    meta: Optional[dict[str, Any]] = None,
    enabled: bool = True,
) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
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
        r = row.mappings().first()
        await session.commit()
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "type": r["type"],
        "title": r["title"],
        "meta": _jsonb(r["meta"]),
        "enabled": r["enabled"],
        "triggered_at": None,
        "created_at": str(r["created_at"]),
    }


async def create_price_alert(
    user_id: str,
    symbol: str,
    condition: str,
    price: float,
    *,
    one_time: bool = True,
    notify_push: bool = False,
    notify_email: bool = True,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    if condition not in ("above", "below", "cross_above", "cross_below"):
        raise ValueError("invalid condition")
    if price < 0:
        raise ValueError("price must be >= 0")
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
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
        r = row.mappings().first()
        await session.commit()
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "symbol": r["symbol"],
        "condition": r["condition"],
        "price": float(r["price"]),
        "enabled": r["enabled"],
        "triggered_at": None,
        "last_triggered_at": None,
        "one_time": r["one_time"],
        "notify_push": r["notify_push"],
        "notify_email": r["notify_email"],
        "notes": r["notes"],
        "created_at": str(r["created_at"]),
    }


async def toggle_alert(
    user_id: str, alert_id: int, enabled: bool
) -> Optional[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
            text(
                "UPDATE user_alerts SET enabled = :en "
                "WHERE id = :id AND user_id = :uid RETURNING id"
            ),
            {"id": alert_id, "uid": user_id, "en": enabled},
        )
        r = row.first()
        await session.commit()
    if not r:
        return None
    return {"id": alert_id, "enabled": enabled}


async def delete_alert(user_id: str, alert_id: int) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
            text(
                "DELETE FROM user_alerts WHERE id = :id AND user_id = :uid "
                "RETURNING id"
            ),
            {"id": alert_id, "uid": user_id},
        )
        r = row.first()
        await session.commit()
    return r is not None


# ---------- Events --------------------------------------------------------


async def list_alert_events(
    user_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, alert_id, alert_type, symbol, title, body, "
                "payload, channel, delivered_at, read_at, created_at "
                "FROM alert_events WHERE user_id = :uid "
                "ORDER BY created_at DESC LIMIT :lim"
            ),
            {"uid": user_id, "lim": max(1, min(limit, 500))},
        )
        out: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            payload = _jsonb(r["payload"])
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "alert_id": r["alert_id"],
                    "alert_type": r["alert_type"],
                    "symbol": r["symbol"],
                    "title": r["title"],
                    "body": r["body"],
                    "payload": payload,
                    "channel": r["channel"],
                    "delivered_at": (
                        str(r["delivered_at"]) if r["delivered_at"] else None
                    ),
                    "read_at": str(r["read_at"]) if r["read_at"] else None,
                    "created_at": str(r["created_at"]),
                }
            )
    return out


async def mark_event_read(user_id: str, event_id: int) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.execute(
            text(
                "UPDATE alert_events SET read_at = now() "
                "WHERE id = :id AND user_id = :uid AND read_at IS NULL "
                "RETURNING id"
            ),
            {"id": event_id, "uid": user_id},
        )
        r = row.first()
        await session.commit()
    return r is not None


async def _record_event(
    user_id: str,
    alert_id: Optional[int],
    alert_type: str,
    symbol: Optional[str],
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
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
        # also insert into in_app_notifications so the existing notification
        # bell picks it up
        await session.execute(
            text(
                "INSERT INTO in_app_notifications "
                "(user_id, kind, title, body, link) "
                "VALUES (:uid, :kind, :title, :body, :link)"
            ),
            {
                "uid": user_id,
                # in_app_notifications.kind uses "price_alert"; alert_events uses
                # "stock_price". Map so the CHECK constraint is satisfied.
                "kind": "price_alert" if alert_type == "stock_price" else alert_type,
                "title": title,
                "body": body,
                "link": None,
            },
        )
        await session.commit()


# ---------- Evaluators ---------------------------------------------------


async def evaluate_price_alerts() -> int:
    """Check all enabled price alerts. Return count of triggered alerts."""
    factory = get_session_factory()
    triggered = 0
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, symbol, condition, price, one_time, "
                "last_triggered_at, notify_push, notify_email "
                "FROM price_alerts WHERE enabled = TRUE"
            )
        )
        alerts = [dict(r) for r in rows.mappings().all()]

    for a in alerts:
        try:
            price_data = await get_latest_price(a["symbol"], allow_external=False)
        except Exception:
            log.exception("price lookup failed in evaluator")
            continue
        if not price_data or price_data.get("price") is None:
            continue
        latest = float(price_data["price"])
        threshold = float(a["price"])
        cond = a["condition"]
        is_cross = cond in ("cross_above", "cross_below")
        fired = False
        if cond == "above" and latest >= threshold:
            fired = True
        elif cond == "below" and latest <= threshold:
            fired = True
        elif cond == "cross_above":
            prev = price_data.get("previous_close")
            if prev is not None and prev < threshold <= latest:
                fired = True
        elif cond == "cross_below":
            prev = price_data.get("previous_close")
            if prev is not None and prev > threshold >= latest:
                fired = True
        if not fired:
            continue
        title = f"{a['symbol']} {cond.replace('_', ' ')} PKR {threshold:.2f}"
        body = (
            f"{a['symbol']} is now PKR {latest:.2f} (threshold PKR {threshold:.2f})."
        )
        await _record_event(
            a["user_id"],
            alert_id=a["id"],
            alert_type="stock_price",
            symbol=a["symbol"],
            title=title,
            body=body,
            payload={"price": latest, "threshold": threshold, "condition": cond},
        )
        factory = get_session_factory()
        async with factory() as session:
            update_sql = (
                "UPDATE price_alerts SET last_triggered_at = now(), "
                "triggered_at = COALESCE(triggered_at, now())"
            )
            params: dict[str, Any] = {"id": a["id"]}
            if a.get("one_time"):
                update_sql += ", enabled = FALSE"
            update_sql += " WHERE id = :id"
            await session.execute(text(update_sql), params)
            await session.commit()
        triggered += 1
    return triggered


async def evaluate_bill_reminders(days_ahead: int = 3) -> int:
    """Create reminder events for bills due within N days."""
    factory = get_session_factory()
    triggered = 0
    async with factory() as session:
        rows = await session.execute(
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
        bills = [dict(r) for r in rows.mappings().all()]
    for b in bills:
        due_date = b["due_date"]
        days = calc.bill_due_in_days(due_date)
        await _record_event(
            b["user_id"],
            alert_id=None,
            alert_type="bill",
            symbol=None,
            title=f"{b['name']} due in {days if days is not None else 'N/A'} day(s)",
            body=f"Bill '{b['name']}' for PKR {float(b['amount']):.2f} is due on {due_date}.",
            payload={
                "bill_id": b["id"],
                "amount": float(b["amount"]),
                "due_date": str(due_date),
            },
        )
        triggered += 1
    return triggered


async def evaluate_budget_alerts(
    thresholds: tuple[float, ...] = (80.0, 90.0, 100.0)
) -> int:
    """Create budget alert events at each threshold.

    Idempotency: only one event per (budget, threshold) is created within
    a 24-hour window.
    """
    factory = get_session_factory()
    triggered = 0
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT b.id, b.user_id, b.category, b.spent, b.limit_amount, "
                "b.period, b.tip "
                "FROM user_budgets b"
            )
        )
        budgets = [dict(r) for r in rows.mappings().all()]
    for b in budgets:
        usage = calc.budget_usage(float(b["spent"]), float(b["limit_amount"]))
        for t in thresholds:
            if usage < t:
                continue
            # 24h idempotency check
            async with factory() as session:
                recent = await session.execute(
                    text(
                        "SELECT id FROM alert_events "
                        "WHERE user_id = :uid AND alert_type = 'budget' "
                        "AND created_at > now() - INTERVAL '24 hours' "
                        "AND payload->>'budget_id' = :bid "
                        "AND payload->>'threshold' = :th"
                    ),
                    {
                        "uid": b["user_id"],
                        "bid": str(b["id"]),
                        "th": str(t),
                    },
                )
                if recent.first():
                    continue
            title = f"{b['category']} {t:.0f}% of budget used"
            body = (
                f"Spending on {b['category']} is PKR {float(b['spent']):.2f} "
                f"of PKR {float(b['limit_amount']):.2f} ({usage:.1f}%)."
            )
            await _record_event(
                b["user_id"],
                alert_id=None,
                alert_type="budget",
                symbol=None,
                title=title,
                body=body,
                payload={
                    "budget_id": b["id"],
                    "category": b["category"],
                    "usage_pct": usage,
                    "threshold": t,
                },
            )
            triggered += 1
    return triggered


async def evaluate_goal_alerts(
    thresholds: tuple[float, ...] = (25.0, 50.0, 75.0, 100.0)
) -> int:
    factory = get_session_factory()
    triggered = 0
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, user_id, name, target, saved "
                "FROM user_goals"
            )
        )
        goals = [dict(r) for r in rows.mappings().all()]
    for g in goals:
        progress = calc.goal_progress(float(g["saved"]), float(g["target"]))
        for t in thresholds:
            if progress < t:
                continue
            async with factory() as session:
                recent = await session.execute(
                    text(
                        "SELECT id FROM alert_events "
                        "WHERE user_id = :uid AND alert_type = 'goal' "
                        "AND created_at > now() - INTERVAL '24 hours' "
                        "AND payload->>'goal_id' = :gid "
                        "AND payload->>'threshold' = :th"
                    ),
                    {"uid": g["user_id"], "gid": str(g["id"]), "th": str(t)},
                )
                if recent.first():
                    continue
            title = f"{g['name']} {t:.0f}% reached"
            body = (
                f"You have saved PKR {float(g['saved']):.2f} of "
                f"PKR {float(g['target']):.2f} ({progress:.1f}%) for {g['name']}."
            )
            await _record_event(
                g["user_id"],
                alert_id=None,
                alert_type="goal",
                symbol=None,
                title=title,
                body=body,
                payload={
                    "goal_id": g["id"],
                    "goal_name": g["name"],
                    "progress_pct": progress,
                    "threshold": t,
                },
            )
            triggered += 1
    return triggered


async def evaluate_all() -> dict[str, int]:
    p = await evaluate_price_alerts()
    b = await evaluate_bill_reminders()
    bu = await evaluate_budget_alerts()
    g = await evaluate_goal_alerts()
    return {"price_alerts": p, "bill_reminders": b, "budget_alerts": bu, "goal_alerts": g}
