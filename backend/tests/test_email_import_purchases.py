"""Merchant purchase receipts (foodpanda, Anomaly, any store) get imported too.

Locks in the "open the gate" behaviour: receipts from non-bank senders pass the
candidate gate, the Gmail query fetches them, and foreign-currency receipts are
converted to PKR (or skipped when no rate is available) rather than guessed.
"""
from datetime import datetime, timezone

import pytest

from app.services.email_import import llm
from app.services.email_import.senders import (
    gmail_query,
    is_candidate,
    looks_like_purchase,
)

FOODPANDA_BODY = (
    "foodpanda Order receipt. Order number: js22-2625-8ou4. "
    "Order date: 2026-06-17. Fajita Sizzler Pizza. Total PKR 879.80. "
    "Payment method: Credit Card PKR 879.80"
)
ANOMALY_BODY = "Receipt from Anomaly US$5.00 Paid on July 2, 2026. Receipt number 2458-7298"


def test_purchase_gate_accepts_pkr_receipt():
    assert looks_like_purchase("Thanks for your order!", FOODPANDA_BODY)


def test_purchase_gate_accepts_usd_receipt():
    assert looks_like_purchase("Receipt from Anomaly", ANOMALY_BODY)


def test_purchase_gate_rejects_promo_without_amount():
    # Has the "your order" keyword but no price -> marketing, not a receipt.
    assert not looks_like_purchase("50% off your order this weekend!", "Grab the deal now")


def test_purchase_gate_rejects_otp_even_with_amount():
    assert not looks_like_purchase(
        "Your OTP", "Your one-time password for the PKR 500 order is 123456"
    )


def test_non_finance_sender_receipt_is_candidate():
    assert is_candidate("foodpanda <no-reply@mail.foodpanda.pk>", "Thanks for your order!", FOODPANDA_BODY)
    assert is_candidate("Anomaly <invoice+statements@anoma.ly>", "Receipt from Anomaly", ANOMALY_BODY)


def test_non_finance_sender_non_receipt_is_not_candidate():
    assert not is_candidate("a.friend@gmail.com", "Lunch?", "Are you free at 1pm")


def test_gmail_query_fetches_receipts_and_keeps_banks():
    query = gmail_query(0, now=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc))
    assert "from:meezanbank.com" in query      # banks still fetched
    assert '"order receipt"' in query          # store receipts now fetched too
    assert '"your order"' in query


# ── currency conversion ──────────────────────────────────────────────────────
class _Snap:
    def __init__(self, snap):
        self._snap = snap

    async def __call__(self, *a, **k):
        return self._snap


@pytest.mark.asyncio
async def test_pkr_amount_passes_through(monkeypatch):
    # PKR (and a missing currency) is never converted, even if FX is broken.
    async def boom(*a, **k):
        raise AssertionError("FX must not be called for PKR")

    monkeypatch.setattr(llm, "get_monetary_snapshot", boom)
    assert await llm._to_pkr(879.80, "PKR") == 879.80
    assert await llm._to_pkr(879.80, "") == 879.80


@pytest.mark.asyncio
async def test_usd_amount_converts_to_pkr(monkeypatch):
    monkeypatch.setattr(llm, "get_monetary_snapshot", _Snap({"usd_pkr": 280.0, "rates": {}}))
    assert await llm._to_pkr(5.0, "USD") == 1400.0


@pytest.mark.asyncio
async def test_eur_amount_converts_via_usd(monkeypatch):
    # rates[EUR]=0.9 EUR per USD, usd_pkr=280 -> 10 EUR = 11.11 USD = ~3111 PKR.
    monkeypatch.setattr(llm, "get_monetary_snapshot", _Snap({"usd_pkr": 280.0, "rates": {"EUR": 0.9}}))
    assert round(await llm._to_pkr(10.0, "EUR"), 2) == round(10.0 * 280.0 / 0.9, 2)


@pytest.mark.asyncio
async def test_unconvertible_currency_is_skipped(monkeypatch):
    # No rate for the currency -> None, so the caller skips rather than guesses.
    monkeypatch.setattr(llm, "get_monetary_snapshot", _Snap({"usd_pkr": 280.0, "rates": {}}))
    assert await llm._to_pkr(100.0, "JPY") is None


@pytest.mark.asyncio
async def test_fx_unavailable_skips_foreign(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("providers down")

    monkeypatch.setattr(llm, "get_monetary_snapshot", boom)
    assert await llm._to_pkr(5.0, "USD") is None
