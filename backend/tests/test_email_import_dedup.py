"""Content-level dedup for multi-email merchants.

foodpanda sends several mails for ONE order (order-confirmed, receipt,
delivered), each a distinct Gmail message — so the message_id dedup can't
collapse them and the charge landed 2-3 times. `_import_transaction` now skips a
same-amount + same-merchant transaction inside a tight window. These tests pin
BOTH halves: duplicates are collapsed, and genuinely distinct transactions still
import (the "don't drop a real one" guarantee).
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.services.email_import import pipeline
from app.services.email_import.gmail_client import RawMessage
from app.services.email_import.models import ParsedTransaction

_T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def _msg(mid: str, when: datetime) -> RawMessage:
    return RawMessage(
        message_id=mid,
        sender="foodpanda <no-reply@mail.foodpanda.pk>",
        subject="Thanks for your order!",
        body="Order receipt. Total PKR 879.80",
        received_at=when,
        internal_date=int(when.timestamp() * 1000),
    )


@asynccontextmanager
async def _fake_begin():
    yield object()  # conn is never touched — the repo calls are mocked


@pytest.fixture
def store(monkeypatch):
    """In-memory stand-in whose dup check mirrors the repo's amount+merchant+
    window SQL, driven by the REAL window the pipeline passes."""
    rows: list[dict] = []

    async def find_dup(conn, uid, *, merchant, amount, transaction_type, window_lo, window_hi):
        return any(
            r["amount"] == amount
            and r["merchant"].strip().lower() == (merchant or "").strip().lower()
            and r["transaction_type"] == transaction_type
            and window_lo <= r["transaction_date"] <= window_hi
            for r in rows
        )

    async def insert_dedup(conn, values):
        rows.append(values)
        return {"id": len(rows)}

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline.notifier, "notify_activity", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.notifier, "fire_and_forget", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.finance_repo, "insert_transaction_dedup", insert_dedup)
    return rows


@pytest.mark.asyncio
async def test_foodpanda_multi_email_order_imports_once(store):
    parsed = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    # Three mails for ONE order, minutes to an hour apart, distinct message ids.
    assert await pipeline._import_transaction("u1", _msg("m1", _T0), parsed) is True
    assert await pipeline._import_transaction("u1", _msg("m2", _T0 + timedelta(minutes=15)), parsed) is False
    assert await pipeline._import_transaction("u1", _msg("m3", _T0 + timedelta(hours=1)), parsed) is False
    assert len(store) == 1


@pytest.mark.asyncio
async def test_different_amount_still_imports(store):
    a = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    b = ParsedTransaction(amount=1250.00, merchant="foodpanda", direction="debit")
    assert await pipeline._import_transaction("u1", _msg("m1", _T0), a) is True
    # Same merchant, same time, DIFFERENT amount — a real second order, not a dup.
    assert await pipeline._import_transaction("u1", _msg("m2", _T0), b) is True
    assert len(store) == 2


@pytest.mark.asyncio
async def test_same_order_next_day_still_imports(store):
    parsed = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    assert await pipeline._import_transaction("u1", _msg("m1", _T0), parsed) is True
    # The same meal ordered ~24h later is a genuine repeat — outside the 12h
    # window, so it must NOT be swallowed as a duplicate.
    assert await pipeline._import_transaction("u1", _msg("m2", _T0 + timedelta(hours=24)), parsed) is True
    assert len(store) == 2


@pytest.mark.asyncio
async def test_dup_window_is_symmetric_12h(monkeypatch, store):
    seen: dict = {}

    async def capture(conn, uid, *, merchant, amount, transaction_type, window_lo, window_hi):
        seen["lo"], seen["hi"] = window_lo, window_hi
        return False

    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", capture)
    parsed = ParsedTransaction(amount=500.0, merchant="foodpanda", direction="debit")
    await pipeline._import_transaction("u1", _msg("m1", _T0), parsed)
    assert seen["lo"] == _T0 - timedelta(hours=12)
    assert seen["hi"] == _T0 + timedelta(hours=12)
