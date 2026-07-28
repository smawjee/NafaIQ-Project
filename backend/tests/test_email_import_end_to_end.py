"""End-to-end: the exact scenario that was reported, through the real code.

Everything here is the REAL implementation — senders.is_candidate, the rules
parser, correlate, reconcile.merge_pass — with only the database swapped for an
in-memory stand-in. The other test files pin units in isolation; this one exists
to prove the reported bug is actually fixed when the pieces run together, which
is the only claim that matters.

THE REPORTED BUG
A foodpanda order produces three emails: order confirmation (foodpanda),
payment alert (the bank), delivery confirmation (foodpanda). One charge of
PKR 879.80. All three landed as separate transactions.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.services.email_import import pipeline, reconcile
from app.services.email_import.gmail_client import RawMessage

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def msg(mid, sender, subject, body, at, thread=None):
    return RawMessage(
        message_id=mid, sender=sender, subject=subject, body=body,
        received_at=at, internal_date=int(at.timestamp() * 1000), thread_id=thread,
    )


# The three emails one foodpanda order actually produces, plus the bank's.
ORDER_CONFIRMED = msg(
    "fp-1", "foodpanda <no-reply@mail.foodpanda.pk>",
    "Thanks for your order!",
    "Order #FP-88213 confirmed. Your order receipt total is PKR 879.80.",
    T0, thread="thread-fp",
)
BANK_ALERT = msg(
    "hbl-1", "HBL Alerts <alerts@hbl.com>",
    "Transaction alert",
    "PKR 879.80 has been debited from your account ending 1234 at "
    "FOODPANDA PK KARACHI. Available Balance PKR 45,120.00",
    T0 + timedelta(minutes=3),
)
DELIVERED = msg(
    "fp-2", "foodpanda <no-reply@mail.foodpanda.pk>",
    "Your order has been delivered",
    "Order #FP-88213 delivered. Total paid PKR 879.80. Thanks for your order!",
    T0 + timedelta(minutes=41), thread="thread-fp",
)


@asynccontextmanager
async def _fake_begin():
    yield object()


@pytest.fixture
def world(monkeypatch):
    """One in-memory database shared by the pipeline and the reconciler."""
    db = {"txns": {}, "ledger": {}, "aliases": set(), "next_id": [1]}

    # ── ledger ──
    async def stage_message(conn, values):
        mid = values["message_id"]
        if mid in db["ledger"]:
            return db["ledger"][mid], False
        db["ledger"][mid] = {**values, "attempts": 0, "transaction_id": None}
        return db["ledger"][mid], True

    async def get_message(conn, uid, mid):
        return db["ledger"].get(mid)

    async def set_verdict(conn, uid, mid, *, verdict, transaction_id=None,
                          bill_id=None, error=None, signals=None):
        row = db["ledger"].setdefault(mid, {"attempts": 0})
        row["verdict"] = verdict
        row["attempts"] = row.get("attempts", 0) + 1
        if transaction_id is not None:
            row["transaction_id"] = transaction_id
        if signals:
            row.update(signals)

    async def recent_for_reconcile(conn, uid, since):
        # dict(r): the real repo returns freshly-mapped rows, so a later
        # link_to_transaction cannot mutate what the caller is iterating.
        return [dict(r) for r in sorted(
            (r for r in db["ledger"].values()
             if r.get("verdict") == "imported" and r.get("transaction_id")
             and r["received_at"] >= since),
            key=lambda r: r["received_at"],
        )]

    async def fetch_aliases(conn, uid):
        return frozenset(db["aliases"])

    async def record_alias(conn, uid, brand, alias):
        db["aliases"].add((brand, alias))

    async def link_to_transaction(conn, uid, mid, txn_id, *, verdict):
        db["ledger"][mid]["transaction_id"] = txn_id
        db["ledger"][mid]["verdict"] = verdict

    # ── transactions ──
    async def insert_txn(conn, values):
        tid = db["next_id"][0]
        db["next_id"][0] += 1
        db["txns"][tid] = {**values, "id": tid, "edited_at": None}
        return db["txns"][tid]

    async def find_dup(conn, uid, *, merchant, amount, transaction_type,
                       window_lo, window_hi):
        return any(
            abs(t["amount"] - amount) < 0.005
            and t["transaction_type"] == transaction_type
            and t["merchant"].strip().lower() == (merchant or "").strip().lower()
            and window_lo <= t["transaction_date"] <= window_hi
            for t in db["txns"].values()
        )

    async def get_by_ids(conn, uid, ids):
        return {i: db["txns"][i] for i in ids if i in db["txns"]}

    async def absorb(conn, uid, *, keep_id, absorb_id, values):
        if keep_id not in db["txns"] or absorb_id not in db["txns"]:
            return False
        if db["txns"][keep_id]["edited_at"] or db["txns"][absorb_id]["edited_at"]:
            return False
        db["txns"][keep_id].update(values)
        del db["txns"][absorb_id]
        return True

    async def find_reversal_target(conn, uid, **kw):
        return None

    for mod in (pipeline, reconcile):
        monkeypatch.setattr(mod, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.notifier, "notify_activity", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.notifier, "fire_and_forget", lambda *a, **k: None)
    for mod in (pipeline.ledger_repo, reconcile.ledger_repo):
        monkeypatch.setattr(mod, "stage_message", stage_message, raising=False)
        monkeypatch.setattr(mod, "get_message", get_message, raising=False)
        monkeypatch.setattr(mod, "set_verdict", set_verdict, raising=False)
        monkeypatch.setattr(mod, "recent_for_reconcile", recent_for_reconcile, raising=False)
        monkeypatch.setattr(mod, "fetch_aliases", fetch_aliases, raising=False)
        monkeypatch.setattr(mod, "record_alias", record_alias, raising=False)
        monkeypatch.setattr(mod, "link_to_transaction", link_to_transaction, raising=False)
    monkeypatch.setattr(pipeline.finance_repo, "insert_transaction_dedup", insert_txn)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "find_reversal_target", find_reversal_target)
    monkeypatch.setattr(reconcile.txn_repo, "get_transactions_by_ids", get_by_ids)
    monkeypatch.setattr(reconcile.txn_repo, "absorb_transaction", absorb)
    # No LLM in tests: the rules parser must carry these emails on its own.
    monkeypatch.setattr(pipeline.llm, "is_configured", lambda: False)
    return db


async def _run(db, messages):
    """Everything sync_user does per message, then the reconcile pass."""
    result = pipeline.SyncResult()
    for m in messages:
        assert pipeline.senders.is_candidate(m.sender, m.subject, m.body), (
            f"{m.message_id} was rejected at the candidate gate"
        )
        staged, created = await pipeline._stage("u1", m)
        if not created and pipeline._prior_disposition(staged) != "process":
            continue
        await pipeline._process_message("u1", m, [0], result)
    result.merged = await reconcile.merge_pass("u1", now=T0 + timedelta(hours=1))
    return result


@pytest.mark.asyncio
async def test_the_reported_bug_one_order_becomes_one_transaction(world):
    """Three emails, two senders, one charge of PKR 879.80 -> ONE transaction."""
    result = await _run(world, [ORDER_CONFIRMED, BANK_ALERT, DELIVERED])

    assert len(world["txns"]) == 1, (
        f"expected 1 transaction, got {len(world['txns'])}: "
        f"{[(t['merchant'], t['amount']) for t in world['txns'].values()]}"
    )
    txn = next(iter(world["txns"].values()))
    assert abs(txn["amount"] - 879.80) < 0.005
    assert result.imported_transactions + result.merged >= 2


@pytest.mark.asyncio
async def test_the_surviving_row_is_the_richest_one(world):
    """Consolidation, not just suppression: the survivor must carry the
    merchant's real name AND the card tail only the bank knew."""
    await _run(world, [ORDER_CONFIRMED, BANK_ALERT, DELIVERED])

    txn = next(iter(world["txns"].values()))
    assert "foodpanda" in txn["merchant"].lower()
    assert txn["account_tail"] == "1234"
    assert txn["order_ref"] == "FP88213"


