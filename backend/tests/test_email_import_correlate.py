"""Correlation signals and the merge-scoring policy.

The whole reason this module exists: one financial event produces several
emails, and the previous dedup could only collapse them when the merchant
string matched EXACTLY. It never does across sources -- the merchant's own mail
says "foodpanda", the bank's alert for the same charge says "FOODPANDA PK
KARACHI" or falls back to "Card Purchase". So the bank leg always escaped and
the charge landed twice.

These tests pin BOTH directions, which is the only way this feature is safe:
related legs must collapse, and genuinely separate purchases must survive. A
false merge silently deletes money from someone's records, so every test that
asserts "these do NOT merge" is load-bearing.
"""
from datetime import datetime, timedelta, timezone

from app.services.email_import import correlate
from app.services.email_import.correlate import (
    MERGE_THRESHOLD,
    Signals,
    score,
    should_merge,
)

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)


def sig(**kw) -> Signals:
    """A merchant-leg signal set; override only what the case is about."""
    base = dict(
        order_ref=None,
        amount=879.80,
        original_currency=None,
        account_tail=None,
        merchant_norm="foodpanda",
        brand_token="foodpanda",
        occurred_at=T0,
        transaction_type="expense",
    )
    base.update(kw)
    return Signals(**base)


# ── signal extraction ────────────────────────────────────────────────────────


def test_order_ref_from_common_phrasings():
    assert correlate.extract_order_ref("Order #FP-88213 confirmed", "") == "FP88213"
    assert correlate.extract_order_ref("", "Your order id: 4471902") == "4471902"
    assert correlate.extract_order_ref("", "Ref No. AB/123-9") == "AB1239"
    assert correlate.extract_order_ref("", "Transaction ID: 99881234") == "99881234"


def test_order_ref_normalizes_separators_so_legs_match():
    """The merchant writes 'Order #FP-88213', the bank writes 'Ref FP 88213'.
    Same order -- they must reduce to the same token or the decisive signal is
    worthless."""
    assert correlate.extract_order_ref("Order #FP-88213", "") == correlate.extract_order_ref(
        "", "reference fp 88213"
    )


def test_order_ref_absent_returns_none():
    assert correlate.extract_order_ref("Your food is on the way", "") is None


def test_order_ref_rejects_prose_captures():
    """'order number' followed by words, not an identifier. Returning 'has been'
    here would merge two unrelated emails on a 100-point decisive signal."""
    assert correlate.extract_order_ref("", "Your order number has been confirmed") is None


def test_normalize_merchant_strips_noise():
    assert correlate.normalize_merchant("FOODPANDA PK KARACHI") == "foodpanda"
    assert correlate.normalize_merchant("Imtiaz Super Market (Pvt) Ltd") == "imtiaz super market"
    assert correlate.normalize_merchant("POS TPL*FOODPANDA") == "foodpanda"
    assert correlate.normalize_merchant(None) == ""


def test_brand_token_prefers_merchant_then_domain():
    assert correlate.brand_token("foodpanda", "mail.foodpanda.pk") == "foodpanda"
    # Non-finance sender with an unusable merchant: the domain names the brand.
    assert correlate.brand_token("card purchase", "orders.anomaly.pk") == "anomaly"


def test_brand_token_never_claims_a_bank_domain_as_the_merchant():
    """A bank alert's domain names the BANK, not who was paid. Claiming
    'bankalfalah' as the brand would alias-match every Alfalah mail to every
    other -- 55 points of pure noise on unrelated transactions."""
    assert correlate.brand_token("card purchase", "bankalfalah.com") is None


def test_brand_token_rejects_generic_channel_words():
    assert correlate.brand_token("funds transfer", None) is None
    assert correlate.brand_token("atm withdrawal", None) is None


def test_account_tail():
    assert correlate.extract_account_tail("debited from account ending 1234") == "1234"
    assert correlate.extract_account_tail("card xxx2769 used") == "2769"
    assert correlate.extract_account_tail("no account here") is None


# ── scoring ──────────────────────────────────────────────────────────────────


def test_foodpanda_leg_plus_bank_leg_merges():
    """THE bug this feature exists for. The merchant leg names foodpanda; the
    bank leg has no usable merchant at all but carries the card tail. Same
    amount, minutes apart: amount 35 + tail 40 + within-2h 25 = 100."""
    merchant_leg = sig(account_tail="1234")
    bank_leg = sig(
        merchant_norm="card purchase",
        brand_token=None,
        account_tail="1234",
        occurred_at=T0 + timedelta(minutes=8),
    )
    assert score(merchant_leg, bank_leg) >= MERGE_THRESHOLD
    assert should_merge(merchant_leg, bank_leg)


def test_order_ref_is_decisive_alone():
    """A shared order ref outranks everything: different merchant strings, no
    amount on one side, 30 hours apart -- still one event."""
    a = sig(order_ref="FP88213")
    b = sig(
        order_ref="FP88213",
        merchant_norm="tpl khi",
        brand_token=None,
        amount=None,
        occurred_at=T0 + timedelta(hours=30),
    )
    assert should_merge(a, b)


