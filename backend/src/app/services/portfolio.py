"""Portfolio service: business logic for holdings, valuation, allocation,
performance, and trades. All DB access is delegated to
app.repositories.portfolio_repo; this module holds no SQL.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import portfolio_repo as repo
from app.repositories.base import begin, connect, session
from app.schemas.portfolio import HoldingCreate, HoldingUpdate, StockTransactionCreate
from app.services import calculations as calc
from app.services.permissions import check_count_limit
from app.services.psx.sector_map import get_sector_map
from app.services.symbols import require_known_symbol

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reads / aggregations
# ---------------------------------------------------------------------------


async def list_holdings(portfolio_id: int) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_holdings(conn, portfolio_id)


async def value_for_portfolio(portfolio_id: int) -> dict[str, Any]:
    """Live P&L: holdings priced against market snapshot + previous close."""
    async with connect() as conn:
        priced = await repo.fetch_priced_holdings(conn, portfolio_id)
    holding_rows: list[dict[str, Any]] = []
    for r in priced:
        row = calc.compute_holding_row(
            symbol=r["symbol"],
            shares=r["shares"],
            avg_cost=r["avg_cost"],
            latest_price=r["current_price"],
            previous_close=r["previous_close"],
        )
        row["id"] = r["id"]
        holding_rows.append(row)
    return {"holdings": holding_rows, "totals": calc.aggregate_portfolio_totals(holding_rows)}


async def allocation(portfolio_id: int, by: str = "stock") -> list[dict[str, Any]]:
    val = await value_for_portfolio(portfolio_id)
    holdings = val["holdings"]
    if by == "stock":
        return calc.allocation_by_stock(holdings)
    if by == "sector":
        sector_map = await get_sector_map()
        return calc.allocation_by_sector(holdings, sector_map)
    return []


async def networth(user_id: str) -> dict[str, Any]:
    """Sum totals across all of a user's portfolios.

    Today P&L is lot-aware: shares bought today (from stock_transactions) are
    valued against their buy price, older shares against the previous close.
    """
    async with connect() as conn:
        raw = await repo.fetch_networth_holdings(conn, user_id)
        portfolio_count = await repo.count_user_portfolios(conn, user_id)
    holdings = [
        calc.compute_holding_row(
            symbol=r["symbol"],
            shares=r["shares"],
            avg_cost=r["avg_cost"],
            latest_price=r["current_price"],
            previous_close=r["previous_close"],
            today_qty=r["today_qty"],
            today_avg_price=r["today_avg_price"],
        )
        for r in raw
    ]
    totals = calc.aggregate_portfolio_totals(holdings)
    totals["portfolio_count"] = portfolio_count
    totals["holding_count"] = len(holdings)
    totals["by_holding"] = holdings
    return totals


async def history(user_id: str, days: int = 180) -> list[dict[str, Any]]:
    """Build portfolio history from current holdings and psx_ohlcv."""
    async with connect() as conn:
        holdings = await repo.fetch_holding_symbols(conn, user_id)
        symbols = [h["symbol"] for h in holdings]
        if not symbols:
            return []
        ohlcv: dict[str, list[dict[str, Any]]] = {}
        for sym in symbols:
            ohlcv[sym] = await repo.fetch_symbol_ohlcv(conn, sym, int(days))
    return calc.portfolio_history_from_ohlcv(holdings, ohlcv, days=int(days))


async def enriched_watchlist(user_id: str) -> list[dict[str, Any]]:
    """Return the user's watchlist enriched with names, prices, and sectors."""
    async with connect() as conn:
        return await repo.fetch_watchlist_enriched(conn, user_id)


async def performance_vs_kse100(user_id: str, days: int = 180) -> list[dict[str, Any]]:
    from app.services.psx.benchmark import get_kse100_series

    port = await history(user_id, days=days)
    kse = await get_kse100_series(days=days)
    kse_points = [{"date": b["date"], "close": b["close"]} for b in kse]
    return calc.performance_vs_kse100(port, kse_points)


# ---------------------------------------------------------------------------
# Portfolio / holding CRUD
# ---------------------------------------------------------------------------


