"""Finance transactions data access (user_transactions)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.repositories.finance._common import table

Executor = Any


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
