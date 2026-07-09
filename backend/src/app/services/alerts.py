"""Alerts service: CRUD and evaluators for price / bill / budget / goal alerts.

Business logic only — all SQL is delegated to app.repositories.alerts_repo.
Designed to be called by an external cron / scheduler; POST /api/alerts/evaluate
lets the frontend trigger a manual run for testing.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories import alerts_repo as repo
from app.repositories.base import begin, connect
from app.services import calculations as calc
from app.services.permissions import check_count_limit
from app.services.psx.prices import get_latest_price

log = logging.getLogger(__name__)


# ---------- CRUD ---------------------------------------------------------


async def list_alerts(user_id: str, alert_type: Optional[str] = None) -> list[dict[str, Any]]:
    async with connect() as conn:
        if alert_type == "price":
            return await repo.list_price_alerts(conn, user_id)
        return await repo.list_user_alerts(conn, user_id)


async def create_user_alert(
    user_id: str,
    alert_type: str,
    title: str,
    meta: Optional[dict[str, Any]] = None,
    enabled: bool = True,
) -> dict[str, Any]:
    async with begin() as conn:
        return await repo.insert_user_alert(conn, user_id, alert_type, title, meta or {}, enabled)


async def create_price_alert(
    user: dict,
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
    user_id = user["user_id"]
    async with begin() as conn:
        current = await repo.count_price_alerts(conn, user_id)
        check_count_limit(user, feature_key="max_price_alerts", current=current, label="Price alerts")
        return await repo.insert_price_alert(
            conn, user_id, symbol, condition, price, one_time, notify_push, notify_email, notes
        )


async def toggle_alert(user_id: str, alert_id: int, enabled: bool) -> Optional[dict[str, Any]]:
    async with begin() as conn:
        updated = await repo.toggle_user_alert(conn, user_id, alert_id, enabled)
    if updated is None:
        return None
    return {"id": alert_id, "enabled": enabled}


async def delete_alert(user_id: str, alert_id: int) -> bool:
    async with begin() as conn:
        return await repo.delete_user_alert(conn, user_id, alert_id)


# ---------- Events --------------------------------------------------------


async def list_alert_events(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_alert_events(conn, user_id, limit)


async def mark_event_read(user_id: str, event_id: int) -> bool:
    async with begin() as conn:
        return await repo.mark_event_read(conn, user_id, event_id)


async def _record_event(
    user_id: str,
    alert_id: Optional[int],
    alert_type: str,
    symbol: Optional[str],
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    """Persist an alert event and mirror it into the notification bell."""
    # in_app_notifications.kind uses "price_alert"; alert_events uses
    # "stock_price". Map so the CHECK constraint is satisfied.
    kind = "price_alert" if alert_type == "stock_price" else alert_type
    async with begin() as conn:
        await repo.insert_alert_event(
            conn, user_id, alert_id, alert_type, symbol, title, body, payload
        )
        await repo.insert_in_app_notification(conn, user_id, kind, title, body, None)


# ---------- Evaluators ---------------------------------------------------


async def evaluate_price_alerts() -> int:
    """Check all enabled price alerts. Return count of triggered alerts."""
    async with connect() as conn:
        alerts = await repo.fetch_enabled_price_alerts(conn)

    triggered = 0
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
        body = f"{a['symbol']} is now PKR {latest:.2f} (threshold PKR {threshold:.2f})."
        await _record_event(
            a["user_id"],
            alert_id=a["id"],
            alert_type="stock_price",
            symbol=a["symbol"],
            title=title,
            body=body,
            payload={"price": latest, "threshold": threshold, "condition": cond},
        )
        async with begin() as conn:
            await repo.mark_price_alert_triggered(conn, a["id"], disable=bool(a.get("one_time")))
        triggered += 1
    return triggered


async def evaluate_bill_reminders(days_ahead: int = 3) -> int:
    """Create reminder events for bills due within N days."""
    async with connect() as conn:
        bills = await repo.fetch_due_bills(conn, days_ahead)
    triggered = 0
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


async def evaluate_budget_alerts(thresholds: tuple[float, ...] = (80.0, 90.0, 100.0)) -> int:
    """Create budget alert events at each threshold. Only one event per
    (budget, threshold) within a 24-hour window."""
    async with connect() as conn:
        budgets = await repo.fetch_all_budgets(conn)
    triggered = 0
    for b in budgets:
        usage = calc.budget_usage(float(b["spent"]), float(b["limit_amount"]))
        for t in thresholds:
            if usage < t:
                continue
            async with connect() as conn:
                if await repo.recent_event_exists(
                    conn, b["user_id"], "budget", "budget_id", str(b["id"]), str(t)
                ):
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


async def evaluate_goal_alerts(thresholds: tuple[float, ...] = (25.0, 50.0, 75.0, 100.0)) -> int:
    async with connect() as conn:
        goals = await repo.fetch_all_goals(conn)
    triggered = 0
    for g in goals:
        progress = calc.goal_progress(float(g["saved"]), float(g["target"]))
        for t in thresholds:
            if progress < t:
                continue
            async with connect() as conn:
                if await repo.recent_event_exists(
                    conn, g["user_id"], "goal", "goal_id", str(g["id"]), str(t)
                ):
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
    return {
        "price_alerts": await evaluate_price_alerts(),
        "bill_reminders": await evaluate_bill_reminders(),
        "budget_alerts": await evaluate_budget_alerts(),
        "goal_alerts": await evaluate_goal_alerts(),
    }
