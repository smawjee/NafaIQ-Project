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
