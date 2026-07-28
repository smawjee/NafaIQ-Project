"""Reconciler: collapsing the legs of one financial event into one transaction.

The scenario this exists for: a foodpanda order produces an order confirmation
(foodpanda), a payment alert (the bank) and a delivery confirmation
(foodpanda). Three Gmail messages, one charge. The old dedup required the
merchant string to match exactly, so the bank leg always escaped and the charge
landed two or three times.

Both directions are pinned here. A false merge silently deletes a real
transaction from someone's records, so every "these must NOT merge" test is as
load-bearing as the ones that assert collapsing works.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.services.email_import import reconcile

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def ledger(
    message_id: str,
    txn_id: int,
    *,
    at: datetime = T0,
    amount: float = 879.80,
    merchant_norm: str = "foodpanda",
    brand_token: str | None = "foodpanda",
    account_tail: str | None = None,
    order_ref: str | None = None,
    original_currency: str | None = None,
) -> dict:
    return {
        "message_id": message_id,
        "transaction_id": txn_id,
        "received_at": at,
        "amount": amount,
        "original_currency": original_currency,
        "merchant_norm": merchant_norm,
        "brand_token": brand_token,
        "account_tail": account_tail,
        "order_ref": order_ref,
        "verdict": "imported",
        "parsed": {"transaction_type": "expense"},
    }


def txn(txn_id: int, **kw) -> dict:
    base = {
        "id": txn_id,
        "merchant": "foodpanda",
        "amount": 879.80,
        "transaction_type": "expense",
        "category": "food & dining",
        "transaction_date": T0,
        "source": "Email receipt · auto",
        "account_tail": None,
        "order_ref": None,
        "edited_at": None,
    }
    base.update(kw)
    return base


@asynccontextmanager
async def _fake_begin():
    yield object()


@pytest.fixture
def store(monkeypatch):
    """In-memory stand-in for the ledger + transactions tables, wired so the
    REAL merge_pass logic drives it."""
    state = {"ledger": [], "txns": {}, "aliases": set(), "recorded_aliases": []}

    async def recent_for_reconcile(conn, user_id, since):
        # dict(r) -- the real repo maps each row into a fresh dict, so a later
        # link_to_transaction UPDATE cannot mutate a list the caller is already
        # iterating. Sharing the objects here made merge_pass see writes it
        # never sees in production.
        return [dict(r) for r in state["ledger"]
                if r["received_at"] >= since and r["verdict"] == "imported"]

    async def fetch_aliases(conn, user_id):
        return frozenset(state["aliases"])

    async def record_alias(conn, user_id, brand, alias_norm):
        state["recorded_aliases"].append((brand, alias_norm))
        state["aliases"].add((brand, alias_norm))

    async def link_to_transaction(conn, user_id, message_id, transaction_id, *, verdict):
        for r in state["ledger"]:
            if r["message_id"] == message_id:
                r["transaction_id"] = transaction_id
                r["verdict"] = verdict

    async def get_transactions_by_ids(conn, uid, ids):
        return {i: state["txns"][i] for i in ids if i in state["txns"]}

    async def absorb_transaction(conn, uid, *, keep_id, absorb_id, values):
        keep = state["txns"].get(keep_id)
        absorb = state["txns"].get(absorb_id)
        if keep is None or absorb is None:
            return False
        if keep.get("edited_at") or absorb.get("edited_at"):
            return False
        keep.update(values)
        del state["txns"][absorb_id]
        return True

    monkeypatch.setattr(reconcile, "begin", _fake_begin)
    monkeypatch.setattr(reconcile.ledger_repo, "recent_for_reconcile", recent_for_reconcile)
    monkeypatch.setattr(reconcile.ledger_repo, "fetch_aliases", fetch_aliases)
    monkeypatch.setattr(reconcile.ledger_repo, "record_alias", record_alias)
    monkeypatch.setattr(reconcile.ledger_repo, "link_to_transaction", link_to_transaction)
    monkeypatch.setattr(reconcile.txn_repo, "get_transactions_by_ids", get_transactions_by_ids)
    monkeypatch.setattr(reconcile.txn_repo, "absorb_transaction", absorb_transaction)
    return state


# ── merge_values: which field wins ───────────────────────────────────────────


def test_merge_values_prefers_a_named_counterparty_over_a_channel_title():
    """The bank leg landed first and could only say "Card Purchase". When the
    merchant's own mail arrives it must upgrade that heading, not be discarded."""
    keep = txn(1, merchant="Card Purchase", account_tail="1234")
    absorb = txn(2, merchant="foodpanda", order_ref="FP88213")
    merged = reconcile.merge_values(keep, absorb)
    assert merged["merchant"] == "foodpanda"
    assert merged["account_tail"] == "1234"  # kept: absorbed row had none
    assert merged["order_ref"] == "FP88213"  # gained from the absorbed row


