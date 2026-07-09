"""Portfolio data access: portfolios, holdings, stock transactions, watchlist,
and the priced/aggregation queries. All SQL for the portfolio domain lives here.

Every function takes an executor (AsyncConnection or AsyncSession) so the
calling service owns the transaction boundary. Functions return plain Python
data (dicts / scalars), never ORM rows.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text

Executor = Any  # AsyncConnection | AsyncSession — both expose .execute()


# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------


async def list_portfolios(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, name, created_at
            FROM psx_portfolios
            WHERE user_id = :uid
            ORDER BY created_at ASC
            """
        ),
        {"uid": user_id},
    )
    return [
        {"id": r["id"], "name": r["name"], "created_at": str(r["created_at"])}
        for r in result.mappings().all()
    ]


async def insert_portfolio(conn: Executor, user_id: str, name: str) -> dict[str, Any]:
    result = await conn.execute(
        text(
            """
            INSERT INTO psx_portfolios (user_id, name)
            VALUES (:uid, :name)
            RETURNING id, name, created_at
            """
        ),
        {"uid": user_id, "name": name},
    )
    row = result.mappings().first()
    return {"id": row["id"], "name": row["name"], "created_at": str(row["created_at"])}


async def is_portfolio_owned(conn: Executor, user_id: str, portfolio_id: int) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
        {"pid": portfolio_id, "uid": user_id},
    )
    return result.first() is not None


