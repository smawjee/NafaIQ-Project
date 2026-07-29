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

# A watchlisted stock moving at least this % (up or down) on the day fires an
# automatic alert, without the user having created one. Deduped to once per
# user per symbol per 24h.
WATCHLIST_MOVE_PCT = 5.0
DUE_BILL_DAYS_AHEAD = 3


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


async def evaluate_due_bills() -> int:
    """Auto-alert on bills due soon, including bills imported from email.

    This is not tied to a user-created `user_alerts` row: once a bill exists in
    user_bills, the user should get a reminder close to the due date. Deduped by
    bill id + due date to one notification per 24h.
    """
    async with connect() as conn:
        bills = await repo.fetch_due_bills(conn, DUE_BILL_DAYS_AHEAD)

    triggered = 0
    for bill in bills:
        try:
            bill_id = str(bill["id"])
            due_date = str(bill["due_date"])
            async with connect() as conn:
                if await repo.recent_event_exists(
                    conn,
                    bill["user_id"],
                    "bill",
                    "bill_id",
                    bill_id,
                    due_date,
                    discriminator_field="due_date",
                ):
                    continue
            days_left = calc.bill_due_in_days(bill["due_date"])
            if days_left is None:
                continue
            when = "today" if days_left == 0 else (
                f"in {days_left} day(s)" if days_left > 0 else f"{abs(days_left)} day(s) overdue"
            )
            title = f"{bill['name']} due {when}"
            body = f"PKR {float(bill['amount']):,.2f} is due on {due_date}."
            await record_event(
                bill["user_id"],
                alert_id=None,
                alert_type="bill",
                symbol=None,
                title=title,
                body=body,
                payload={
                    "bill_id": bill_id,
                    "bill": bill["name"],
                    "amount": float(bill["amount"]),
                    "due_date": due_date,
                    "source": "due_bill_auto",
                },
            )
            triggered += 1
        except Exception:
            log.exception("due-bill evaluation failed for bill %s", bill.get("id"))
    return triggered

async def evaluate_watchlist_moves() -> int:
    """Auto-alert on big daily moves of watchlisted symbols — no user-created
    alert needed. Fires (once per user per symbol per 24h) when |change_pct| >=
    WATCHLIST_MOVE_PCT. Lands in the alerts bucket (gated by email_alerts)."""
    async with connect() as conn:
        rows = await repo.fetch_watchlist_with_snapshot(conn)

    triggered = 0
    for r in rows:
        change_pct = _num(r.get("change_pct"))
        price = _num(r.get("price"))
        if change_pct is None or abs(change_pct) < WATCHLIST_MOVE_PCT:
            continue
        user_id, symbol = r["user_id"], r["symbol"]
        try:
            async with connect() as conn:
                if await repo.recent_watchlist_event(conn, user_id, symbol):
                    continue
            direction = "up" if change_pct >= 0 else "down"
            price_str = f" to PKR {price:,.2f}" if price is not None else ""
            title = f"{symbol} {direction} {abs(change_pct):.1f}% today"
            body = (
                f"{symbol} on your watchlist moved {direction} {abs(change_pct):.1f}%"
                f"{price_str} today."
            )
            await record_event(
                user_id,
                alert_id=None,
                alert_type="stock_price",
                symbol=symbol,
                title=title,
                body=body,
                payload={"symbol": symbol, "change_pct": change_pct, "price": price,
                         "source": "watchlist"},
            )
            triggered += 1
        except Exception:
            log.exception("watchlist-move evaluation failed for %s/%s", user_id, symbol)
    return triggered


async def evaluate_all() -> dict[str, int]:
    return {
        "user_alerts": await evaluate_user_alerts(),
        "price_alerts": await evaluate_price_alerts(),
        "watchlist_moves": await evaluate_watchlist_moves(),
        "due_bills": await evaluate_due_bills(),
    }
