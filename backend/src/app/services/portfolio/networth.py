"""Portfolio valuation & analytics: per-portfolio value, net worth, allocation,
history, and performance vs KSE-100. Business logic over portfolio."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import connect
from app.services import calculations as calc
from app.services.psx.sector_map import get_sector_map


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
        ohlcv = await repo.fetch_symbols_ohlcv(conn, symbols, int(days))
    return calc.portfolio_history_from_ohlcv(holdings, ohlcv, days=int(days))


async def performance_vs_kse100(user_id: str, days: int = 180) -> list[dict[str, Any]]:
    from app.services.psx.benchmark import get_kse100_series

    port = await history(user_id, days=days)
    kse = await get_kse100_series(days=days)
    kse_points = [{"date": b["date"], "close": b["close"]} for b in kse]
    return calc.performance_vs_kse100(port, kse_points)


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