def test_two_same_price_coffees_stay_separate():
    """Same cafe, same price, 3h apart, no shared ref or card tail. These are two
    real purchases. Merging them would delete one from the user's records."""
    a = sig(merchant_norm="cafe kohi", brand_token="kohi", amount=450.0)
    b = sig(
        merchant_norm="cafe kohi",
        brand_token="kohi",
        amount=450.0,
        occurred_at=T0 + timedelta(hours=3),
    )
    assert score(a, b) < MERGE_THRESHOLD
    assert not should_merge(a, b)


def test_same_merchant_same_amount_next_day_stays_separate():
    """The same lunch ordered ~24h later is a genuine repeat."""
    a = sig()
    b = sig(occurred_at=T0 + timedelta(hours=24))
    assert not should_merge(a, b)


def test_opposite_direction_never_merges():
    """A refund and the expense it reverses share every signal including the
    order ref. They must stay two rows that offset -- collapsing them would
    erase both the charge and the money coming back."""
    expense = sig(order_ref="FP88213", transaction_type="expense")
    refund = sig(order_ref="FP88213", transaction_type="income")
    assert score(expense, refund) == 0
    assert not should_merge(expense, refund)


def test_fx_converted_amounts_score_less_than_exact():
    """An FX-converted leg can never equal the bank's own marked-up figure, so
    exact matching cannot correlate them. The tolerant tier bridges that -- but
    scores 20, not 35, so it can never reach 100 on amount+tail+time alone."""
    converted = sig(amount=1402.35, original_currency="USD", account_tail="1234")
    bank_leg = sig(
        amount=1405.00,
        account_tail="1234",
        merchant_norm="card purchase",
        brand_token=None,
        occurred_at=T0 + timedelta(minutes=5),
    )
    s = score(converted, bank_leg)
    assert s == 85  # fx 20 + tail 40 + within-2h 25
    assert not should_merge(converted, bank_leg)


def test_fx_tolerance_does_not_stretch_to_unrelated_amounts():
    """3% absorbs an FX markup. It must not absorb a genuinely different price."""
    a = sig(amount=1000.00, original_currency="USD", account_tail="1234")
    b = sig(amount=1200.00, account_tail="1234", occurred_at=T0 + timedelta(minutes=5))
    assert correlate.POINTS_AMOUNT_FX not in (score(a, b),)
    assert score(a, b) == correlate.POINTS_ACCOUNT_TAIL + correlate.POINTS_WITHIN_2H + correlate.POINTS_MERCHANT_ALIAS


def test_amounts_compare_with_tolerance_not_equality():
    """879.80 has no exact float representation. `==` against a NUMERIC round-trip
    silently misses, which would defeat the dedup entirely."""
    a = sig(amount=879.80)
    b = sig(amount=879.8000000001, account_tail="1234", occurred_at=T0 + timedelta(minutes=1))
    assert should_merge(sig(account_tail="1234"), b)
    assert score(a, b) >= correlate.POINTS_AMOUNT_EXACT


def test_learned_alias_lets_bank_descriptor_merge():
    """'FPANDA KHI' shares no token with 'foodpanda', so normalisation alone can
    never match it. Once an order-ref merge has taught us the pair, it does --
    with no code change. This is what makes the system merchant-agnostic."""
    merchant_leg = sig()
    bank_leg = sig(
        brand_token=None,
        merchant_norm="fpanda khi",
        occurred_at=T0 + timedelta(minutes=5),
    )
    assert not should_merge(merchant_leg, bank_leg)
    assert should_merge(merchant_leg, bank_leg, {("foodpanda", "fpanda khi")})


def test_brand_token_inside_the_other_merchant_string_matches():
    """'foodpanda' appearing as a token of 'foodpanda pk karachi' is the common
    case and must not need a learned alias."""
    a = sig()
    b = sig(
        merchant_norm="foodpanda pk karachi",
        brand_token="foodpanda",
        occurred_at=T0 + timedelta(minutes=5),
    )
    assert should_merge(a, b)


def test_time_bands_do_not_stack():
    """A pair inside 2h scores the 2h band only -- never 2h + 12h."""
    a = sig(account_tail="1234")
    b = sig(account_tail="1234", occurred_at=T0 + timedelta(minutes=30))
    assert score(a, b) == (
        correlate.POINTS_AMOUNT_EXACT
        + correlate.POINTS_ACCOUNT_TAIL
        + correlate.POINTS_MERCHANT_ALIAS
        + correlate.POINTS_WITHIN_2H
    )


def test_missing_signals_score_zero_rather_than_guessing():
    """Two messages sharing nothing but a timestamp must not merge."""
    a = sig(amount=None, brand_token=None, merchant_norm="")
    b = sig(amount=None, brand_token=None, merchant_norm="", occurred_at=T0 + timedelta(minutes=1))
    assert score(a, b) == correlate.POINTS_WITHIN_2H
    assert not should_merge(a, b)
