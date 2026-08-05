"""Stock-transaction data access (stock_transactions) + the user_transactions
reflection insert that mirrors a trade into the finance feed."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


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
    broker_import_item_id: Optional[int] = None,
) -> dict[str, Any]:
    result = await conn.execute(
        text(
            "INSERT INTO stock_transactions "
            "(user_id, portfolio_id, symbol, side, quantity, price, fees, "
            "executed_at, notes, source, broker_import_item_id) "
            "VALUES (:uid, :pid, :sym, :side, :qty, :price, :fees, "
            "        :executed, :notes, :src, :broker_item_id) "
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
            "broker_item_id": broker_import_item_id,
        },
    )
    return _stock_txn_dict(result.mappings().first())


async def fetch_portfolio_lots(conn: Executor, portfolio_id: int) -> list[dict[str, Any]]:
    """Every stock_transactions lot for a portfolio, ordered so a fold
    reconstructs each symbol's holding: by symbol, then chronologically.

    Ordering by (executed_at, id) makes `adjust` snapshots authoritative at
    their point in time and keeps buy/sell weighted-average maths deterministic.
    """
    result = await conn.execute(
        text(
            "SELECT symbol, side, quantity, price, fees, executed_at "
            "FROM stock_transactions WHERE portfolio_id = :pid "
            "ORDER BY symbol ASC, executed_at ASC, id ASC"
        ),
        {"pid": portfolio_id},
    )
    return [
        {
            "symbol": r["symbol"],
            "side": r["side"],
            "quantity": int(r["quantity"]),
            "price": float(r["price"]),
            "fees": float(r["fees"]),
            "executed_at": r["executed_at"],
        }
        for r in result.mappings().all()
    ]


async def fetch_symbol_lots(
    conn: Executor, portfolio_id: int, symbol: str
) -> list[dict[str, Any]]:
    """Ordered lots for a single (portfolio, symbol) — used by drift detection."""
    result = await conn.execute(
        text(
            "SELECT symbol, side, quantity, price, fees, executed_at "
            "FROM stock_transactions WHERE portfolio_id = :pid AND symbol = :sym "
            "ORDER BY executed_at ASC, id ASC"
        ),
        {"pid": portfolio_id, "sym": symbol.upper()},
    )
    return [
        {
            "symbol": r["symbol"],
            "side": r["side"],
            "quantity": int(r["quantity"]),
            "price": float(r["price"]),
            "fees": float(r["fees"]),
            "executed_at": r["executed_at"],
        }
        for r in result.mappings().all()
    ]


async def delete_symbol_lots(
    conn: Executor, portfolio_id: int, symbol: str
) -> dict[str, int]:
    """Delete a (portfolio, symbol)'s lots when its holding is removed as a
    mistake, WITHOUT erasing realised income from real prior sales.

    The delete path means "this position never should have existed". That
    undoes the buys — their lots and their EXPENSE reflections. It must NOT
    touch INCOME reflections: if the user genuinely sold part of the position
    earlier (POST /trades side='sell'), real cash came in and was booked to the
    finance feed. That income is money they actually received; deleting it
    silently would falsify their finance history (audit 2026-07-22, HIGH).

    So: delete only the expense reflections, then delete every lot. The
    surviving income reflections have their `stock_transaction_id` set to NULL
    by the FK's ON DELETE SET NULL — no longer linked to a lot (there is no
    position left to link to), but retained as standalone, truthful realised
    income. Deleting all lots (not just the buys) keeps the symbol free of
    orphan sell lots, so a later rebuild_holdings_from_transactions cannot
    reconstruct a nonsensical negative position from a lone sell.

    Expense reflections go FIRST, before their lots: `stock_transaction_id` is
    ON DELETE SET NULL, so removing a buy lot first would strand its expense
    reflection with a NULL link — a phantom expense the user never made.

    Scoped to the symbol: other positions in the same portfolio are untouched.
    """
    sym = symbol.upper()
    # Only the expenses (the mistaken buys). Income from real sells is preserved.
    reflections = await conn.execute(
        text(
            "DELETE FROM user_transactions "
            "WHERE source = 'stock_trade' AND transaction_type = 'expense' "
            "AND stock_transaction_id IN ("
            "    SELECT id FROM stock_transactions "
            "    WHERE portfolio_id = :pid AND symbol = :sym"
            ") RETURNING id"
        ),
        {"pid": portfolio_id, "sym": sym},
    )
    reflections_deleted = len(reflections.fetchall())

    # Count income reflections that will survive (their link is about to NULL),
    # for an honest return value the caller can surface.
    income_kept = await conn.execute(
        text(
            "SELECT count(*) AS n FROM user_transactions "
            "WHERE source = 'stock_trade' AND transaction_type = 'income' "
            "AND stock_transaction_id IN ("
            "    SELECT id FROM stock_transactions "
            "    WHERE portfolio_id = :pid AND symbol = :sym"
            ")"
        ),
        {"pid": portfolio_id, "sym": sym},
    )
    income_preserved = int(income_kept.mappings().first()["n"])

    lots = await conn.execute(
        text(
            "DELETE FROM stock_transactions "
            "WHERE portfolio_id = :pid AND symbol = :sym RETURNING id"
        ),
        {"pid": portfolio_id, "sym": sym},
    )
    lots_deleted = len(lots.fetchall())

    return {
        "lots_deleted": lots_deleted,
        "reflections_deleted": reflections_deleted,
        "income_preserved": income_preserved,
    }


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
