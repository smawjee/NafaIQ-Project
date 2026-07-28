"""Finance bills data access (user_bills), incl. recurring roll-over on paid."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.repositories.finance._common import count_owned, table

Executor = Any


def _optional(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row.get(key, default)
    except AttributeError:
        try:
            return row[key]
        except KeyError:
            return default


def _bill(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "due_date": str(row["due_date"]) if row["due_date"] else None,
        "status": row["status"],
        "recurring": row["recurring"],
        "paid_at": str(row["paid_at"]) if row["paid_at"] else None,
        "source": _optional(row, "source", "manual"),
        "note": _optional(row, "note"),
        "email_message_id": _optional(row, "email_message_id"),
        "created_at": str(row["created_at"]),
    }


async def count_bills(conn: Executor, uid: str) -> int:
    return await count_owned(conn, "user_bills", uid)


async def find_duplicate_bill(conn: Executor, uid: str, correlation_key: str) -> bool:
    """True if this user already has a bill for the same biller, amount and due
    date.

    The content-level guard the email_message_id index cannot provide: a biller
    sends the invoice and then a reminder days later, as two distinct Gmail
    messages, which previously created two bills for one obligation.
    """
    if not correlation_key:
        return False
    bills = await table("user_bills")
    if "correlation_key" not in bills.c:
        return False  # migration not applied yet — fail open, never block an import
    result = await conn.execute(
        select(bills.c.id)
        .where(bills.c.user_id == uid, bills.c.correlation_key == correlation_key)
        .limit(1)
    )
    return result.first() is not None


async def list_bills(conn: Executor, uid: str) -> list[dict[str, Any]]:
    bills = await table("user_bills")
    result = await conn.execute(
        select(bills)
        .where(bills.c.user_id == uid)
        .order_by(bills.c.due_date.asc().nulls_last(), bills.c.created_at.desc())
    )
    return [_bill(r) for r in result.mappings().all()]


async def insert_bill(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    bills = await table("user_bills")
    result = await conn.execute(insert(bills).values(**values).returning(bills))
    return _bill(result.mappings().first())


async def insert_bill_dedup(
    conn: Executor, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Insert an email-sourced bill, ignoring one already imported.

    Targets the partial unique index on (user_id, email_message_id), matching the
    transaction importer, so repeated Gmail polls cannot duplicate the same bill.
    """
    bills = await table("user_bills")
    # Reflected schema + out-of-band migrations: drop keys the DB lacks rather
    # than failing the import (mirrors insert_transaction_dedup).
    values = {k: v for k, v in values.items() if k in bills.c}
    result = await conn.execute(
        pg_insert(bills)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["user_id", "email_message_id"],
            index_where=bills.c.email_message_id.isnot(None),
        )
        .returning(bills)
    )
    row = result.mappings().first()
    return _bill(row) if row else None


async def update_bill(
    conn: Executor, uid: str, bill_id: int, values: dict[str, Any]
) -> Optional[dict[str, Any]]:
    bills = await table("user_bills")
    result = await conn.execute(
        update(bills)
        .where(bills.c.id == bill_id, bills.c.user_id == uid)
        .values(**values)
        .returning(bills)
    )
    row = result.mappings().first()
    return _bill(row) if row else None


async def mark_bill_paid(conn: Executor, uid: str, bill_id: int) -> Optional[dict[str, Any]]:
    bills = await table("user_bills")
    existing = await conn.execute(
        select(bills.c.recurring).where(bills.c.id == bill_id, bills.c.user_id == uid)
    )
    row = existing.first()
    if row is None:
        return None
    if row[0]:  # recurring: record the payment, then roll to next month's cycle
        result = await conn.execute(
            update(bills)
            .where(bills.c.id == bill_id, bills.c.user_id == uid)
            .values(
                status="UPCOMING",
                paid_at=text("now()"),
                due_date=text("(COALESCE(due_date, CURRENT_DATE) + INTERVAL '1 month')::date"),
            )
            .returning(bills)
        )
    else:  # one-off: mark paid
        result = await conn.execute(
            update(bills)
            .where(bills.c.id == bill_id, bills.c.user_id == uid)
            .values(status="PAID", paid_at=text("now()"))
            .returning(bills)
        )
    return _bill(result.mappings().first())


async def delete_bill(conn: Executor, uid: str, bill_id: int) -> Optional[int]:
    bills = await table("user_bills")
    result = await conn.execute(
        delete(bills).where(bills.c.id == bill_id, bills.c.user_id == uid).returning(bills.c.id)
    )
    row = result.first()
    return bill_id if row else None