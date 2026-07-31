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
from app.schemas.alerts import PRICE_CONDITIONS
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


#: Conditions that need 52-week / average-volume aggregates from psx_ohlcv.
_STATS_CONDITIONS = frozenset({"volume_spike", "high_52w", "low_52w"})

#: How close to the 52-week extreme counts as "at" it. Requiring an exact match
#: would almost never fire: the stored extreme comes from psx_ohlcv (yesterday's
#: bar at the newest), while `latest` is a live intraday price, so the two are
#: measured at different moments and rarely land on the same paisa.
_EXTREME_TOLERANCE = 0.001  # 0.1%


def _evaluate_condition(
    cond: str,
    threshold: float,
    price_data: dict,
    stats: dict | None,
) -> tuple[bool, str, str, dict] | None:
    """Decide whether one alert fires, and describe it if so.

    Split out of the loop so each condition can be unit-tested against a plain
    dict instead of a live database, and so adding a tenth condition is a local
    change rather than another branch in a growing for-loop.

    Returns (fired, title_suffix, body, extra_payload) or None when the data
    needed for this condition is unavailable.
    """
    latest = price_data.get("price")
    if latest is None:
        return None
    latest = float(latest)

    if cond == "above":
        return (latest >= threshold, f"above PKR {threshold:,.2f}",
                f"now PKR {latest:,.2f}", {})
    if cond == "below":
        return (latest <= threshold, f"below PKR {threshold:,.2f}",
                f"now PKR {latest:,.2f}", {})

    if cond in ("cross_above", "cross_below"):
        prev = price_data.get("previous_close")
        if prev is None:
            return None
        prev = float(prev)
        if cond == "cross_above":
            return (prev < threshold <= latest, f"crossed above PKR {threshold:,.2f}",
                    f"moved from PKR {prev:,.2f} to PKR {latest:,.2f}", {"previous_close": prev})
        return (prev > threshold >= latest, f"crossed below PKR {threshold:,.2f}",
                f"moved from PKR {prev:,.2f} to PKR {latest:,.2f}", {"previous_close": prev})

    if cond in ("pct_change_above", "pct_change_below"):
        change_pct = price_data.get("change_pct")
        if change_pct is None:
            return None
        change_pct = float(change_pct)
        if cond == "pct_change_above":
            # "Moved up by at least N%". Signed, not absolute: a user asking to
            # be told about a +5% move does not want to hear about a -6% one.
            return (change_pct >= threshold, f"up {threshold:g}% or more",
                    f"is {change_pct:+.2f}% today at PKR {latest:,.2f}",
                    {"change_pct": change_pct})
        return (change_pct <= -abs(threshold), f"down {abs(threshold):g}% or more",
                f"is {change_pct:+.2f}% today at PKR {latest:,.2f}",
                {"change_pct": change_pct})

    if cond == "volume_spike":
        volume = price_data.get("volume")
        avg = (stats or {}).get("avg_volume")
        if volume is None or not avg:
            return None
        volume = float(volume)
        multiple = volume / avg
        return (multiple >= threshold, f"volume {threshold:g}x average",
                f"traded {volume:,.0f} shares — {multiple:.1f}x its "
                f"{avg:,.0f} average", {"volume": volume, "avg_volume": avg,
                                        "multiple": round(multiple, 2)})

    if cond in ("high_52w", "low_52w"):
        if not stats:
            return None
        # Guard against a thin history: a symbol with 12 bars trivially sits at
        # its own "52-week" extreme, which would fire on day one and every day
        # after. Require a meaningful window before claiming an extreme.
        if stats.get("bars", 0) < 60:
            return None
        if cond == "high_52w":
            high = stats.get("high_52w")
            if high is None:
                return None
            return (latest >= high * (1 - _EXTREME_TOLERANCE), "at a 52-week high",
                    f"hit PKR {latest:,.2f}, its highest in 52 weeks "
                    f"(prior high PKR {high:,.2f})", {"high_52w": high})
        low = stats.get("low_52w")
        if low is None:
            return None
        return (latest <= low * (1 + _EXTREME_TOLERANCE), "at a 52-week low",
                f"fell to PKR {latest:,.2f}, its lowest in 52 weeks "
                f"(prior low PKR {low:,.2f})", {"low_52w": low})

    return None


