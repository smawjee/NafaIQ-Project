"""Alert evaluators for price / bill / budget / goal alerts.

Designed to be called by an external cron / scheduler; POST /api/alerts/evaluate
lets the frontend trigger a manual run for testing.
"""
from __future__ import annotations

import logging

from app.repositories import alerts as repo
from app.repositories.base import begin, connect
from app.services import calculations as calc
from app.services.alerts.events import record_event
from app.services.psx.prices import get_latest_price

log = logging.getLogger(__name__)


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
        await record_event(
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
    """Create reminder events for bills due within N days. Only one reminder per
    (bill, due_date) within a 24-hour window (the job runs every 60s)."""
    async with connect() as conn:
        bills = await repo.fetch_due_bills(conn, days_ahead)
    triggered = 0
    for b in bills:
        due_date = b["due_date"]
        async with connect() as conn:
            if await repo.recent_event_exists(
                conn, b["user_id"], "bill", "bill_id", str(b["id"]), str(due_date),
                discriminator_field="due_date",
            ):
                continue
        days = calc.bill_due_in_days(due_date)
        await record_event(
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
            await record_event(
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
            await record_event(
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