async def list_portfolios(user_id: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_portfolios(conn, user_id)


async def create_portfolio(user: dict, name: str) -> dict[str, Any]:
    user_id = user["user_id"]
    async with begin() as conn:
        current = await repo.count_user_portfolios(conn, user_id)
        check_count_limit(user, feature_key="max_portfolios", current=current, label="Portfolios")
        return await repo.insert_portfolio(conn, user_id, name)


async def list_holdings_owned(user_id: str, portfolio_id: int) -> list[dict[str, Any]]:
    async with connect() as conn:
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        return await repo.list_holdings(conn, portfolio_id)


async def add_holding(user: dict, portfolio_id: int, body: HoldingCreate) -> dict[str, Any]:
    user_id = user["user_id"]
    async with begin() as conn:
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        await require_known_symbol(conn, body.symbol)
        current = await repo.count_holdings(conn, portfolio_id, body.symbol)
        check_count_limit(
            user, feature_key="max_holdings_per_portfolio", current=current, label="Holdings"
        )
        return await repo.upsert_holding_add(
            conn, portfolio_id, body.symbol, body.shares, body.avg_cost, body.purchased_at
        )


async def update_holding(
    user_id: str, portfolio_id: int, holding_id: int, body: HoldingUpdate
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if body.shares is not None:
        fields["shares"] = body.shares
    if body.avg_cost is not None:
        fields["avg_cost"] = body.avg_cost
    if body.purchased_at is not None:
        fields["purchased_at"] = body.purchased_at
    if not fields:
        raise HTTPException(400, "No fields to update")

    async with begin() as conn:
        if not await repo.is_holding_owned(conn, user_id, portfolio_id, holding_id):
            raise HTTPException(404, "Holding not found")
        return await repo.update_holding_fields(conn, holding_id, fields)


async def delete_holding(user_id: str, portfolio_id: int, holding_id: int) -> dict[str, Any]:
    async with begin() as conn:
        deleted = await repo.delete_holding(conn, user_id, portfolio_id, holding_id)
    if deleted is None:
        raise HTTPException(404, "Holding not found")
    return {"deleted": holding_id}


async def portfolio_value(user_id: str, portfolio_id: int) -> dict[str, Any]:
    """Live P&L for one portfolio; 404 if not owned by the user."""
    async with connect() as conn:
        name = await repo.get_portfolio_name(conn, user_id, portfolio_id)
        if name is None:
            raise HTTPException(404, "Portfolio not found")
        holdings = await repo.fetch_portfolio_value_holdings(conn, portfolio_id)

    totals = {
        "market_value": sum(h["market_value"] for h in holdings),
        "cost_basis": sum(h["cost_basis"] for h in holdings),
        "unrealized_pnl": sum(h["unrealized_pnl"] for h in holdings),
    }
    totals["pnl_pct"] = (
        round((totals["unrealized_pnl"] / totals["cost_basis"]) * 100, 2)
        if totals["cost_basis"] > 0
        else 0.0
    )
    return {"portfolio_id": portfolio_id, "name": name, "holdings": holdings, "totals": totals}


async def portfolio_history(user_id: str, days: int = 180) -> dict[str, Any]:
    """Historical value of current holdings across PSX closes + KSE-100 overlay,
    plus a live "today" point when today's EOD bar isn't ingested yet."""
    bounded_days = max(7, min(days, 365))
    async with connect() as conn:
        rows = await repo.fetch_portfolio_history_rows(conn, user_id, bounded_days)

        # Append a live "today" point from the snapshot when today's EOD bar
        # hasn't been ingested yet, so a freshly bought portfolio charts
        # immediately instead of showing an empty state.
        last_date = rows[-1]["date"] if rows else None
        today_row = None
        if last_date is None or str(last_date) < str(datetime.now(timezone.utc).date()):
            live_value = await repo.fetch_portfolio_live_value(conn, user_id)
            if live_value and live_value > 0:
                today = datetime.now(timezone.utc).date()
                today_row = {
                    "date": today,
                    "value": live_value,
                    "benchmark": rows[-1]["benchmark"] if rows else live_value,
                }

    points = [
        {
            "date": str(r["date"]),
            "label": r["date"].strftime("%b %d") if hasattr(r["date"], "strftime") else str(r["date"]),
            "value": r["value"],
            "benchmark": r["benchmark"],
        }
        for r in rows
    ]
    if today_row is not None:
        points.append(
            {
                "date": str(today_row["date"]),
                "label": today_row["date"].strftime("%b %d"),
                "value": today_row["value"],
                "benchmark": today_row["benchmark"],
            }
        )
    return {"days": bounded_days, "points": points}


async def resolve_owned_portfolio(user_id: str, portfolio_id: Optional[int]) -> Optional[int]:
    """None -> user's first portfolio (or None); an explicit id must be owned."""
    async with connect() as conn:
        if portfolio_id is None:
            return await repo.first_portfolio_id(conn, user_id)
        if not await repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")
        return portfolio_id


# ---------------------------------------------------------------------------
# Stock transactions (trade -> holding upsert -> finance reflection)
# ---------------------------------------------------------------------------


async def list_stock_transactions(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_stock_transactions(conn, user_id, limit)


async def _apply_holding_change(conn, body: StockTransactionCreate, executed) -> None:
    """Weighted-average-cost buy / decrement-or-remove sell on the holding."""
    existing = await repo.get_holding_by_symbol(conn, body.portfolio_id, body.symbol)
    if existing is None and body.side == "buy":
        await repo.insert_holding(
            conn, body.portfolio_id, body.symbol, int(body.quantity),
            float(body.price), executed.date(),
        )
    elif existing is not None:
        if body.side == "buy":
            new_shares = existing["shares"] + int(body.quantity)
            new_cost = (
                (existing["avg_cost"] * existing["shares"])
                + (float(body.price) * int(body.quantity))
            ) / new_shares if new_shares > 0 else 0
            await repo.update_holding_position(
                conn, existing["id"], new_shares, round(new_cost, 4), executed.date()
            )
        else:  # sell
            new_shares = max(0, existing["shares"] - int(body.quantity))
            if new_shares == 0:
                await repo.delete_holding_by_id(conn, existing["id"])
            else:
                await repo.set_holding_shares(conn, existing["id"], new_shares)


async def create_stock_transaction(user: dict, body: StockTransactionCreate) -> dict[str, Any]:
    """Record a trade; for buy/sell also upsert the holding (weighted average
    cost) and reflect the cash movement into personal finance."""
    async with session() as sess:
        if not await repo.is_portfolio_owned(sess, user["user_id"], body.portfolio_id):
            raise HTTPException(404, "Portfolio not found")

        await require_known_symbol(sess, body.symbol)

        if body.side == "buy":
            current = await repo.count_holdings(sess, body.portfolio_id, body.symbol)
            check_count_limit(
                user, feature_key="max_holdings_per_portfolio", current=current, label="Holdings"
            )

        executed = body.executed_at or datetime.now(timezone.utc)
        r = await repo.insert_stock_transaction(
            sess,
            user_id=user["user_id"],
            portfolio_id=body.portfolio_id,
            symbol=body.symbol,
            side=body.side,
            quantity=int(body.quantity),
            price=float(body.price),
            fees=float(body.fees),
            executed_at=executed,
            notes=body.notes,
            source=body.source,
        )

        if body.side in ("buy", "sell"):
            await _apply_holding_change(sess, body, executed)

            # Reflect the trade in personal finance: a buy is cash out
            # (expense), a sell is cash in (income); categorised 'Investment',
            # source 'stock_trade' so they're identifiable/filterable later.
            gross = float(body.price) * int(body.quantity)
            if body.side == "buy":
                fin_type = "expense"
                fin_amount = gross + float(body.fees)
                merchant = f"Buy {int(body.quantity)} {body.symbol.upper()}"
            else:
                fin_type = "income"
                fin_amount = max(0.01, gross - float(body.fees))
                merchant = f"Sell {int(body.quantity)} {body.symbol.upper()}"
            await repo.insert_finance_reflection(
                sess,
                user_id=user["user_id"],
                merchant=merchant,
                amount=round(fin_amount, 2),
                transaction_type=fin_type,
                transaction_date=executed,
                note=f"{int(body.quantity)} @ {float(body.price)}",
                stock_transaction_id=r["id"],
            )

        await sess.commit()
    return r