def test_merge_values_never_downgrades_a_good_merchant_to_a_channel_title():
    keep = txn(1, merchant="foodpanda", account_tail="1234", order_ref="FP88213")
    absorb = txn(2, merchant="Card Purchase")
    merged = reconcile.merge_values(keep, absorb)
    assert merged.get("merchant", "foodpanda") == "foodpanda"


def test_merge_values_never_changes_the_amount():
    """Merging is about identity, not arithmetic. Silently altering a figure
    would be indistinguishable from corrupting the user's records."""
    keep = txn(1, amount=879.80)
    absorb = txn(2, amount=880.00)
    assert "amount" not in reconcile.merge_values(keep, absorb)


def test_merge_values_keeps_the_earliest_date():
    """When the event actually happened, not when the last email about it
    arrived."""
    keep = txn(1, transaction_date=T0 + timedelta(hours=1))
    absorb = txn(2, transaction_date=T0)
    assert reconcile.merge_values(keep, absorb)["transaction_date"] == T0


def test_merge_values_upgrades_a_generic_category():
    keep = txn(1, category="other")
    absorb = txn(2, category="food & dining")
    assert reconcile.merge_values(keep, absorb)["category"] == "food & dining"


# ── merge_pass ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bank_leg_and_merchant_leg_collapse_to_one_transaction(store):
    """THE bug. Two sources, one order: one transaction must survive, carrying
    the merchant name from one leg and the card tail from the other."""
    store["txns"] = {
        1: txn(1, merchant="Card Purchase", account_tail="1234", transaction_date=T0),
        2: txn(2, merchant="foodpanda", account_tail="1234",
               transaction_date=T0 + timedelta(minutes=8)),
    }
    store["ledger"] = [
        ledger("bank-1", 1, merchant_norm="card purchase", brand_token=None,
               account_tail="1234"),
        ledger("panda-1", 2, at=T0 + timedelta(minutes=8), account_tail="1234"),
    ]

    absorbed = await reconcile.merge_pass("u1", now=T0 + timedelta(minutes=10))

    assert absorbed == 1
    assert len(store["txns"]) == 1
    survivor = next(iter(store["txns"].values()))
    assert survivor["merchant"] == "foodpanda"   # upgraded from "Card Purchase"
    assert survivor["account_tail"] == "1234"    # kept from the bank leg


@pytest.mark.asyncio
async def test_three_emails_for_one_order_leave_one_transaction(store):
    """foodpanda's order-confirmed, receipt and delivered mails."""
    store["txns"] = {
        i: txn(i, transaction_date=T0 + timedelta(minutes=15 * i), account_tail="1234")
        for i in (1, 2, 3)
    }
    store["ledger"] = [
        ledger(f"m{i}", i, at=T0 + timedelta(minutes=15 * i), account_tail="1234")
        for i in (1, 2, 3)
    ]

    absorbed = await reconcile.merge_pass("u1", now=T0 + timedelta(hours=1))

    assert absorbed == 2
    assert len(store["txns"]) == 1


@pytest.mark.asyncio
async def test_distinct_orders_are_not_merged(store):
    """Same merchant, same price, 3h apart, nothing else in common. Two real
    purchases — merging them would delete one from the user's records."""
    store["txns"] = {
        1: txn(1, merchant="Cafe Kohi", transaction_date=T0, amount=450.0),
        2: txn(2, merchant="Cafe Kohi", transaction_date=T0 + timedelta(hours=3),
               amount=450.0),
    }
    store["ledger"] = [
        ledger("a", 1, amount=450.0, merchant_norm="cafe kohi", brand_token="kohi"),
        ledger("b", 2, at=T0 + timedelta(hours=3), amount=450.0,
               merchant_norm="cafe kohi", brand_token="kohi"),
    ]

    assert await reconcile.merge_pass("u1", now=T0 + timedelta(hours=4)) == 0
    assert len(store["txns"]) == 2


@pytest.mark.asyncio
async def test_user_edited_row_is_never_absorbed(store):
    """Once a human corrects a transaction, automation must not discard it."""
    store["txns"] = {
        1: txn(1, merchant="Card Purchase", account_tail="1234"),
        2: txn(2, merchant="foodpanda", account_tail="1234",
               transaction_date=T0 + timedelta(minutes=8), edited_at="2026-06-18"),
    }
    store["ledger"] = [
        ledger("bank-1", 1, merchant_norm="card purchase", brand_token=None,
               account_tail="1234"),
        ledger("panda-1", 2, at=T0 + timedelta(minutes=8), account_tail="1234"),
    ]

    assert await reconcile.merge_pass("u1", now=T0 + timedelta(minutes=10)) == 0
    assert len(store["txns"]) == 2