async def get_portfolio_name(
    conn: Executor, user_id: str, portfolio_id: int
) -> Optional[str]:
    result = await conn.execute(
        text("SELECT name FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
        {"pid": portfolio_id, "uid": user_id},
    )
    row = result.mappings().first()
    return row["name"] if row else None


async def first_portfolio_id(conn: Executor, user_id: str) -> Optional[int]:
    result = await conn.execute(
        text(
            "SELECT id FROM psx_portfolios "
            "WHERE user_id = :uid ORDER BY created_at ASC LIMIT 1"
        ),
        {"uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else None


async def count_user_portfolios(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text("SELECT COUNT(*) AS c FROM psx_portfolios WHERE user_id = :uid"),
        {"uid": user_id},
    )
    return int(result.scalar() or 0)


async def count_holdings(conn: Executor, portfolio_id: int, exclude_symbol: str) -> int:
    """Holdings in a portfolio excluding one symbol (for add-holding quota:
    updating an existing symbol must not be blocked by the limit)."""
    result = await conn.execute(
        text(
            "SELECT COUNT(*) FROM psx_holdings "
            "WHERE portfolio_id = :pid AND symbol <> :sym"
        ),
        {"pid": portfolio_id, "sym": exclude_symbol.upper()},
    )
    return int(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


def _holding_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "portfolio_id": r["portfolio_id"],
        "symbol": r["symbol"],
        "shares": int(r["shares"]),
        "avg_cost": float(r["avg_cost"]),
        "purchased_at": str(r["purchased_at"]) if r["purchased_at"] is not None else None,
    }


async def list_holdings(conn: Executor, portfolio_id: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, portfolio_id, symbol, shares, avg_cost, purchased_at
            FROM psx_holdings
            WHERE portfolio_id = :pid
            ORDER BY symbol ASC
            """
        ),
        {"pid": portfolio_id},
    )
    return [_holding_dict(r) for r in result.mappings().all()]


async def is_holding_owned(
    conn: Executor, user_id: str, portfolio_id: int, holding_id: int
) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT h.id FROM psx_holdings h
            JOIN psx_portfolios p ON p.id = h.portfolio_id
            WHERE h.id = :hid AND p.id = :pid AND p.user_id = :uid
            """
        ),
        {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
    )
    return result.first() is not None


async def upsert_holding_add(
    conn: Executor,
    portfolio_id: int,
    symbol: str,
    shares: int,
    avg_cost: float,
    purchased_at: Optional[str],
) -> dict[str, Any]:
    """Add shares to a holding (weighted-average cost) or create it."""
    result = await conn.execute(
        text(
            """
            INSERT INTO psx_holdings (portfolio_id, symbol, shares, avg_cost, purchased_at)
            VALUES (:pid, :sym, :shares, :cost, :pdate)
            ON CONFLICT (portfolio_id, symbol) DO UPDATE
            SET shares = psx_holdings.shares + EXCLUDED.shares,
                avg_cost = (psx_holdings.avg_cost * psx_holdings.shares + EXCLUDED.avg_cost * EXCLUDED.shares)
                           / NULLIF(psx_holdings.shares + EXCLUDED.shares, 0)
            RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """
        ),
        {
            "pid": portfolio_id,
            "sym": symbol.upper(),
            "shares": shares,
            "cost": avg_cost,
            "pdate": purchased_at,
        },
    )
    return _holding_dict(result.mappings().first())


async def update_holding_fields(
    conn: Executor, holding_id: int, fields: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Patch shares/avg_cost/purchased_at. `fields` uses column names."""
    column_bind = {"shares": "shares", "avg_cost": "cost", "purchased_at": "pdate"}
    sets: list[str] = []
    params: dict[str, Any] = {"hid": holding_id}
    for col, bind in column_bind.items():
        if col in fields:
            sets.append(f"{col} = :{bind}")
            params[bind] = fields[col]
    if not sets:
        return None
    result = await conn.execute(
        text(
            f"""
            UPDATE psx_holdings SET {", ".join(sets)}
            WHERE id = :hid
            RETURNING id, portfolio_id, symbol, shares, avg_cost, purchased_at
            """
        ),
        params,
    )
    return _holding_dict(result.mappings().first())


async def delete_holding(
    conn: Executor, user_id: str, portfolio_id: int, holding_id: int
) -> Optional[int]:
    result = await conn.execute(
        text(
            """
            DELETE FROM psx_holdings h
            USING psx_portfolios p
            WHERE h.id = :hid
              AND h.portfolio_id = p.id
              AND p.id = :pid
              AND p.user_id = :uid
            RETURNING h.id
            """
        ),
        {"hid": holding_id, "pid": portfolio_id, "uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else None


async def get_holding_by_symbol(
    conn: Executor, portfolio_id: int, symbol: str
) -> Optional[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT id, shares, avg_cost FROM psx_holdings "
            "WHERE portfolio_id = :pid AND symbol = :sym"
        ),
        {"pid": portfolio_id, "sym": symbol.upper()},
    )
    r = result.mappings().first()
    if r is None:
        return None
    return {"id": r["id"], "shares": int(r["shares"]), "avg_cost": float(r["avg_cost"])}


async def insert_holding(
    conn: Executor,
    portfolio_id: int,
    symbol: str,
    shares: int,
    avg_cost: float,
    purchased_at: date,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO psx_holdings "
            "(portfolio_id, symbol, shares, avg_cost, purchased_at) "
            "VALUES (:pid, :sym, :shares, :cost, :date)"
        ),
        {
            "pid": portfolio_id,
            "sym": symbol.upper(),
            "shares": shares,
            "cost": avg_cost,
            "date": purchased_at,
        },
    )


async def update_holding_position(
    conn: Executor, holding_id: int, shares: int, avg_cost: float, purchased_at: date
) -> None:
    await conn.execute(
        text(
            "UPDATE psx_holdings "
            "SET shares = :shares, avg_cost = :cost, "
            "    purchased_at = LEAST(purchased_at, :date) "
            "WHERE id = :id"
        ),
        {"shares": shares, "cost": avg_cost, "date": purchased_at, "id": holding_id},
    )


async def set_holding_shares(conn: Executor, holding_id: int, shares: int) -> None:
    await conn.execute(
        text("UPDATE psx_holdings SET shares = :s WHERE id = :id"),
        {"s": shares, "id": holding_id},
    )


async def delete_holding_by_id(conn: Executor, holding_id: int) -> None:
    await conn.execute(
        text("DELETE FROM psx_holdings WHERE id = :id"), {"id": holding_id}
    )


# ---------------------------------------------------------------------------
# Priced / aggregation reads (return raw values; service applies calc.*)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


async def fetch_watchlist_enriched(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT
                w.symbol,
                COALESCE(p.name, w.symbol) AS company_name,
                COALESCE(p.sector, 'Other') AS sector,
                p.logoid,
                s.price,
                s.change,
                s.change_pct,
                s.volume,
                s.refreshed_at AS last_updated
            FROM user_watchlist w
            LEFT JOIN psx_profile p ON upper(trim(p.symbol)) = upper(trim(w.symbol))
            LEFT JOIN psx_market_snapshot s ON upper(trim(s.symbol)) = upper(trim(w.symbol))
            WHERE w.user_id = :uid
            ORDER BY w.added_at DESC
            """
        ),
        {"uid": user_id},
    )
    return [
        {
            "symbol": r["symbol"],
            "company_name": r["company_name"],
            "sector": r["sector"],
            "logoid": r["logoid"],
            "price": float(r["price"]) if r["price"] is not None else None,
            "change": float(r["change"]) if r["change"] is not None else None,
            "change_pct": float(r["change_pct"]) if r["change_pct"] is not None else None,
            "volume": int(r["volume"]) if r["volume"] else 0,
            "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
        }
        for r in result.mappings().all()
    ]


# ---------------------------------------------------------------------------
# Stock transactions
# ---------------------------------------------------------------------------


def _stock_txn_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "portfolio_id": r["portfolio_id"],
        "symbol": r["symbol"],
        "side": r["side"],
        "quantity": int(r["quantity"]),
        "price": float(r["price"]),
        "fees": float(r["fees"]),
        "executed_at": str(r["executed_at"]),
        "notes": r["notes"],
        "source": r["source"],
        "created_at": str(r["created_at"]),
    }


async def list_stock_transactions(
    conn: Executor, user_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT id, user_id, portfolio_id, symbol, side, quantity, price, "
            "fees, executed_at, notes, source, created_at "
            "FROM stock_transactions WHERE user_id = :uid "
            "ORDER BY executed_at DESC LIMIT :lim"
        ),
        {"uid": user_id, "lim": max(1, min(limit, 500))},
    )
    return [_stock_txn_dict(r) for r in result.mappings().all()]


