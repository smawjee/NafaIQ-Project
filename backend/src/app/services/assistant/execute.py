"""ActionDraft -> the existing domain services.

This is the ONLY place an assistant-originated write happens, and it happens
only on an explicit second request from the client, after the user has seen the
draft. The chat loop never calls anything here.

Two rules shape the module:

1. **Nothing is trusted.** The draft arrives as JSON from a client, so every
   handler re-validates it through the same Pydantic request model the REST API
   uses and calls the same service function. There is no assistant-specific
   write path that could drift from — or skip a guard enforced by — the normal
   one: `check_count_limit`, `require_known_symbol`, `canonical_category` and
   the oversell check all still apply, because they live in the services being
   called.

2. **Resolution happens here, not in the model.** A goal NAME becomes a goal id,
   a sole portfolio becomes a portfolio_id, "food" becomes "Food & Dining", and
   "Meezan card" becomes "Meezan Debit" — all against the user's real rows.
   Letting the model emit ids would mean trusting it to know them.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Coroutine

from fastapi import HTTPException

from app.schemas.alerts import PriceAlertCreate
from app.schemas.finance import BillCreate, GoalCreate, TransactionCreate
from app.services.ai.observability import observe
from app.schemas.portfolio import HoldingCreate, StockTransactionCreate, WatchlistCreate
from app.services.assistant.tools import (
    BY_NAME,
    Tool,
    apply_defaults,
    is_placeholder,
    missing_fields,
)
from app.services.finance.categories import canonical_category
from app.services.finance.payment_methods import canonical_payment_method

finance_bills = importlib.import_module("app.services.finance.bills")
finance_goals = importlib.import_module("app.services.finance.goals")
finance_transactions = importlib.import_module("app.services.finance.transactions")
app_alerts = importlib.import_module("app.services.alerts.app_alerts")
price_alerts = importlib.import_module("app.services.alerts.price_alerts")
portfolio_holdings = importlib.import_module("app.services.portfolio.holdings")
portfolio_trades = importlib.import_module("app.services.portfolio.trades")
portfolio_watchlist = importlib.import_module("app.services.portfolio.watchlist")

Handler = Callable[[dict, dict[str, Any]], Coroutine[Any, Any, Any]]


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_goal(user_id: str, name: str | None) -> dict[str, Any]:
    """A goal name to the user's actual goal row.

    Matched case- and whitespace-insensitively because the name makes a round
    trip through speech recognition and the model before it gets here, and
    "hajj fund" must still find "Hajj Fund".
    """
    if not name or not name.strip():
        raise HTTPException(400, "Which goal? Please name one of your savings goals.")
    goals = await finance_goals.list_goals(user_id)
    wanted = name.strip().casefold()
    for goal in goals:
        if str(goal.get("name", "")).strip().casefold() == wanted:
            return goal
    known = ", ".join(g["name"] for g in goals) or "you have no goals yet"
    raise HTTPException(404, f"No goal called '{name}'. Your goals: {known}")


async def _resolve_portfolio(user_id: str, portfolio_id: int | None) -> int:
    """An explicit portfolio id (ownership-checked) or the user's only one.

    Reuses resolve_owned_portfolio, so the ownership check is the same one the
    REST API performs — an id belonging to someone else 404s here too.
    """
    resolved = await portfolio_holdings.resolve_owned_portfolio(user_id, portfolio_id)
    if resolved is None:
        raise HTTPException(
            400, "You don't have a portfolio yet. Create one before adding holdings."
        )
    return resolved


def _clean_transaction_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalise the two free-text fields onto their controlled vocabularies.

    Category matters most: budgets join transactions on the exact category
    string, so an off-vocabulary spelling silently never moves the user's
    budget. `source` is not a join key, so an unresolvable payment method is
    left as the model wrote it rather than dropped — better a slightly odd
    label than a lost detail.
    """
    out = dict(args)
    if out.get("category"):
        out["category"] = canonical_category(out["category"])
    if out.get("source"):
        out["source"] = canonical_payment_method(out["source"]) or out["source"]
    return out


# ---------------------------------------------------------------------------
# Handlers — one per write tool
# ---------------------------------------------------------------------------


async def _add_transaction(user: dict, args: dict[str, Any]) -> Any:
    body = TransactionCreate(**_strip_none(_clean_transaction_args(args)))
    return await finance_transactions.create_transaction(user["user_id"], body)


async def _add_bill(user: dict, args: dict[str, Any]) -> Any:
    body = BillCreate(**_strip_none(args))
    return await finance_bills.create_bill(user["user_id"], body, user)


async def _add_goal(user: dict, args: dict[str, Any]) -> Any:
    body = GoalCreate(**_strip_none(args))
    return await finance_goals.create_goal(user["user_id"], body, user)


