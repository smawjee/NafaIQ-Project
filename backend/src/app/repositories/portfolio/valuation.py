"""Priced / aggregation reads for the portfolio domain (return raw values; the
service applies calc.* on top). Covers per-portfolio and per-user valuation,
today's P&L lots, history vs KSE-100, and the live total."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def fetch_priced_holdings(conn: Executor, portfolio_id: int) -> list[dict[str, Any]]:
    """Holdings with resolved current price + previous close, for one portfolio."""
    result = await conn.execute(
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
    return [
        {
            "id": r["id"],
            "symbol": r["symbol"],
            "shares": int(r["shares"]),
            "avg_cost": float(r["avg_cost"]),
            "current_price": float(r["current_price"]) if r["current_price"] is not None else None,
            "previous_close": float(r["previous_close"]) if r["previous_close"] is not None else None,
        }
        for r in result.mappings().all()
    ]


async def fetch_networth_holdings(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    """All of a user's holdings with price, previous close, and today's buy lots."""
    result = await conn.execute(
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
            ),
            today_buys AS (
                SELECT
                    st.portfolio_id,
                    st.symbol,
                    SUM(st.quantity) AS today_qty,
                    CASE WHEN SUM(st.quantity) > 0
                         THEN SUM(st.price * st.quantity) / SUM(st.quantity)
                         ELSE 0
                    END AS today_avg_price
                FROM stock_transactions st
                WHERE st.user_id = :uid
                  AND st.side = 'buy'
                  AND (st.executed_at AT TIME ZONE 'Asia/Karachi')::date
                      = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Karachi')::date
                GROUP BY st.portfolio_id, st.symbol
            )
            SELECT
                h.id, h.symbol, h.shares, h.avg_cost,
                COALESCE(s.price, lc.eod_close) AS current_price,
                pc.previous_close AS previous_close,
                s.change AS day_change,
                tb.today_qty,
                tb.today_avg_price
            FROM psx_holdings h
            JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
            LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
            LEFT JOIN prev_close pc ON pc.symbol = h.symbol
            LEFT JOIN latest_close lc ON lc.symbol = h.symbol
            LEFT JOIN today_buys tb ON tb.portfolio_id = h.portfolio_id AND tb.symbol = h.symbol
            ORDER BY h.symbol
            """
        ),
        {"uid": user_id},
    )
    return [
        {
            "id": r["id"],
            "symbol": r["symbol"],
            "shares": int(r["shares"]),
            "avg_cost": float(r["avg_cost"]),
            "current_price": float(r["current_price"]) if r["current_price"] is not None else None,
            "previous_close": float(r["previous_close"]) if r["previous_close"] is not None else None,
            "day_change": float(r["day_change"]) if r["day_change"] is not None else None,
            "today_qty": int(r["today_qty"]) if r["today_qty"] is not None else None,
            "today_avg_price": float(r["today_avg_price"]) if r["today_avg_price"] is not None else None,
        }
        for r in result.mappings().all()
    ]