@pytest.mark.asyncio
async def test_merged_ledger_rows_point_at_the_surviving_transaction(store):
    """The audit trail: "which emails formed this transaction" must stay
    answerable after a merge."""
    store["txns"] = {
        1: txn(1, merchant="Card Purchase", account_tail="1234"),
        2: txn(2, merchant="foodpanda", account_tail="1234",
               transaction_date=T0 + timedelta(minutes=8)),
    }
    store["ledger"] = [
        ledger("bank-1", 1, merchant_norm="card purchase", brand_token=None,
               account_tail="1234"),
        ledger("panda-1", 2, at=T0 + timedelta(minutes=8), account_tail="1234"),
    ]

    await reconcile.merge_pass("u1", now=T0 + timedelta(minutes=10))

    survivor_id = next(iter(store["txns"]))
    assert {r["transaction_id"] for r in store["ledger"]} == {survivor_id}
    assert sorted(r["verdict"] for r in store["ledger"]) == ["imported", "merged"]


@pytest.mark.asyncio
async def test_decisive_order_ref_merge_teaches_the_alias(store):
    """A bank descriptor sharing no token with the brand can only ever be
    matched once something proves the pairing. An order ref is that proof, and
    the lesson is banked so the NEXT such pair merges without one."""
    store["txns"] = {
        1: txn(1, merchant="foodpanda"),
        2: txn(2, merchant="FPANDA KHI", transaction_date=T0 + timedelta(minutes=5)),
    }
    store["ledger"] = [
        ledger("panda-1", 1, order_ref="FP88213"),
        ledger("bank-1", 2, at=T0 + timedelta(minutes=5), order_ref="FP88213",
               merchant_norm="fpanda", brand_token=None),
    ]

    await reconcile.merge_pass("u1", now=T0 + timedelta(minutes=10))

    assert ("foodpanda", "fpanda") in store["recorded_aliases"]


@pytest.mark.asyncio
async def test_reconcile_window_is_48h(store):
    """A candidate older than the window is not even considered."""
    old = T0 - timedelta(hours=50)
    store["txns"] = {1: txn(1, transaction_date=old), 2: txn(2, transaction_date=T0)}
    store["ledger"] = [
        ledger("old", 1, at=old, account_tail="1234"),
        ledger("new", 2, at=T0, account_tail="1234"),
    ]

    assert await reconcile.merge_pass("u1", now=T0) == 0
    assert len(store["txns"]) == 2


# ── transitivity: the survivor grows as it absorbs ───────────────────────────


def test_merge_signals_fills_gaps_without_overwriting():
    from app.services.email_import.correlate import Signals

    keep = Signals(order_ref=None, amount=879.80, original_currency=None,
                   account_tail=None, merchant_norm="foodpanda",
                   brand_token="foodpanda", occurred_at=T0,
                   transaction_type="expense")
    absorb = Signals(order_ref="FP88213", amount=879.80, original_currency=None,
                     account_tail="1234", merchant_norm="card purchase",
                     brand_token=None, occurred_at=T0 - timedelta(minutes=5),
                     transaction_type="expense")

    merged = reconcile.merge_signals(keep, absorb)
    assert merged.order_ref == "FP88213"        # gained
    assert merged.account_tail == "1234"        # gained
    assert merged.brand_token == "foodpanda"    # kept -- never weakened
    assert merged.merchant_norm == "foodpanda"  # kept
    assert merged.occurred_at == T0 - timedelta(minutes=5)  # earliest leg


@pytest.mark.asyncio
async def test_a_third_leg_merges_on_evidence_the_first_merge_established(store):
    """A names the merchant, B carries the card tail, C shares ONLY the tail.

    Scored against A's arrival signals C never merges -- A had no tail. Scored
    against the survivor after it absorbed B, it does. This is the difference
    between a 3-email order collapsing to one row and to two.
    """
    store["txns"] = {
        1: txn(1, merchant="foodpanda", account_tail=None, transaction_date=T0),
        2: txn(2, merchant="Card Purchase", account_tail="1234",
               transaction_date=T0 + timedelta(minutes=5)),
        3: txn(3, merchant="Card Purchase", account_tail="1234",
               transaction_date=T0 + timedelta(minutes=50)),
    }
    store["ledger"] = [
        # A: names the merchant, no tail.
        ledger("a", 1, at=T0),
        # B: no brand, has the tail -- merges with A on brand-in-merchant+amount+time.
        ledger("b", 2, at=T0 + timedelta(minutes=5), account_tail="1234",
               merchant_norm="foodpanda pk", brand_token=None),
        # C: no brand, has the tail, too far out to merge with A on time alone.
        ledger("c", 3, at=T0 + timedelta(minutes=50), account_tail="1234",
               merchant_norm="card purchase", brand_token=None),
    ]

    absorbed = await reconcile.merge_pass("u1", now=T0 + timedelta(hours=1))

    assert absorbed == 2, "the third leg did not merge onto the enriched survivor"
    assert len(store["txns"]) == 1
