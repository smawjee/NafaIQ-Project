"""Staging-ledger data access (email_import_messages).

Backend-only: the table has RLS enabled with no policy for `authenticated`, so
it is reachable only through the direct Postgres connection — same access model
as user_email_integrations, and for the same reason (it holds email subjects
and parsed financial detail).

This table is import INFRASTRUCTURE, not finance data: a durable queue, an
audit trail and a retry buffer. Nothing in api/finance*, the budget joins or the
assistant's tools reads it. All money lives in user_transactions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.repositories.finance._common import table

Executor = Any

# Terminal verdicts: the message has been fully handled and will never be
# reprocessed. Anything else is still in flight and may be retried.
TERMINAL_VERDICTS: tuple[str, ...] = (
    "imported",
    "merged",
    "duplicate",
    "failed_txn",
    "not_transaction",
    "low_confidence",
)

# A message that has failed this many times is left alone: something about it is
# permanently unparseable, and retrying forever would burn an LLM call every
# poll. It stays queryable so it is visible, not lost.
MAX_ATTEMPTS = 5


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "message_id": row["message_id"],
        "thread_id": row["thread_id"],
        "sender_domain": row["sender_domain"],
        "subject": row["subject"],
        "received_at": row["received_at"],
        "internal_date": row["internal_date"],
        "verdict": row["verdict"],
        "parsed": row["parsed"],
        "order_ref": row["order_ref"],
        "amount": float(row["amount"]) if row["amount"] is not None else None,
        "original_amount": (
            float(row["original_amount"]) if row["original_amount"] is not None else None
        ),
        "original_currency": row["original_currency"],
        "account_tail": row["account_tail"],
        "merchant_norm": row["merchant_norm"],
        "brand_token": row["brand_token"],
        "transaction_id": row["transaction_id"],
        "bill_id": row["bill_id"],
        "error": row["error"],
        "attempts": row["attempts"],
    }


async def stage_message(conn: Executor, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Record a candidate email before anything else touches it.

    This is the durability guarantee. Staging happens BEFORE parsing, so the
    poll watermark can advance without risking loss: retries are driven from
    this table rather than by re-downloading from Gmail.

    Returns (row, created). `created` is False when the message was already
    staged by an earlier poll, in which case the row returned is the EXISTING
    one — verdict and attempts included — so the caller can decide whether it is
    still owed another pass.

    One round-trip either way. `xmax = 0` is the standard Postgres tell for
    "this RETURNING row came from the INSERT, not the UPDATE"; the alternative
    (DO NOTHING, then SELECT on miss) costs a second query on every re-poll, and
    Gmail's coarse `after:` filter means re-polls are the common case, not the
    exception.
    """
    msgs = await table("email_import_messages")
    result = await conn.execute(
        pg_insert(msgs)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id", "message_id"],
            # A no-op touch: the row must be returned, and ON CONFLICT DO
            # NOTHING returns nothing at all.
            set_={"updated_at": func.now()},
        )
        .returning(msgs, literal_column("(xmax = 0)").label("inserted"))
    )
    row = result.mappings().first()
    return _row(row), bool(row["inserted"])


async def get_message(
    conn: Executor, user_id: str, message_id: str
) -> Optional[dict[str, Any]]:
    msgs = await table("email_import_messages")
    result = await conn.execute(
        select(msgs).where(
            msgs.c.user_id == user_id, msgs.c.message_id == message_id
        )
    )
    row = result.mappings().first()
    return _row(row) if row else None


async def set_verdict(
    conn: Executor,
    user_id: str,
    message_id: str,
    *,
    verdict: str,
    transaction_id: Optional[int] = None,
    bill_id: Optional[int] = None,
    error: Optional[str] = None,
    signals: Optional[dict[str, Any]] = None,
) -> None:
    """Record how a message ended up, and bank the signals extracted from it.

    `attempts` always increments, including on success — it is the count of
    processing passes, which is what the retry ceiling needs.
    """
    msgs = await table("email_import_messages")
    values: dict[str, Any] = {
        "verdict": verdict,
        "attempts": msgs.c.attempts + 1,
        "updated_at": func.now(),
        "error": (error or None) and str(error)[:500],
    }
    if transaction_id is not None:
        values["transaction_id"] = transaction_id
    if bill_id is not None:
        values["bill_id"] = bill_id
    if signals:
        values.update(signals)
    await conn.execute(
        update(msgs)
        .where(msgs.c.user_id == user_id, msgs.c.message_id == message_id)
        .values(**values)
    )


