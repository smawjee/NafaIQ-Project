"""Durability: no email may be lost between fetch and import.

REGRESSION THIS PINS
`sync_user` used to catch an import failure, log it, and then advance the poll
watermark past that message anyway. Gmail is only asked for messages newer than
the watermark, so a transient DB error meant that email was never seen again —
a real transaction silently missing from the user's finances, with nothing
anywhere to indicate it had existed.

The fix has two halves and both are tested here: the message is STAGED before
parsing (so it is on record no matter what happens next), and the watermark
does not advance past a message that has not reached a terminal verdict.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from app.repositories import email_import_messages as ledger_repo
from app.services.email_import import pipeline
from app.services.email_import.gmail_client import RawMessage
from app.services.email_import.models import ParsedTransaction

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def _msg(mid: str, minute: int) -> RawMessage:
    when = T0.replace(minute=minute)
    return RawMessage(
        message_id=mid,
        sender="alerts@hbl.com",
        subject="Transaction alert",
        body="PKR 879.80 debited from account ending 1234",
        received_at=when,
        internal_date=int(when.timestamp() * 1000),
        thread_id=None,
    )


@asynccontextmanager
async def _fake_begin():
    yield object()


@pytest.fixture
def harness(monkeypatch):
    """A whole sync_user run against in-memory stand-ins."""
    state = {
        "ledger": {},        # message_id -> row
        "txns": [],
        "watermark": 0,
        "fail_on": set(),    # message_ids whose import raises
        "messages": [],
    }

    async def fetch_new_messages(token, last_internal_date):
        return [m for m in state["messages"] if m.internal_date > last_internal_date]

    async def stage_message(conn, values):
        mid = values["message_id"]
        if mid in state["ledger"]:
            return state["ledger"][mid], False
        state["ledger"][mid] = {**values, "attempts": 0}
        return state["ledger"][mid], True

    async def get_message(conn, uid, message_id):
        return state["ledger"].get(message_id)

    async def set_verdict(conn, uid, message_id, *, verdict, **kw):
        row = state["ledger"].setdefault(message_id, {"attempts": 0})
        row["verdict"] = verdict
        row["attempts"] = row.get("attempts", 0) + 1
        row["error"] = kw.get("error")

    async def insert_txn(conn, values):
        if values["email_message_id"] in state["fail_on"]:
            raise RuntimeError("pooler connection lost")
        state["txns"].append(values)
        return {"id": len(state["txns"])}

    async def find_dup(conn, uid, **kw):
        return False

    async def update_watermark(conn, uid, mark):
        state["watermark"] = mark

    async def merge_pass(user_id, *, now):
        return 0

    monkeypatch.setattr(pipeline, "begin", _fake_begin)
    monkeypatch.setattr(pipeline, "fetch_new_messages", fetch_new_messages)
    monkeypatch.setattr(pipeline, "decrypt", lambda v: "refresh-token")
    monkeypatch.setattr(pipeline, "refresh_access_token", _async_return("access-token"))
    monkeypatch.setattr(pipeline.notifier, "notify_activity", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.notifier, "fire_and_forget", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.ledger_repo, "stage_message", stage_message)
    monkeypatch.setattr(pipeline.ledger_repo, "get_message", get_message)
    monkeypatch.setattr(pipeline.ledger_repo, "set_verdict", set_verdict)
    monkeypatch.setattr(pipeline.finance_repo, "insert_transaction_dedup", insert_txn)
    monkeypatch.setattr(pipeline.finance_repo, "find_duplicate_transaction", find_dup)
    monkeypatch.setattr(pipeline.integrations_repo, "update_watermark", update_watermark)
    monkeypatch.setattr(pipeline.reconcile, "merge_pass", merge_pass)
    monkeypatch.setattr(
        pipeline.rules, "parse",
        lambda *a, **k: ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit"),
    )
    return state


def _async_return(value):
    async def _fn(*a, **k):
        return value
    return _fn


def _integration(watermark: int = 0) -> dict:
    return {
        "user_id": "u1",
        "refresh_token_enc": "enc",
        "last_internal_date": watermark,
    }


@pytest.mark.asyncio
async def test_message_is_staged_before_it_is_parsed(harness):
    harness["messages"] = [_msg("m1", 1)]

    await pipeline.sync_user(_integration())

    assert "m1" in harness["ledger"]
    assert harness["ledger"]["m1"]["verdict"] == "imported"


@pytest.mark.asyncio
async def test_transient_import_error_does_not_advance_the_watermark(harness):
    """THE regression. m1 fails; the watermark must stay behind it so Gmail
    serves it again next poll."""
    harness["messages"] = [_msg("m1", 1)]
    harness["fail_on"] = {"m1"}

    result = await pipeline.sync_user(_integration())

    assert harness["txns"] == []
    assert harness["watermark"] == 0                      # NOT advanced past m1
    assert harness["ledger"]["m1"]["verdict"] == "parse_error"
    assert result.parse_errors == 1


@pytest.mark.asyncio
async def test_the_failed_message_is_imported_on_the_next_poll(harness):
    """The other half: staying behind the watermark only helps if the retry
    actually re-processes the message rather than skipping it as 'seen'."""
    harness["messages"] = [_msg("m1", 1)]
    harness["fail_on"] = {"m1"}
    await pipeline.sync_user(_integration())
    assert harness["txns"] == []

    harness["fail_on"] = set()  # the blip clears
    result = await pipeline.sync_user(_integration(harness["watermark"]))

    assert len(harness["txns"]) == 1
    assert harness["ledger"]["m1"]["verdict"] == "imported"
    assert result.imported_transactions == 1


@pytest.mark.asyncio
async def test_a_stuck_message_does_not_block_later_ones(harness):
    """m1 fails, but m2 must still import this poll — one bad email cannot hold
    up the rest of the mailbox."""
    harness["messages"] = [_msg("m1", 1), _msg("m2", 2)]
    harness["fail_on"] = {"m1"}

    await pipeline.sync_user(_integration())

    assert len(harness["txns"]) == 1
    assert harness["txns"][0]["email_message_id"] == "m2"
    assert harness["watermark"] == 0  # still behind m1, which is owed a retry


@pytest.mark.asyncio
async def test_an_already_handled_message_is_not_reimported(harness):
    """Re-serving a message whose verdict is terminal must be a no-op, or the
    watermark overlap would double-import on every poll."""
    harness["messages"] = [_msg("m1", 1)]
    await pipeline.sync_user(_integration())

    result = await pipeline.sync_user(_integration())  # same watermark, m1 again

    assert len(harness["txns"]) == 1
    assert result.duplicates == 1


@pytest.mark.asyncio
async def test_retry_ceiling_stops_an_unparseable_message_blocking_forever(harness):
    """A permanently broken email must eventually stop holding the watermark,
    or every later transaction is starved. It stays in the ledger, visible."""
    harness["messages"] = [_msg("m1", 1)]
    harness["fail_on"] = {"m1"}

    for _ in range(ledger_repo.MAX_ATTEMPTS):
        await pipeline.sync_user(_integration(harness["watermark"]))

    assert harness["ledger"]["m1"]["attempts"] >= ledger_repo.MAX_ATTEMPTS
    assert harness["ledger"]["m1"]["verdict"] == "parse_error"

    # One more poll: the ceiling is reached, so it is skipped and the watermark
    # is finally free to move.
    await pipeline.sync_user(_integration(harness["watermark"]))
    assert harness["watermark"] == harness["messages"][0].internal_date


@pytest.mark.asyncio
async def test_non_candidate_mail_advances_the_watermark(harness):
    """Ordinary mail is 'handled' by being ignored; it must not hold the poll."""
    promo = RawMessage(
        message_id="p1", sender="news@example.com", subject="Newsletter",
        body="unsubscribe from this", received_at=T0,
        internal_date=int(T0.timestamp() * 1000), thread_id=None,
    )
    harness["messages"] = [promo]

    await pipeline.sync_user(_integration())

    assert harness["watermark"] == promo.internal_date
    assert harness["ledger"] == {}