@pytest.mark.asyncio
async def test_every_email_is_accounted_for(world):
    """No email is lost: all three have a ledger row with a terminal verdict,
    and every one points at the surviving transaction."""
    await _run(world, [ORDER_CONFIRMED, BANK_ALERT, DELIVERED])

    assert set(world["ledger"]) == {"fp-1", "hbl-1", "fp-2"}
    for mid, row in world["ledger"].items():
        assert row["verdict"] in pipeline.ledger_repo.TERMINAL_VERDICTS, mid

    survivor = next(iter(world["txns"]))
    linked = {r["transaction_id"] for r in world["ledger"].values() if r["transaction_id"]}
    assert linked == {survivor}


@pytest.mark.asyncio
async def test_the_legs_arriving_in_separate_polls_still_collapse(world):
    """The realistic case: the bank alert lands in one poll, the merchant's
    receipt in the next. Correlation has to work across poll boundaries."""
    await _run(world, [BANK_ALERT])
    assert len(world["txns"]) == 1  # projected immediately, as designed

    await _run(world, [ORDER_CONFIRMED, DELIVERED])

    assert len(world["txns"]) == 1
    assert "foodpanda" in next(iter(world["txns"].values()))["merchant"].lower()


@pytest.mark.asyncio
async def test_a_genuinely_separate_order_still_imports(world):
    """The other half of the guarantee. A different foodpanda order the next
    day, same price, must NOT be swallowed."""
    await _run(world, [ORDER_CONFIRMED, BANK_ALERT, DELIVERED])
    assert len(world["txns"]) == 1

    next_day = msg(
        "fp-3", "foodpanda <no-reply@mail.foodpanda.pk>", "Thanks for your order!",
        "Order #FP-99001 confirmed. Your order receipt total is PKR 879.80.",
        T0 + timedelta(hours=25), thread="thread-fp2",
    )
    result = pipeline.SyncResult()
    await pipeline._stage("u1", next_day)
    await pipeline._process_message("u1", next_day, [0], result)
    await reconcile.merge_pass("u1", now=T0 + timedelta(hours=26))

    assert len(world["txns"]) == 2, "a real second order was swallowed as a duplicate"


@pytest.mark.asyncio
async def test_a_declined_payment_in_the_same_stream_creates_nothing(world):
    """A declined attempt followed by the real order: one transaction, and the
    decline is on record rather than silently dropped."""
    declined = msg(
        "hbl-0", "HBL Alerts <alerts@hbl.com>", "Transaction declined",
        "Your transaction of PKR 879.80 at FOODPANDA was declined.",
        T0 - timedelta(minutes=2),
    )
    await _run(world, [declined, ORDER_CONFIRMED, BANK_ALERT, DELIVERED])

    assert len(world["txns"]) == 1
    assert world["ledger"]["hbl-0"]["verdict"] == "failed_txn"
    assert world["ledger"]["hbl-0"]["transaction_id"] is None