async def fetch_holding_symbols(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT h.symbol, h.shares
            FROM psx_holdings h
            JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
            """
        ),
        {"uid": user_id},
    )
    return [
        {"symbol": r["symbol"], "shares": int(r["shares"])}
        for r in result.mappings().all()
    ]


async def fetch_symbol_ohlcv(
    conn: Executor, symbol: str, days: int
) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT date, close FROM psx_ohlcv "
            "WHERE symbol = :sym AND date >= CURRENT_DATE - (:days * INTERVAL '1 day') "
            "ORDER BY date ASC"
        ),
        {"sym": symbol, "days": int(days)},
    )
    return [
        {"date": r["date"], "close": float(r["close"] or 0)}
        for r in result.mappings().all()
    ]


async def fetch_symbols_ohlcv(
    conn: Executor, symbols: list[str], days: int
) -> dict[str, list[dict[str, Any]]]:
    if not symbols:
        return {}
    result = await conn.execute(
        text(
            "SELECT symbol, date, close FROM psx_ohlcv "
            "WHERE symbol = ANY(:syms) AND date >= CURRENT_DATE - (:days * INTERVAL '1 day') "
            "ORDER BY symbol, date ASC"
        ),
        {"syms": symbols, "days": int(days)},
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in result.mappings().all():
        sym = r["symbol"]
        if sym not in grouped:
            grouped[sym] = []
        grouped[sym].append({"date": r["date"], "close": float(r["close"] or 0)})
    return grouped


async def fetch_portfolio_value_holdings(
    conn: Executor, portfolio_id: int
) -> list[dict[str, Any]]:
    """Per-holding live P&L (price falls back to cost basis for unpriceable)."""
    result = await conn.execute(
        text(
            """
            -- Resolve current price: live snapshot -> latest EOD close.
            -- Market value falls back to cost basis when a symbol cannot be
            -- priced at all, so unpriceable holdings read flat (0 gain)
            -- instead of a spurious -100% loss.
            SELECT
                h.id, h.symbol, h.shares, h.avg_cost,
                COALESCE(s.price, o.close) AS current_price,
                (h.shares * COALESCE(s.price, o.close, h.avg_cost))::numeric AS market_value,
                (h.shares * h.avg_cost)::numeric AS cost_basis,
                (h.shares * COALESCE(s.price, o.close, h.avg_cost) - h.shares * h.avg_cost)::numeric AS unrealized_pnl,
                CASE WHEN (h.shares * h.avg_cost) > 0 AND COALESCE(s.price, o.close) IS NOT NULL
                    THEN ROUND(
                        ((h.shares * COALESCE(s.price, o.close) - h.shares * h.avg_cost) / (h.shares * h.avg_cost)) * 100,
                        2
                    )
                    ELSE 0
                END AS pnl_pct
            FROM psx_holdings h
            LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
            LEFT JOIN LATERAL (
                SELECT close FROM psx_ohlcv WHERE symbol = h.symbol ORDER BY date DESC LIMIT 1
            ) o ON TRUE
            WHERE h.portfolio_id = :pid
            ORDER BY h.symbol ASC
            """
        ),
        {"pid": portfolio_id},
    )
    return [
        {
            "id": r["id"],
            "symbol": r["symbol"],
            "shares": r["shares"],
            "avg_cost": float(r["avg_cost"]),
            "current_price": float(r["current_price"]) if r["current_price"] else None,
            "market_value": float(r["market_value"]),
            "cost_basis": float(r["cost_basis"]),
            "unrealized_pnl": float(r["unrealized_pnl"]),
            "pnl_pct": float(r["pnl_pct"]),
        }
        for r in result.mappings().all()
    ]


async def fetch_portfolio_history_rows(
    conn: Executor, user_id: str, days: int
) -> list[dict[str, Any]]:
    """Current-holdings value across historical closes with KSE-100 benchmark."""
    result = await conn.execute(
        text(
            """
            WITH portfolio_values AS (
                SELECT
                    o.date,
                    COALESCE(SUM(h.shares * o.close), 0)::numeric AS value
                FROM psx_holdings h
                JOIN psx_portfolios p
                  ON p.id = h.portfolio_id
                 AND p.user_id = :uid
                JOIN psx_ohlcv o
                  ON o.symbol = h.symbol
                -- Chart shows the value of the CURRENT portfolio across
                -- historical closes (no purchased_at filter: a holding
                -- bought today would otherwise have zero bars until the
                -- nightly OHLCV backfill -> empty chart).
                WHERE o.date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                GROUP BY o.date
            ),
            joined AS (
                SELECT
                    pv.date,
                    pv.value,
                    idx.close AS index_close,
                    FIRST_VALUE(pv.value) OVER (ORDER BY pv.date ASC) AS first_value,
                    FIRST_VALUE(idx.close) OVER (ORDER BY pv.date ASC) AS first_index_close
                FROM portfolio_values pv
                LEFT JOIN psx_index_eod idx
                  ON idx.code = 'KSE100'
                 AND idx.date = pv.date
                WHERE pv.value > 0
            )
            SELECT
                date,
                value,
                CASE
                    WHEN first_value > 0
                     AND first_index_close IS NOT NULL
                     AND first_index_close <> 0
                     AND index_close IS NOT NULL
                    THEN (index_close / first_index_close) * first_value
                    ELSE value
                END::numeric AS benchmark
            FROM joined
            ORDER BY date ASC
            """
        ),
        {"uid": user_id, "days": days},
    )
    return [
        {"date": r["date"], "value": float(r["value"]), "benchmark": float(r["benchmark"])}
        for r in result.mappings().all()
    ]


async def fetch_portfolio_live_value(conn: Executor, user_id: str) -> Optional[float]:
    result = await conn.execute(
        text(
            """
            SELECT SUM(
                h.shares * COALESCE(s.price, lc.eod_close, h.avg_cost)
            )::numeric AS value
            FROM psx_holdings h
            JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
            LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
            LEFT JOIN LATERAL (
                SELECT close AS eod_close FROM psx_ohlcv
                WHERE symbol = h.symbol ORDER BY date DESC LIMIT 1
            ) lc ON TRUE
            """
        ),
        {"uid": user_id},
    )
    val = result.scalar()
    return float(val) if val is not None else None
