"""READ tool handlers — the only numbers the model is ever allowed to say.

Every function here returns values ALREADY COMPUTED by an existing service or
repository. The model's job is to narrate them, never to derive them: it does
not add up transactions, work out a savings rate, or convert a percentage. This
is the cheap half of what services/ai/verify.py does for reports — reports have
to verify numbers after the fact because they generate long prose from a large
bundle; here the surface is small enough that withholding the raw material is
enough on its own.

Results are trimmed before they go back into the prompt. A hundred transactions
would cost more tokens than the answer is worth and bury the few rows that
matter, so list tools cap and summarise rather than dumping.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Coroutine

from app.repositories import market as market_repo
from app.repositories.base import connect

finance_goals = importlib.import_module("app.services.finance.goals")
finance_bills = importlib.import_module("app.services.finance.bills")
finance_summary = importlib.import_module("app.services.finance.summary")
finance_transactions = importlib.import_module("app.services.finance.transactions")
portfolio_networth = importlib.import_module("app.services.portfolio.networth")
portfolio_holdings = importlib.import_module("app.services.portfolio.holdings")
portfolio_watchlist = importlib.import_module("app.services.portfolio.watchlist")

ReadHandler = Callable[[dict, dict[str, Any]], Coroutine[Any, Any, Any]]

# Rows returned to the model per list tool. Enough to answer "what did I spend
# on recently"; small enough that the prompt stays cheap on every turn.
_MAX_ROWS = 20


async def _get_finance_summary(user: dict, args: dict[str, Any]) -> Any:
    res = await finance_summary.summary(user["user_id"], args.get("month"))
    return res.model_dump()


async def _get_spending_by_category(user: dict, args: dict[str, Any]) -> Any:
    res = await finance_summary.spending_by_category(
        user["user_id"], int(args.get("days") or 30), user
    )
    return res.model_dump()


async def _get_transactions(user: dict, args: dict[str, Any]) -> Any:
    limit = min(int(args.get("limit") or _MAX_ROWS), _MAX_ROWS)
    rows = await finance_transactions.list_transactions(user["user_id"], limit=limit)
    return [
        {
            "merchant": r.get("merchant"),
            "amount": r.get("amount"),
            "type": r.get("transaction_type"),
            "category": r.get("category"),
            "date": str(r.get("transaction_date") or ""),
            "source": r.get("source"),
        }
        for r in rows[:limit]
    ]


async def _get_goals(user: dict, args: dict[str, Any]) -> Any:
    rows = await finance_goals.list_goals(user["user_id"])
    return [
        {
            "name": g.get("name"),
            "target": g.get("target"),
            "saved": g.get("saved"),
            # Computed here, not by the model: a percentage it works out itself
            # is a number nobody verified.
            "percent_complete": _percent(g.get("saved"), g.get("target")),
            "target_date": str(g.get("target_date") or "") or None,
        }
        for g in rows[:_MAX_ROWS]
    ]


async def _get_bills(user: dict, args: dict[str, Any]) -> Any:
    rows = await finance_bills.list_bills(user["user_id"])
    return [
        {
            "name": b.get("name"),
            "amount": b.get("amount"),
            "due_date": str(b.get("due_date") or "") or None,
            "status": b.get("status"),
            "recurring": b.get("recurring"),
        }
        for b in rows[:_MAX_ROWS]
    ]


async def _get_portfolio_value(user: dict, args: dict[str, Any]) -> Any:
    return await portfolio_networth.networth(user["user_id"])


async def _get_holdings(user: dict, args: dict[str, Any]) -> Any:
    portfolio_id = await portfolio_holdings.resolve_owned_portfolio(user["user_id"], None)
    if portfolio_id is None:
        return []
    rows = await portfolio_holdings.list_holdings(portfolio_id)
    return [
        {
            "symbol": h.get("symbol"),
            "shares": h.get("shares"),
            "avg_cost": h.get("avg_cost"),
        }
        for h in rows[:_MAX_ROWS]
    ]


async def _get_watchlist(user: dict, args: dict[str, Any]) -> Any:
    rows = await portfolio_watchlist.enriched_watchlist(user["user_id"])
    return [
        {
            "symbol": w.get("symbol"),
            "company": w.get("company_name"),
            "price": w.get("price"),
            "change_pct": w.get("change_pct"),
        }
        for w in rows[:_MAX_ROWS]
    ]


async def _resolve_symbol(user: dict, args: dict[str, Any]) -> Any:
    async with connect() as conn:
        candidates = await market_repo.search_symbols(conn, str(args.get("query") or ""))
    return {
        "candidates": candidates,
        # Stated rather than left to inference: with two candidates the agent
        # must ask, and models are markedly better at following an explicit
        # instruction in the tool result than at re-deriving the rule.
        "instruction": (
            "Exactly one candidate: use it. More than one: ask the user which "
            "they meant, listing the names. None: tell the user you could not "
            "find that company on the PSX."
        ),
    }


def _percent(saved: Any, target: Any) -> float | None:
    try:
        saved_f, target_f = float(saved), float(target)
    except (TypeError, ValueError):
        return None
    if target_f <= 0:
        return None
    return round(saved_f / target_f * 100, 1)


READ_HANDLERS: dict[str, ReadHandler] = {
    "get_finance_summary": _get_finance_summary,
    "get_spending_by_category": _get_spending_by_category,
    "get_transactions": _get_transactions,
    "get_goals": _get_goals,
    "get_bills": _get_bills,
    "get_portfolio_value": _get_portfolio_value,
    "get_holdings": _get_holdings,
    "get_watchlist": _get_watchlist,
    "resolve_symbol": _resolve_symbol,
}
