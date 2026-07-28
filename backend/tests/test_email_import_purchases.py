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


# ── merchant receipt parsing (rules.parse_receipt) ───────────────────────────
# A store's receipt uses none of the bank vocabulary rules.parse needs, so
# before this every one of them fell through to the LLM -- unimportable when the
# LLM was unconfigured, down, or out of poll budget, and a model call each time.
from datetime import datetime, timezone  # noqa: E402

from app.services.email_import import rules  # noqa: E402

_AT = datetime(2026, 7, 4, tzinfo=timezone.utc)
_PANDA = "foodpanda <no-reply@mail.foodpanda.pk>"


def test_receipt_parses_with_merchant_from_the_sending_domain():
    """The merchant is whoever sent it -- far more reliable than regexing a name
    out of marketing copy, and merchant-agnostic: no store is named in the code."""
    t = rules.parse_receipt(
        "Thanks for your order!",
        "Order #FP-88213 confirmed. Order total PKR 879.80",
        _AT, sender=_PANDA,
    )
    assert t is not None
    assert t.merchant.lower() == "foodpanda"
    assert t.amount == 879.80
    assert t.direction == "debit"
    assert t.order_ref == "FP88213"


def test_receipt_prefers_the_total_over_the_subtotal():
    """Picking the subtotal would under-record every order that has a fee."""
    t = rules.parse_receipt(
        "Your order receipt",
        "Subtotal PKR 750.00\nDelivery fee PKR 129.80\nOrder total PKR 879.80",
        _AT, sender=_PANDA,
    )
    assert t is not None and t.amount == 879.80


def test_receipt_never_picks_a_fee_or_discount_line():
    t = rules.parse_receipt(
        "Your order receipt",
        "Discount PKR 100.00\nTotal PKR 879.80",
        _AT, sender=_PANDA,
    )
    assert t is not None and t.amount == 879.80


def test_bare_subtotal_is_not_treated_as_a_total():
    """`(?<!sub)total` -- 'Subtotal' must not satisfy the 'total' label."""
    t = rules.parse_receipt("Your order receipt", "Subtotal PKR 750.00", _AT, sender=_PANDA)
    assert t is None


def test_receipt_parser_never_touches_a_bank_alert():
    """Bank mail is rules.parse's job. One this module rejected is one we do not
    understand well enough to guess at."""
    assert rules.parse_receipt(
        "Transaction alert",
        "Your purchase total PKR 879.80 was debited",
        _AT, sender="alerts@hbl.com",
    ) is None


def test_store_refund_receipt_is_a_credit():
    t = rules.parse_receipt(
        "Your refund has been processed",
        "We have refunded your order. Total PKR 879.80",
        _AT, sender=_PANDA,
    )
    assert t is not None and t.direction == "credit"


def test_promo_with_a_total_but_no_receipt_wording_is_ignored():
    assert rules.parse_receipt(
        "50% off this weekend!",
        "Spend a total of PKR 2,000 and save big",
        _AT, sender=_PANDA,
    ) is None


def test_receipt_without_any_amount_is_ignored():
    assert rules.parse_receipt(
        "Thanks for your order!", "Your order is on its way.", _AT, sender=_PANDA
    ) is None


def test_receipt_confidence_is_below_a_bank_template():
    t = rules.parse_receipt("Your order receipt", "Total PKR 100.00", _AT, sender=_PANDA)
    assert t is not None and t.confidence < 1.0


# ── regressions found by dry-running against REAL mailboxes ──────────────────
# Every fixture above was written from patterns already in the code, so none of
# them could surface these. Both were found by running the real parsers over
# real Gmail bodies.


def test_a_cashback_promo_is_not_parsed_as_a_transaction():
    """FOUND IN PRODUCTION. A Bank Alfalah cashback promo -- "spend ... from 1st
    May to 31st May and get up to PKR 20,000 cashback" -- parsed as a PKR 20,000
    CREDIT from a merchant called "31st May", injecting phantom income into the
    user's finances. A date is never a counterparty; rejecting it sends the mail
    to the LLM, which classifies promos as non-transactions.
    """
    assert rules.parse(
        "Don't Miss Out on Your Cashback on Your Card",
        "Spend with your Bank Alfalah card from 1st May to 31st May and get up "
        "to PKR 20,000 cashback credited to your account.",
        _AT, sender="promo@bankalfalah.com",
    ) is None


def test_date_like_merchants_are_rejected():
    from app.services.email_import.sanitize import is_valid_merchant

    for bad in ("31st May", "1st May", "May 2026", "December", "12/05/2026",
                "2026-05-12", "Jun 3"):
        assert not is_valid_merchant(bad), f"{bad!r} was accepted as a merchant"


def test_a_real_merchant_containing_a_month_word_still_passes():
    """The date guard must not swallow legitimate names."""
    from app.services.email_import.sanitize import is_valid_merchant

    assert is_valid_merchant("May Flower Restaurant")
    assert is_valid_merchant("March Boutique Lahore")


def test_a_forwarded_receipt_is_not_filed_against_the_mail_provider():
    """FOUND IN PRODUCTION. A user forwards a receipt to themselves, so the From
    header is their own gmail.com address and the domain brand became "Gmail" --
    the purchase was filed against a merchant called Gmail. Defer to the LLM,
    which can read the forwarded body, rather than inventing a merchant."""
    assert rules.parse_receipt(
        "Fwd: Thanks for your order!",
        "Order receipt. Order total PKR 930.80",
        _AT, sender="someone@gmail.com",
    ) is None


def test_freemail_domains_never_supply_a_brand_token():
    from app.services.email_import.correlate import brand_token

    assert brand_token("card purchase", "gmail.com") is None
    assert brand_token("card purchase", "outlook.com") is None
    # A real merchant domain still does.
    assert brand_token("card purchase", "orders.anomaly.pk") == "anomaly"