async def insert_stock_transaction(
    conn: Executor,
    *,
    user_id: str,
    portfolio_id: int,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    fees: float,
    executed_at: Any,
    notes: Optional[str],
    source: str,
) -> dict[str, Any]:
    result = await conn.execute(
        text(
            "INSERT INTO stock_transactions "
            "(user_id, portfolio_id, symbol, side, quantity, price, fees, "
            "executed_at, notes, source) "
            "VALUES (:uid, :pid, :sym, :side, :qty, :price, :fees, "
            "        :executed, :notes, :src) "
            "RETURNING id, user_id, portfolio_id, symbol, side, quantity, "
            "          price, fees, executed_at, notes, source, created_at"
        ),
        {
            "uid": user_id,
            "pid": portfolio_id,
            "sym": symbol.upper(),
            "side": side,
            "qty": int(quantity),
            "price": float(price),
            "fees": float(fees),
            "executed": executed_at,
            "notes": notes,
            "src": source,
        },
    )
    return _stock_txn_dict(result.mappings().first())


async def insert_finance_reflection(
    conn: Executor,
    *,
    user_id: str,
    merchant: str,
    amount: float,
    transaction_type: str,
    transaction_date: Any,
    note: str,
    stock_transaction_id: int,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO user_transactions "
            "(user_id, merchant, amount, currency, transaction_type, category, "
            " transaction_date, source, note, stock_transaction_id) "
            "VALUES (:uid, :merchant, :amount, 'PKR', :ttype, 'Investment', "
            "        :txdate, 'stock_trade', :note, :stid)"
        ),
        {
            "uid": user_id,
            "merchant": merchant,
            "amount": amount,
            "ttype": transaction_type,
            "txdate": transaction_date,
            "note": note,
            "stid": stock_transaction_id,
        },
    )
