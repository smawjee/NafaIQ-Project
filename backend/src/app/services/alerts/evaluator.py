"""Alert evaluators.

Two sources, both user-scoped:
- app-created alerts in `user_alerts` (bill / budget / goal / stock_price):
  meta-driven — a notification fires only for the exact condition the user
  configured (e.g. "Groceries at 80%"). This is the opt-in source, so a user
  who created no alerts is never notified (no global firing).
- `price_alerts` rows created from the stock-detail page.

Delivery (in-app / email) respects the user's notification preferences — see
app.services.alerts.events.record_event.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories import alerts as repo
from app.repositories.base import begin, connect
from app.services import calculations as calc
from app.services.alerts.events import record_event
from app.services.psx.prices import get_latest_price

log = logging.getLogger(__name__)


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timing_days(timing: str) -> int:
    """'1 day before' / '3 days before' / '7 days before' -> the number."""
    for tok in str(timing).split():
        if tok.isdigit():
            return int(tok)
    return 3


async def evaluate_price_alerts() -> int:
    """Check all enabled price_alerts rows (stock-detail page). Returns count fired."""
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


# ---------------------------------------------------------------------------
# Per-type meta evaluators — return (title, body, payload, symbol) if the
# alert's configured condition is currently met, else None.
# ---------------------------------------------------------------------------


async def _eval_stock_price(uid: str, meta: dict) -> Optional[tuple]:
    symbol = str(meta.get("symbol", "")).upper()
    target = _num(meta.get("price"))
    direction = str(meta.get("direction", "")).lower()
    if not symbol or target is None or direction not in ("above", "below"):
        return None
    try:
        pd = await get_latest_price(symbol, allow_external=False)
    except Exception:
        return None
    if not pd or pd.get("price") is None:
        return None
    latest = float(pd["price"])
    if not ((direction == "above" and latest >= target) or (direction == "below" and latest <= target)):
        return None
    title = f"{symbol} {direction} PKR {target:.2f}"
    body = f"{symbol} is now PKR {latest:.2f} ({direction} your PKR {target:.2f} alert)."
    return title, body, {"symbol": symbol, "price": latest, "target": target, "direction": direction}, symbol


async def _eval_budget(uid: str, meta: dict) -> Optional[tuple]:
    category = str(meta.get("category", ""))
    threshold = _num(meta.get("threshold"))
    if not category or threshold is None:
        return None
    async with connect() as conn:
        b = await repo.get_budget_by_category(conn, uid, category)
    if not b:
        return None
    usage = calc.budget_usage(b["spent"], b["limit_amount"])
    if usage < threshold:
        return None
    title = f"{category} {threshold:.0f}% of budget used"
    body = (
        f"Spending on {category} is PKR {b['spent']:.2f} of "
        f"PKR {b['limit_amount']:.2f} ({usage:.1f}%)."
    )
    return title, body, {"category": category, "usage_pct": usage, "threshold": threshold}, None


async def _eval_goal(uid: str, meta: dict) -> Optional[tuple]:
    name = str(meta.get("goal", ""))
    milestone = _num(meta.get("milestone"))
    if not name or milestone is None:
        return None
    async with connect() as conn:
        g = await repo.get_goal_by_name(conn, uid, name)
    if not g:
        return None
    progress = calc.goal_progress(g["saved"], g["target"])
    if progress < milestone:
        return None
    title = f"{name} {milestone:.0f}% reached"
    body = (
        f"You've saved PKR {g['saved']:.2f} of PKR {g['target']:.2f} "
        f"({progress:.1f}%) for {name}."
    )
    return title, body, {"goal": name, "progress_pct": progress, "milestone": milestone}, None


async def _eval_bill(uid: str, meta: dict) -> Optional[tuple]:
    name = str(meta.get("bill", ""))
    if not name:
        return None
    days_ahead = _timing_days(meta.get("timing", "3 days before"))
    async with connect() as conn:
        bill = await repo.get_bill_by_name(conn, uid, name)
    if not bill or bill["status"] == "PAID" or bill["due_date"] is None:
        return None
    days_left = calc.bill_due_in_days(bill["due_date"])
    if days_left is None or days_left > days_ahead:
        return None
    when = f"in {days_left} day(s)" if days_left >= 0 else f"{abs(days_left)} day(s) ago"
    title = f"{name} due {when}"
    body = f"Bill '{name}' for PKR {bill['amount']:.2f} is due on {bill['due_date']}."
    return title, body, {"bill": name, "amount": bill["amount"], "due_date": str(bill["due_date"])}, None


_EVALUATORS = {
    "stock_price": _eval_stock_price,
    "budget": _eval_budget,
    "goal": _eval_goal,
    "bill": _eval_bill,
}


async def evaluate_user_alerts() -> int:
    """Evaluate every enabled app-created alert against its own configured
    condition. Fires (once per alert per 24h) only for the user who owns it."""
    async with connect() as conn:
        alerts = await repo.fetch_enabled_user_alerts(conn)

    triggered = 0
    seen: set[int] = set()
    for a in alerts:
        # Never process the same alert twice in one pass.
        if a["id"] in seen:
            continue
        seen.add(a["id"])
        # Isolate each alert: a transient error on one must not skip the rest.
        try:
            evaluator = _EVALUATORS.get(a["type"])
            if evaluator is None:
                continue
            result = await evaluator(a["user_id"], a["meta"] or {})
            if result is None:
                continue
            # One notification per alert per 24h window.
            async with connect() as conn:
                if await repo.recent_event_for_alert(conn, a["id"]):
                    continue
            title, body, payload, symbol = result
            await record_event(
                a["user_id"],
                alert_id=a["id"],
                alert_type=a["type"],
                symbol=symbol,
                title=title,
                body=body,
                payload={**payload, "alert_id": a["id"]},
            )
            triggered += 1
        except Exception:
            log.exception("user-alert evaluation failed for alert %s", a.get("id"))
    return triggered


async def evaluate_all() -> dict[str, int]:
    return {
        "user_alerts": await evaluate_user_alerts(),
        "price_alerts": await evaluate_price_alerts(),
    }
