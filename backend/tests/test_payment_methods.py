"""Payment-method resolution — turning spoken phrases into picker labels.

The assistant hears "add transaction of food via Meezan bank card" and must
produce exactly the string the transaction form's account picker would have
sent (`source: "Meezan Debit"`). The interesting cases are the near-miss
("Meezan Debit" vs "Meezan Savings") and the genuinely ambiguous bare brand,
where guessing is worse than asking.
"""
import pytest

from app.services.finance.payment_methods import (
    PAYMENT_METHODS,
    canonical_payment_method,
    match_payment_methods,
)


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("Meezan bank card", "Meezan Debit"),
        ("meezan card", "Meezan Debit"),
        ("my meezan debit card", "Meezan Debit"),
        ("meezan savings", "Meezan Savings"),
        ("meezan savings account", "Meezan Savings"),
        ("HBL", "HBL Current"),
        ("hbl current account", "HBL Current"),
        ("easypaisa", "Easypaisa"),
        ("easy paisa", "Easypaisa"),
    ],
)
def test_spoken_phrases_resolve(phrase, expected):
    assert canonical_payment_method(phrase) == expected


def test_card_beats_the_near_miss():
    # The whole point: "card" must pull toward Debit, not tie with Savings.
    # A tie here would surface as an unnecessary follow-up question.
    assert match_payment_methods("meezan bank card") == ["Meezan Debit"]


def test_bare_brand_is_ambiguous_not_guessed():
    # Two Meezan methods exist; "meezan" alone cannot pick one. Returning both
    # is the signal the agent needs to ask instead of silently choosing.
    matches = match_payment_methods("meezan")
    assert sorted(matches) == ["Meezan Debit", "Meezan Savings"]
    assert canonical_payment_method("meezan") is None


def test_no_match_returns_nothing():
    assert match_payment_methods("bitcoin wallet") == []
    assert canonical_payment_method("bitcoin wallet") is None


def test_stopwords_alone_do_not_match():
    # "via my bank account" carries no brand — must not resolve to whichever
    # label happens to sort first.
    assert match_payment_methods("via my bank account") == []


def test_empty_is_safe():
    assert match_payment_methods("") == []
    assert match_payment_methods(None) == []
    assert canonical_payment_method(None) is None


def test_labels_are_fixed_points():
    # Every canonical label must resolve to itself, unambiguously.
    for label in PAYMENT_METHODS:
        assert canonical_payment_method(label) == label
