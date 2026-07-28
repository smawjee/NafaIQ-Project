"""Transaction lifecycle: reversals, failed payments, FX provenance, bills.

These cover the states a payment can be in beyond "it happened once and
succeeded" — the states the importer previously either dropped at the gate or
could not tell apart from each other.
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import pytest

from app.services.email_import import pipeline, senders
from app.services.email_import.gmail_client import RawMessage
from app.services.email_import.models import ParsedBill, ParsedTransaction

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def _msg(mid="m1", subject="Transaction alert", body="PKR 879.80 debited", sender="alerts@hbl.com"):
    return RawMessage(
        message_id=mid,
        sender=sender,
        subject=subject,
        body=body,
        received_at=T0,
        internal_date=int(T0.timestamp() * 1000),
        thread_id="t1",
    )


@asynccontextmanager
async def _fake_begin():
    yield object()


# ── the parsed model ─────────────────────────────────────────────────────────


def test_parsed_transaction_carries_fx_provenance():
    """The PKR figure is what gets stored, but the pre-conversion values have to
    survive: the bank's own leg carries an FX markup and will never match the
    converted figure exactly, so correlation needs to know a conversion
    happened."""
    t = ParsedTransaction(
        amount=1402.35, merchant="Anomaly", direction="debit",
        original_amount=5.0, original_currency="USD",
    )
    assert t.original_amount == 5.0
    assert t.original_currency == "USD"


def test_fx_provenance_defaults_to_none_for_pkr():
    t = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    assert t.original_amount is None
    assert t.original_currency is None


def test_is_reversal_defaults_false():
    assert ParsedTransaction(amount=1.0, merchant="x", direction="debit").is_reversal is False


# ── classification ───────────────────────────────────────────────────────────


def test_reversal_is_no_longer_excluded_at_the_gate():
    """Regression: "reversed" sat in EXCLUDE_HINTS, so money genuinely coming
    back to the user was dropped before parsing and never imported. Their
    records showed the charge and no sign of it being returned."""
    assert senders.is_candidate(
        "alerts@hbl.com",
        "Transaction reversed",
        "PKR 879.80 has been reversed and credited to your account ending 1234",
    )


def test_refund_from_a_store_is_a_candidate():
    assert senders.is_candidate(
        "no-reply@mail.foodpanda.pk",
        "Your refund has been processed",
        "We have refunded PKR 879.80 for your order.",
    )


def test_classify_failed():
    assert senders.classify("Transaction declined", "your payment was declined") == "failed"


def test_classify_reversal():
    assert senders.classify("Refund processed", "PKR 500 refunded") == "reversal"


def test_classify_normal():
    assert senders.classify("Transaction alert", "PKR 500 debited") == "normal"


def test_failed_refund_is_a_failure_not_a_refund():
    """Order matters: "your refund could not be processed" contains both
    vocabularies. Treating it as a refund would credit money that never
    arrived."""
    assert senders.classify("Refund update", "your refund could not be processed") == "failed"


def test_otp_is_still_excluded():
    assert not senders.is_candidate(
        "alerts@hbl.com", "Your OTP", "one-time password 123456 PKR 0"
    )


def test_gmail_query_downloads_refund_mail():
    """A merchant's refund mail carries none of the receipt words, so without
    this it is never even downloaded and no local logic could recover it."""
    q = senders.gmail_query(0)
    assert "refund" in q.lower()


# ── pipeline behaviour ───────────────────────────────────────────────────────


@pytest.fixture
def store(monkeypatch):
    """In-memory transactions + ledger, driven by the real pipeline code."""
    state = {"txns": [], "bills": [], "verdicts": {}, "reversal_target": None}

    async def find_dup(conn, uid, **kw):
        return False

    async def find_dup_bill(conn, uid, correlation_key):
        return any(b.get("correlation_key") == correlation_key for b in state["bills"])

    async def insert_txn(conn, values):
        state["txns"].append(values)
        return {"id": len(state["txns"])}

    async def insert_bill(conn, values):
        state["bills"].append(values)
        return {"id": len(state["bills"])}

    async def find_reversal_target(conn, uid, **kw):
        return state["reversal_target"]

    async def set_verdict(conn, uid, message_id, *, verdict, **kw):
        state["verdicts"][message_id] = {"verdict": verdict, **kw}

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.notifier, "notify_activity", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.notifier, "fire_and_forget", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_bill", find_dup_bill)
    monkeypatch.setattr(pipeline.finance_repo, "insert_transaction_dedup", insert_txn)
    monkeypatch.setattr(pipeline.finance_repo, "insert_bill_dedup", insert_bill)
    monkeypatch.setattr(pipeline.finance_repo, "find_reversal_target", find_reversal_target)
    monkeypatch.setattr(pipeline.ledger_repo, "set_verdict", set_verdict)
    return state


@pytest.mark.asyncio
async def test_failed_payment_creates_no_transaction_but_is_recorded(store):
    """No money moved, so no transaction — but it must still be on record, so
    the successful retry that follows has something to correlate against."""
    result = pipeline.SyncResult()
    msg = _msg("f1", subject="Transaction declined", body="Your payment of PKR 500 was declined")

    await pipeline._process_message("u1", msg, [5], result)

    assert store["txns"] == []
    assert result.failed_txn == 1
    assert store["verdicts"]["f1"]["verdict"] == "failed_txn"


@pytest.mark.asyncio
async def test_failed_then_successful_retry_imports_exactly_once(store, monkeypatch):
    """The classic double-count risk once failures stop being dropped: the
    failure must not import, and the retry must import once."""
    result = pipeline.SyncResult()
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=500.0, merchant="Daraz", direction="debit"),
    )

    await pipeline._process_message(
        "u1", _msg("f1", subject="Payment failed", body="PKR 500 could not be processed"),
        [5], result,
    )
    await pipeline._process_message(
        "u1", _msg("s1", subject="Transaction alert", body="PKR 500 debited"), [5], result,
    )

    assert len(store["txns"]) == 1
    assert result.imported_transactions == 1
    assert result.failed_txn == 1


@pytest.mark.asyncio
async def test_reversal_links_to_the_original_without_mutating_it(store, monkeypatch):
    """A refund is its own offsetting row pointing at the charge. The original
    stays exactly as it was, so the net is right AND the history survives."""
    store["reversal_target"] = 41
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=879.80, merchant="foodpanda", direction="credit"),
    )
    result = pipeline.SyncResult()

    await pipeline._process_message(
        "u1", _msg("r1", subject="Refund processed", body="PKR 879.80 refunded to you"),
        [5], result,
    )

    assert len(store["txns"]) == 1
    row = store["txns"][0]
    assert row["transaction_type"] == "income"
    assert row["reverses_transaction_id"] == 41


@pytest.mark.asyncio
async def test_reversal_with_no_findable_original_still_imports(store, monkeypatch):
    """Money coming back is real whether or not we can find what it reverses.
    Dropping it would be worse than recording it unlinked."""
    store["reversal_target"] = None
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=100.0, merchant="Store", direction="credit"),
    )
    result = pipeline.SyncResult()

    await pipeline._process_message(
        "u1", _msg("r2", subject="Refund processed", body="PKR 100 refunded"), [5], result,
    )

    assert len(store["txns"]) == 1
    assert store["txns"][0].get("reverses_transaction_id") is None


@pytest.mark.asyncio
async def test_account_tail_is_persisted(store, monkeypatch):
    """It was parsed and thrown away before — it only reached the notification
    text — yet it is the signal that ties a bank leg to a merchant leg."""
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit"),
    )
    result = pipeline.SyncResult()

    await pipeline._process_message(
        "u1", _msg("a1", body="PKR 879.80 debited from account ending 1234"), [5], result,
    )

    assert store["txns"][0]["account_tail"] == "1234"


@pytest.mark.asyncio
async def test_order_ref_is_persisted(store, monkeypatch):
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit"),
    )
    result = pipeline.SyncResult()

    await pipeline._process_message(
        "u1", _msg("o1", subject="Order #FP-88213", body="PKR 879.80 debited"), [5], result,
    )

    assert store["txns"][0]["order_ref"] == "FP88213"


@pytest.mark.asyncio
async def test_invoice_and_its_reminder_create_one_bill(store, monkeypatch):
    """PTCL sends the invoice, then a reminder days later: two Gmail messages,
    one obligation. Only email_message_id was deduped before, so both landed."""
    bill = ParsedBill(amount=3200.0, name="PTCL Internet", due_date=date(2026, 7, 5))
    monkeypatch.setattr(pipeline.rules, "parse", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.rules, "parse_bill", lambda *a, **k: bill)
    result = pipeline.SyncResult()

    await pipeline._process_message("u1", _msg("b1", sender="billing@ptcl.com.pk"), [5], result)
    await pipeline._process_message("u1", _msg("b2", sender="billing@ptcl.com.pk"), [5], result)

    assert len(store["bills"]) == 1
    assert result.imported_bills == 1
    assert store["verdicts"]["b2"]["verdict"] == "duplicate"


@pytest.mark.asyncio
async def test_a_different_due_date_is_a_different_bill(store, monkeypatch):
    """Next month's PTCL bill is a real, separate obligation."""
    bills = iter([
        ParsedBill(amount=3200.0, name="PTCL Internet", due_date=date(2026, 7, 5)),
        ParsedBill(amount=3200.0, name="PTCL Internet", due_date=date(2026, 8, 5)),
    ])
    monkeypatch.setattr(pipeline.rules, "parse", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.rules, "parse_bill", lambda *a, **k: next(bills))
    result = pipeline.SyncResult()

    await pipeline._process_message("u1", _msg("b1", sender="billing@ptcl.com.pk"), [5], result)
    await pipeline._process_message("u1", _msg("b2", sender="billing@ptcl.com.pk"), [5], result)

    assert len(store["bills"]) == 2