async def _contribute_to_goal(user: dict, args: dict[str, Any]) -> Any:
    goal = await _resolve_goal(user["user_id"], args.get("goal_name"))
    amount = float(args.get("amount") or 0)
    return await finance_goals.contribute_goal(user["user_id"], goal["id"], amount)


async def _add_goal_alert(user: dict, args: dict[str, Any]) -> Any:
    """Create the goal-milestone alert the evaluator already understands.

    The meta shape is dictated by services/alerts/evaluator.py::_eval_goal,
    which matches on the goal NAME and compares progress against `milestone`.
    We resolve the name against the user's real goals first so the alert cannot
    be created against a goal that does not exist — the evaluator would simply
    never fire it, which looks identical to a broken alert.
    """
    goal = await _resolve_goal(user["user_id"], args.get("goal_name"))
    milestone = float(args.get("milestone") or 0)
    if not 0 < milestone <= 100:
        raise HTTPException(400, "Milestone must be a percentage between 1 and 100.")
    return await app_alerts.create_user_alert(
        user["user_id"],
        "goal",
        f"{goal['name']} {milestone:g}% reached",
        {"goal": goal["name"], "milestone": milestone},
    )


async def _add_price_alert(user: dict, args: dict[str, Any]) -> Any:
    body = PriceAlertCreate(**_strip_none(args))
    return await price_alerts.create_price_alert(
        user, body.symbol, body.condition, body.price, notes=body.notes
    )


async def _add_holding(user: dict, args: dict[str, Any]) -> Any:
    portfolio_id = await _resolve_portfolio(user["user_id"], args.get("portfolio_id"))
    body = HoldingCreate(**_strip_none({k: v for k, v in args.items() if k != "portfolio_id"}))
    return await portfolio_holdings.add_holding(user, portfolio_id, body)


async def _record_trade(user: dict, args: dict[str, Any]) -> Any:
    portfolio_id = await _resolve_portfolio(user["user_id"], args.get("portfolio_id"))
    body = StockTransactionCreate(**_strip_none({**args, "portfolio_id": portfolio_id}))
    return await portfolio_trades.create_stock_transaction(user, body)


async def _add_to_watchlist(user: dict, args: dict[str, Any]) -> Any:
    body = WatchlistCreate(**_strip_none(args))
    return await portfolio_watchlist.add_to_watchlist(user, body.symbol)


async def _remove_from_watchlist(user: dict, args: dict[str, Any]) -> Any:
    body = WatchlistCreate(**_strip_none(args))
    return await portfolio_watchlist.remove_from_watchlist(user["user_id"], body.symbol)


HANDLERS: dict[str, Handler] = {
    "add_transaction": _add_transaction,
    "add_bill": _add_bill,
    "add_goal": _add_goal,
    "contribute_to_goal": _contribute_to_goal,
    "add_goal_alert": _add_goal_alert,
    "add_price_alert": _add_price_alert,
    "add_holding": _add_holding,
    "record_trade": _record_trade,
    "add_to_watchlist": _add_to_watchlist,
    "remove_from_watchlist": _remove_from_watchlist,
}


def _strip_none(args: dict[str, Any]) -> dict[str, Any]:
    """Drop unset keys so the request model's own defaults apply.

    Passing source=None explicitly would override TransactionCreate's
    `source: str = "manual"` with None and fail validation, even though the
    field was simply never mentioned.
    """
    return {k: v for k, v in args.items() if v is not None}


# capture_input=False: the first positional arg is the user dict (JWT-derived
# claims), which must not land in a trace. The action's content is already
# visible in the chat turn's draft event.
@observe(name="assistant_execute", capture_input=False, capture_output=False)
async def execute_draft(user: dict, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one confirmed draft. Raises HTTPException on anything invalid.

    Returns the created entity plus the query keys the client must invalidate,
    so the UI refreshes exactly the surfaces this write touched rather than
    everything.
    """
    tool: Tool | None = BY_NAME.get(tool_name)
    if tool is None or tool.kind != "write":
        raise HTTPException(400, f"'{tool_name}' is not an executable action")

    # Strip filler here too, not just in the agent: /execute accepts a draft
    # posted straight from a client, which may never have passed through the
    # chat loop at all.
    filled = apply_defaults(
        tool, {k: (None if is_placeholder(v) else v) for k, v in args.items()}
    )
    gaps = missing_fields(tool, filled)
    if gaps:
        # Reachable when a client posts a draft it never finished collecting.
        # A clean 400 naming the gaps beats a 422 from deep inside Pydantic.
        raise HTTPException(400, f"Missing required information: {', '.join(gaps)}")

    result = await HANDLERS[tool_name](user, filled)
    return {"ok": True, "action": tool_name, "entity": result, "invalidate": list(tool.invalidate)}