async def evaluate_price_alerts() -> int:
    """Check all enabled price_alerts rows (stock-detail page). Returns count fired."""
    async with connect() as conn:
        alerts = await repo.fetch_enabled_price_alerts(conn)
    if not alerts:
        return 0

    # One aggregate query per tick, not one per alert. Only the symbols that
    # actually have a stats-backed alert are fetched.
    stats_symbols = sorted({
        a["symbol"].upper() for a in alerts if a["condition"] in _STATS_CONDITIONS
    })
    symbol_stats: dict[str, dict] = {}
    if stats_symbols:
        try:
            async with connect() as conn:
                symbol_stats = await repo.fetch_symbol_stats(conn, stats_symbols)
        except Exception:
            # Degrade to evaluating the price-only conditions rather than
            # skipping the whole tick.
            log.exception("symbol stats lookup failed in evaluator")

    triggered = 0
    for a in alerts:
        try:
            price_data = await get_latest_price(a["symbol"], allow_external=False)
        except Exception:
            log.exception("price lookup failed in evaluator")
            continue
        if not price_data or price_data.get("price") is None:
            continue

        cond = a["condition"]
        threshold = float(a["price"])
        try:
            outcome = _evaluate_condition(
                cond, threshold, price_data, symbol_stats.get(a["symbol"].upper())
            )
        except Exception:
            log.exception("condition evaluation failed for alert %s", a.get("id"))
            continue
        if outcome is None:
            continue
        fired, phrase, detail, extra = outcome
        if not fired:
            continue

        title = f"{a['symbol']} {phrase}"
        body = f"{a['symbol']} {detail}."
        await record_event(
            a["user_id"],
            alert_id=a["id"],
            alert_type="stock_price",
            symbol=a["symbol"],
            title=title,
            body=body,
            payload={
                "price": float(price_data["price"]),
                "threshold": threshold,
                "condition": cond,
                **extra,
            },
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
    """LEGACY meta-driven stock alert (`user_alerts` rows with type='stock_price').

    The product has two ways a stock alert can exist: the `price_alerts` table
    (what the UI and the assistant write today, all nine conditions) and these
    meta rows. Nothing has created a meta row since the alerts screen was moved
    onto `price_alerts`; two remain in production, both `HBL above`.

    This used to carry its OWN comparison logic supporting only above/below, so
    the same user intent behaved differently depending on which path created it.
    It now delegates to `_evaluate_condition` — one implementation, one set of
    semantics — and reads `condition` with a fall back to the older `direction`
    key so the surviving rows keep working.

    Aggregate-backed conditions (volume_spike, high_52w, low_52w) are not offered
    here: they need `fetch_symbol_stats`, this path evaluates one alert at a time
    with no batching, and nothing can create such a row anyway. They return None
    (treated as "unavailable"), not a wrong answer.
    """
    symbol = str(meta.get("symbol", "")).upper()
    target = _num(meta.get("price"))
    # `condition` is the current spelling; `direction` is what the pre-existing
    # rows use.
    cond = str(meta.get("condition") or meta.get("direction") or "").lower()
    if not symbol or target is None or cond not in PRICE_CONDITIONS:
        return None
    try:
        pd = await get_latest_price(symbol, allow_external=False)
    except Exception:
        return None
    if not pd or pd.get("price") is None:
        return None

    outcome = _evaluate_condition(cond, float(target), pd, None)
    if outcome is None:
        return None
    fired, phrase, detail, extra = outcome
    if not fired:
        return None

    title = f"{symbol} {phrase}"
    body = f"{symbol} {detail}."
    payload = {
        "symbol": symbol,
        "price": float(pd["price"]),
        "target": float(target),
        "condition": cond,
        **extra,
    }
    return title, body, payload, symbol


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
                # Pass the type: alert_id alone is ambiguous across user_alerts
                # and price_alerts (see recent_event_for_alert).
                if await repo.recent_event_for_alert(conn, a["id"], a["type"]):
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
