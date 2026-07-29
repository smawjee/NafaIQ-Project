"""Finance transactions data access (user_transactions)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, func, insert, or_ as sa_or, select, update
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


def _optional(row: Any, key: str, default: Any = None) -> Any:
    """Read a column that may not exist yet.

    Schema is REFLECTED from the live DB at startup and migrations are applied
    out-of-band, so there is a window where the code knows about a column the
    database does not have. Mirrors the same helper in bills.py.
    """
    try:
        return row.get(key, default)
    except AttributeError:
        try:
            return row[key]
        except KeyError:
            return default


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
        "order_ref": _optional(row, "order_ref"),
        "account_tail": _optional(row, "account_tail"),
        "reverses_transaction_id": _optional(row, "reverses_transaction_id"),
        "edited_at": (
            str(_optional(row, "edited_at")) if _optional(row, "edited_at") else None
        ),
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
    # Schema is reflected from the live DB and migrations are applied
    # out-of-band, so drop keys the database does not have yet rather than
    # failing the whole import on a column that has not landed.
    values = {k: v for k, v in values.items() if k in txns.c}
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
    # Stamp the row as user-edited. This is the reconciler's merge guard: once a
    # human has corrected a transaction, automation must never absorb or
    # overwrite it, because a bad merge would silently discard their correction.
    if "edited_at" in txns.c:
        values = {**values, "edited_at": func.now()}
    result = await conn.execute(
        update(txns)
        .where(txns.c.id == txn_id, txns.c.user_id == uid)
        .values(**values)
        .returning(txns)
    )
    row = result.mappings().first()
    return _transaction(row) if row else None


async def get_transactions_by_ids(
    conn: Executor, uid: str, ids: list[int]
) -> dict[int, dict[str, Any]]:
    """The named transactions, keyed by id. Ids that no longer exist are simply
    absent — which is how the reconciler notices a row was already absorbed."""
    if not ids:
        return {}
    txns = await table("user_transactions")
    result = await conn.execute(
        select(txns).where(txns.c.user_id == uid, txns.c.id.in_(ids))
    )
    return {r["id"]: _transaction(r) for r in result.mappings().all()}


async def absorb_transaction(
    conn: Executor, uid: str, *, keep_id: int, absorb_id: int, values: dict[str, Any]
) -> bool:
    """Merge `absorb_id` into `keep_id`: enrich the survivor, delete the other.

    Returns False WITHOUT touching anything when either row has been edited by
    the user. That guard is the whole reason this is a repository function
    rather than an update + delete at the call site: the check and the write
    must not be separable, or a merge could race past a correction.
    """
    txns = await table("user_transactions")
    if "edited_at" in txns.c:
        guard = await conn.execute(
            select(txns.c.id).where(
                txns.c.user_id == uid,
                txns.c.id.in_([keep_id, absorb_id]),
                txns.c.edited_at.isnot(None),
            )
        )
        if guard.first() is not None:
            return False

    # Both rows must still exist — one may have been absorbed by an earlier
    # pairing in this same pass, or deleted by the user mid-poll.
    present = await conn.execute(
        select(func.count())
        .select_from(txns)
        .where(txns.c.user_id == uid, txns.c.id.in_([keep_id, absorb_id]))
    )
    row = present.first()
    if not row or int(row[0]) != 2:
        return False

    if values:
        await conn.execute(
            update(txns)
            .where(txns.c.id == keep_id, txns.c.user_id == uid)
            .values(**values)
        )
    await conn.execute(
        delete(txns).where(txns.c.id == absorb_id, txns.c.user_id == uid)
    )
    return True


async def fill_missing_correlation_fields(
    conn: Executor,
    uid: str,
    *,
    merchant: str,
    amount: float,
    transaction_type: str,
    window_lo: Any,
    window_hi: Any,
    order_ref: Optional[str] = None,
    account_tail: Optional[str] = None,
) -> bool:
    """Give a suppressed duplicate's signals to the row that already exists.

    When a merchant's second email is dropped as a duplicate, it often knows
    something the recorded row does not — the receipt leg carries the order ref
    the order-confirmation lacked. Without this those signals are stranded on
    the ledger and the later cross-source merge loses its decisive evidence.

    Only ever FILLS NULLs; never overwrites a value already present, and never
    touches a user-edited row. Returns True if anything was written.
    """
    if not (order_ref or account_tail):
        return False
    txns = await table("user_transactions")
    updates: dict[str, Any] = {}
    if order_ref and "order_ref" in txns.c:
        updates["order_ref"] = order_ref
    if account_tail and "account_tail" in txns.c:
        updates["account_tail"] = account_tail
    if not updates:
        return False

    conditions = [
        txns.c.user_id == uid,
        func.abs(txns.c.amount - amount) < 0.005,
        txns.c.transaction_type == transaction_type,
        func.lower(func.btrim(txns.c.merchant)) == (merchant or "").strip().lower(),
        txns.c.transaction_date >= window_lo,
        txns.c.transaction_date <= window_hi,
        # Only rows still missing at least one of the fields we can supply.
        sa_or(*[txns.c[column].is_(None) for column in updates]),
    ]
    if "edited_at" in txns.c:
        conditions.append(txns.c.edited_at.is_(None))

    target = await conn.execute(
        select(txns.c.id).where(*conditions).order_by(txns.c.transaction_date.asc()).limit(1)
    )
    row = target.first()
    if row is None:
        return False
    # COALESCE so a column that already has a value is left exactly as it was.
    await conn.execute(
        update(txns)
        .where(txns.c.id == row[0], txns.c.user_id == uid)
        .values(**{c: func.coalesce(txns.c[c], v) for c, v in updates.items()})
    )
    return True


async def find_reversal_target(
    conn: Executor,
    uid: str,
    *,
    amount: float,
    transaction_type: str,
    order_ref: Optional[str],
    window_lo: Any,
    window_hi: Any,
) -> Optional[int]:
    """The transaction a refund/reversal is giving money back for.

    Matches the OPPOSITE direction (a refund of an expense is income), by order
    ref when both have one, else by amount within the window. Returns None when
    nothing matches — the reversal still imports, just unlinked, because a
    refund with no findable original is still real money.
    """
    txns = await table("user_transactions")
    conditions = [
        txns.c.user_id == uid,
        txns.c.transaction_type == transaction_type,
        txns.c.transaction_date >= window_lo,
        txns.c.transaction_date <= window_hi,
    ]
    if order_ref and "order_ref" in txns.c:
        conditions.append(txns.c.order_ref == order_ref)
    else:
        # Half-cent tolerance, not `==`: NUMERIC bound as a float.
        conditions.append(func.abs(txns.c.amount - amount) < 0.005)
    result = await conn.execute(
        select(txns.c.id)
        .where(*conditions)
        .order_by(txns.c.transaction_date.desc())
        .limit(1)
    )
    row = result.first()
    return int(row[0]) if row else None


async def delete_transaction(conn: Executor, uid: str, txn_id: int) -> Optional[int]:
    txns = await table("user_transactions")
    result = await conn.execute(
        delete(txns).where(txns.c.id == txn_id, txns.c.user_id == uid).returning(txns.c.id)
    )
    row = result.first()
    return txn_id if row else None