async def link_to_transaction(
    conn: Executor, user_id: str, message_id: str, transaction_id: int, *, verdict: str
) -> None:
    """Repoint a message at the transaction that absorbed it.

    Used after a merge, so "which emails formed transaction #41" stays a single
    indexed query even for the legs whose own rows were absorbed.
    """
    msgs = await table("email_import_messages")
    await conn.execute(
        update(msgs)
        .where(msgs.c.user_id == user_id, msgs.c.message_id == message_id)
        .values(transaction_id=transaction_id, verdict=verdict, updated_at=func.now())
    )


async def recent_for_reconcile(
    conn: Executor, user_id: str, since: datetime
) -> list[dict[str, Any]]:
    """Staged messages that produced a live transaction since `since`.

    Only 'imported' rows are candidates: an already-'merged' row's transaction
    no longer exists, and re-considering it would let a rejected pairing come
    back every poll.
    """
    msgs = await table("email_import_messages")
    result = await conn.execute(
        select(msgs)
        .where(
            msgs.c.user_id == user_id,
            msgs.c.received_at >= since,
            msgs.c.verdict == "imported",
            msgs.c.transaction_id.isnot(None),
        )
        .order_by(msgs.c.received_at.asc())
    )
    return [_row(r) for r in result.mappings().all()]


async def retryable(
    conn: Executor, user_id: str, *, max_attempts: int = MAX_ATTEMPTS
) -> list[dict[str, Any]]:
    """Messages still owed another processing pass, oldest first."""
    msgs = await table("email_import_messages")
    result = await conn.execute(
        select(msgs)
        .where(
            msgs.c.user_id == user_id,
            msgs.c.verdict.in_(("pending", "parse_error")),
            msgs.c.attempts < max_attempts,
        )
        .order_by(msgs.c.internal_date.asc())
    )
    return [_row(r) for r in result.mappings().all()]


async def unparsed_count(conn: Executor, user_id: str) -> int:
    """How many emails could not be read. Surfaced in Settings so an incomplete
    picture is visible to the user rather than silently incomplete."""
    msgs = await table("email_import_messages")
    result = await conn.execute(
        select(func.count())
        .select_from(msgs)
        .where(msgs.c.user_id == user_id, msgs.c.verdict == "parse_error")
    )
    row = result.first()
    return int(row[0]) if row else 0


async def recent_failures(
    conn: Executor, user_id: str, since: datetime
) -> list[dict[str, Any]]:
    """Recent failed/declined payments — what a successful retry correlates
    against so the retry imports exactly once."""
    msgs = await table("email_import_messages")
    result = await conn.execute(
        select(msgs).where(
            and_(
                msgs.c.user_id == user_id,
                msgs.c.received_at >= since,
                msgs.c.verdict == "failed_txn",
            )
        )
    )
    return [_row(r) for r in result.mappings().all()]


# ── learned merchant aliases ─────────────────────────────────────────────────


async def record_alias(
    conn: Executor, user_id: str, brand: str, alias_norm: str
) -> None:
    """Remember that `alias_norm` is how some sender writes `brand`.

    Only ever called after a DECISIVE (order-ref) merge, so the pairing is
    evidence-backed rather than inferred from a weaker match — otherwise a bad
    guess would compound into future merges.
    """
    if not brand or not alias_norm or brand == alias_norm:
        return
    aliases = await table("email_merchant_aliases")
    await conn.execute(
        pg_insert(aliases)
        .values(user_id=user_id, brand_token=brand, alias_norm=alias_norm)
        .on_conflict_do_update(
            index_elements=["user_id", "brand_token", "alias_norm"],
            set_={"hits": aliases.c.hits + 1, "last_seen": func.now()},
        )
    )


async def fetch_aliases(conn: Executor, user_id: str) -> frozenset[tuple[str, str]]:
    """This user's learned (brand, alias) pairs, in the shape correlate.score
    expects."""
    aliases = await table("email_merchant_aliases")
    result = await conn.execute(
        select(aliases.c.brand_token, aliases.c.alias_norm).where(
            aliases.c.user_id == user_id
        )
    )
    return frozenset((r[0], r[1]) for r in result.all())