# ── a suppressed duplicate still hands over what it knows ────────────────────


@pytest.mark.asyncio
async def test_a_suppressed_duplicate_donates_its_order_ref(monkeypatch):
    """foodpanda's order-confirmation may carry no order ref while the receipt
    that follows does. The receipt is correctly dropped as a duplicate -- the
    charge is already recorded -- but its ref must NOT go with it, or the bank
    leg later has to merge on weaker evidence than a decisive ref.
    """
    calls = {}

    async def find_dup(conn, uid, **kw):
        return True  # the charge is already on record

    async def fill(conn, uid, **kw):
        calls.update(kw)
        return True

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "fill_missing_correlation_fields", fill)

    parsed = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    txn_id = await pipeline._import_transaction(
        object(), "u1",
        _msg("fp-2", subject="Your order receipt",
             body="Order #FP-88213. Total PKR 879.80 paid from card ending 1234"),
        parsed,
    )

    assert txn_id is None                       # still suppressed, no second row
    assert calls["order_ref"] == "FP88213"      # but the ref was handed over
    assert calls["account_tail"] == "1234"


@pytest.mark.asyncio
async def test_a_suppressed_duplicate_with_nothing_to_add_writes_nothing(monkeypatch):
    """No signals to donate -> no pointless UPDATE against the user's data."""
    called = []

    async def find_dup(conn, uid, **kw):
        return True

    async def fill(conn, uid, **kw):
        called.append(kw)
        return False

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "fill_missing_correlation_fields", fill)

    parsed = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    await pipeline._import_transaction(
        object(), "u1",
        _msg("fp-3", subject="Your order", body="Your order has been delivered."),
        parsed,
    )

    assert called == []


@pytest.mark.asyncio
async def test_enrichment_failure_never_fails_the_poll(monkeypatch):
    """Enrichment is an optimisation for a LATER merge. If it blows up, the
    duplicate was still correctly suppressed and the poll must carry on."""
    async def find_dup(conn, uid, **kw):
        return True

    async def boom(conn, uid, **kw):
        raise RuntimeError("column vanished")

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "fill_missing_correlation_fields", boom)

    parsed = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    assert await pipeline._import_transaction(
        object(), "u1",
        _msg("fp-4", subject="Order #FP-88213 receipt", body="Total PKR 879.80"),
        parsed,
    ) is None
