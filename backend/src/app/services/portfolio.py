"""Portfolio service: holdings aggregation, allocation, performance."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text

from app.db.sqlalchemy import get_session_factory
from app.services import calculations as calc
from app.services.psx.sector_map import get_sector_map

log = logging.getLogger(__name__)


async def list_holdings(portfolio_id: int) -> list[dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                "SELECT id, portfolio_id, symbol, shares, avg_cost, purchased_at "
                "FROM psx_holdings WHERE portfolio_id = :pid ORDER BY symbol"
            ),
            {"pid": portfolio_id},
        )
        return [
            {
                "id": r["id"],
                "portfolio_id": r["portfolio_id"],
                "symbol": r["symbol"],
                "shares": int(r["shares"]),
                "avg_cost": float(r["avg_cost"]),
                "purchased_at": (
                    str(r["purchased_at"]) if r["purchased_at"] is not None else None
                ),
            }
            for r in rows.mappings().all()
        ]


async def value_for_portfolio(portfolio_id: int) -> dict[str, Any]:
    """Live P&L: join holdings with current market prices and previous close."""
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                """
                WITH prev_close AS (
                    SELECT DISTINCT ON (symbol) symbol, close AS previous_close
                    FROM psx_ohlcv
                    WHERE date < CURRENT_DATE
                    ORDER BY symbol, date DESC
                ),
                latest_close AS (
                    SELECT DISTINCT ON (symbol) symbol, close AS eod_close
                    FROM psx_ohlcv
                    ORDER BY symbol, date DESC
                )
                SELECT
                    h.id, h.symbol, h.shares, h.avg_cost,
                    COALESCE(s.price, lc.eod_close) AS current_price,
                    pc.previous_close AS previous_close
                FROM psx_holdings h
                LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                LEFT JOIN prev_close pc ON pc.symbol = h.symbol
                LEFT JOIN latest_close lc ON lc.symbol = h.symbol
                WHERE h.portfolio_id = :pid
                ORDER BY h.symbol
                """
            ),
            {"pid": portfolio_id},
        )
        holding_rows: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            row = calc.compute_holding_row(
                symbol=r["symbol"],
                shares=int(r["shares"]),
                avg_cost=float(r["avg_cost"]),
                latest_price=(
                    float(r["current_price"]) if r["current_price"] is not None else None
                ),
                previous_close=(
                    float(r["previous_close"])
                    if r["previous_close"] is not None
                    else None
                ),
            )
            row["id"] = r["id"]
            holding_rows.append(row)
    totals = calc.aggregate_portfolio_totals(holding_rows)
    return {
        "holdings": holding_rows,
        "totals": totals,
    }


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
    """Sum totals across all user portfolios."""
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            text(
                """
                WITH prev_close AS (
                    SELECT DISTINCT ON (symbol) symbol, close AS previous_close
                    FROM psx_ohlcv
                    WHERE date < CURRENT_DATE
                    ORDER BY symbol, date DESC
                ),
                latest_close AS (
                    SELECT DISTINCT ON (symbol) symbol, close AS eod_close
                    FROM psx_ohlcv
                    ORDER BY symbol, date DESC
                )
                SELECT
                    h.id, h.symbol, h.shares, h.avg_cost,
                    COALESCE(s.price, lc.eod_close) AS current_price,
                    pc.previous_close AS previous_close
                FROM psx_holdings h
                JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
                LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                LEFT JOIN prev_close pc ON pc.symbol = h.symbol
                LEFT JOIN latest_close lc ON lc.symbol = h.symbol
                ORDER BY h.symbol
                """
            ),
            {"uid": user_id},
        )
        holdings: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            row = calc.compute_holding_row(
                symbol=r["symbol"],
                shares=int(r["shares"]),
                avg_cost=float(r["avg_cost"]),
                latest_price=(
                    float(r["current_price"]) if r["current_price"] is not None else None
                ),
                previous_close=(
                    float(r["previous_close"])
                    if r["previous_close"] is not None
                    else None
                ),
            )
            holdings.append(row)
        portfolio_count_row = await session.execute(
            text("SELECT COUNT(*) AS c FROM psx_portfolios WHERE user_id = :uid"),
            {"uid": user_id},
        )
        portfolio_count = int(portfolio_count_row.scalar() or 0)
    totals = calc.aggregate_portfolio_totals(holdings)
    totals["portfolio_count"] = portfolio_count
    totals["holding_count"] = len(holdings)
    totals["by_holding"] = holdings
    return totals


async def history(user_id: str, days: int = 180) -> list[dict[str, Any]]:
    """Build portfolio history from current holdings and psx_ohlcv."""
    factory = get_session_factory()
    async with factory() as session:
        # current holdings
        h_rows = await session.execute(
            text(
                """
                SELECT h.symbol, h.shares
                FROM psx_holdings h
                JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
                """
            ),
            {"uid": user_id},
        )
        holdings = [
            {"symbol": r["symbol"], "shares": int(r["shares"])}
            for r in h_rows.mappings().all()
        ]
        symbols = [h["symbol"] for h in holdings]
        if not symbols:
            return []
        # historical OHLCV for each symbol
        ohlcv: dict[str, list[dict[str, Any]]] = {}
        for sym in symbols:
            r = await session.execute(
                text(
                    "SELECT date, close FROM psx_ohlcv "
                    "WHERE symbol = :sym AND date >= CURRENT_DATE - (:days * INTERVAL '1 day') "
                    "ORDER BY date ASC"
                ),
                {"sym": sym, "days": int(days)},
            )
            ohlcv[sym] = [
                {"date": row["date"], "close": float(row["close"] or 0)}
                for row in r.mappings().all()
            ]
    return calc.portfolio_history_from_ohlcv(holdings, ohlcv, days=int(days))


async def performance_vs_kse100(user_id: str, days: int = 180) -> list[dict[str, Any]]:
    from app.services.psx.benchmark import get_kse100_series

    port = await history(user_id, days=days)
    kse = await get_kse100_series(days=days)
    kse_points = [{"date": b["date"], "close": b["close"]} for b in kse]
    return calc.performance_vs_kse100(port, kse_points)
