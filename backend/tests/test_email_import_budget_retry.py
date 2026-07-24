"""A poll that runs out of LLM budget must RETRY the unparsed candidate next
poll, not skip past it. _parse_message signals that by raising _BudgetExhausted
(transient) instead of returning None (permanent non-transaction).
"""
from datetime import datetime, timezone

import pytest

from app.services.email_import import pipeline
from app.services.email_import.gmail_client import RawMessage
from app.services.email_import.models import ParsedTransaction

_MSG = RawMessage(
    message_id="m1",
    sender="foodpanda <no-reply@mail.foodpanda.pk>",
    subject="Thanks for your order!",
    body="Order receipt. Total PKR 930.80",
    received_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
    internal_date=1_000,
)


@pytest.mark.asyncio
async def test_budget_exhausted_raises_not_skips(monkeypatch):
    # Rules miss, LLM is configured, but budget is 0 -> transient, must raise so
    # the caller leaves the watermark and retries (never silently drops it).
    monkeypatch.setattr(pipeline.rules, "parse", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.rules, "parse_bill", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.llm, "is_configured", lambda: True)
    with pytest.raises(pipeline._BudgetExhausted):
        await pipeline._parse_message(_MSG, [0])


@pytest.mark.asyncio
async def test_no_llm_configured_returns_none(monkeypatch):
    # No LLM at all -> permanent verdict, return None (safe to advance past).
    monkeypatch.setattr(pipeline.rules, "parse", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.rules, "parse_bill", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.llm, "is_configured", lambda: False)
    assert await pipeline._parse_message(_MSG, [0]) is None


@pytest.mark.asyncio
async def test_budget_spent_when_llm_used(monkeypatch):
    txn = ParsedTransaction(amount=930.8, merchant="foodpanda", direction="debit")

    async def fake_llm_parse(*a, **k):
        return txn

    monkeypatch.setattr(pipeline.rules, "parse", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.rules, "parse_bill", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.llm, "is_configured", lambda: True)
    monkeypatch.setattr(pipeline.llm, "parse", fake_llm_parse)
    budget = [2]
    result = await pipeline._parse_message(_MSG, budget)
    assert result is txn
    assert budget[0] == 1  # one LLM parse consumed
