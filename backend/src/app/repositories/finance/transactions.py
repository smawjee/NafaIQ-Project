"""Finance transactions data access (user_transactions)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.repositories.finance._common import table

Executor = Any


async def find_duplicate_transaction(
    conn: Executor,
    uid: str,
    *,
    merchant: str,
    amount: float,
    transaction_type: str,
    window_lo: Any,
    window_hi: Any,
) -> bool:
    """True if this user already has a transaction with the same amount, type and
    (case/space-insensitively) the same merchant within [window_lo, window_hi].

    This is the content-level guard the message_id dedup can't provide: a
    multi-email merchant (foodpanda sends order-confirmed, receipt AND delivered
    mails for ONE order — each a distinct Gmail message) would otherwise land as
    several identical transactions. It matches the merchant EXACTLY (only case and
    surrounding spaces normalized) and fails open — a merchant spelled
    differently across those mails is simply not treated as a duplicate, so a
    genuine new transaction is never silently dropped.
    """
    txns = await table("user_transactions")
    result = await conn.execute(
        select(txns.c.id)
        .where(
            txns.c.user_id == uid,
            # Half-cent tolerance, not `==`: the amount is money stored as NUMERIC
            # but bound here as a float, and float equality against NUMERIC can
            # miss (879.80 has no exact float) — which would silently defeat the
            # dedup and let the duplicate through.
            func.abs(txns.c.amount - amount) < 0.005,
            txns.c.transaction_type == transaction_type,
            func.lower(func.btrim(txns.c.merchant)) == (merchant or "").strip().lower(),
            txns.c.transaction_date >= window_lo,
            txns.c.transaction_date <= window_hi,
        )
        .limit(1)
    )
    return result.first() is not None


def _transaction(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "merchant": row["merchant"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "transaction_type": row["transaction_type"],
        "category": row["category"],
        "transaction_date": str(row["transaction_date"]),
        "source": row["source"],
        "note": row["note"],
        "created_at": str(row["created_at"]),
    }


async def list_transactions(conn: Executor, uid: str, limit: int) -> list[dict[str, Any]]:
    txns = await table("user_transactions")
    result = await conn.execute(
        select(txns)
        .where(txns.c.user_id == uid)
        .order_by(txns.c.transaction_date.desc())
        .limit(max(1, min(limit, 500)))
    )
    return [_transaction(r) for r in result.mappings().all()]


async def insert_transaction(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    txns = await table("user_transactions")
    result = await conn.execute(insert(txns).values(**values).returning(txns))
    return _transaction(result.mappings().first())


async def insert_transaction_dedup(
    conn: Executor, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Insert an email-sourced transaction, ignoring one we've already imported.

    Targets the partial unique index on (user_id, email_message_id) so re-polling
    the same bank email can never duplicate a transaction. Returns None when the
    row already existed (DO NOTHING yields no RETURNING row).
    """
    txns = await table("user_transactions")
    result = await conn.execute(
        pg_insert(txns)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["user_id", "email_message_id"],
            index_where=txns.c.email_message_id.isnot(None),
        )
        .returning(txns)
    )
    row = result.mappings().first()
    return _transaction(row) if row else None


async def update_transaction(
    conn: Executor, uid: str, txn_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    txns = await table("user_transactions")
    result = await conn.execute(
        update(txns)
        .where(txns.c.id == txn_id, txns.c.user_id == uid)
        .values(**values)
        .returning(txns)
    )
    row = result.mappings().first()
    return _transaction(row) if row else None


async def delete_transaction(conn: Executor, uid: str, txn_id: int) -> Optional[int]:
    txns = await table("user_transactions")
    result = await conn.execute(
        delete(txns).where(txns.c.id == txn_id, txns.c.user_id == uid).returning(txns.c.id)
    )
    row = result.first()
    return txn_id if row else None
