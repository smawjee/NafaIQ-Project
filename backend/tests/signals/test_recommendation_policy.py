"""Tests for the Tier 1 recommendation ladder.

This decides what a user is told to do with their money, so the properties that
make it defensible are pinned explicitly: thresholds measured against the real
base rate (not 0.50), the whole interval clearing the bar, abstention on
uncertainty, and the buy-side asymmetry the pilot's evidence requires.
"""
from __future__ import annotations

import pytest

from app.services.signals.base_rates import BaseRate
from app.services.signals.policy import (
    BUY_MARGIN,
    MIN_QUALITY_FOR_STRONG,
    MIN_SAMPLE_FOR_CALL,
    SELL_MARGIN,
    STRONG_BUY_MARGIN,
    STRONG_SELL_MARGIN,
    build_recommendation,
)

# The measured PSX 20-session base rate. Deliberately not 0.50.
BASE = 0.472


def _rate(p: float, *, half_width: float = 0.02, n: int = 2000) -> BaseRate:
    return BaseRate(
        p=p, p_lower=max(0.0, p - half_width), p_upper=min(1.0, p + half_width),
        n=n, median_return=0.01, depth=4, basis="stocks after a large recent decline",
        shrunk=False,
    )


def _build(rate, **kw):
    return build_recommendation(base_rate=rate, global_rate=BASE, **kw)


# --- the ladder -----------------------------------------------------------


def test_clearly_positive_cohort_is_a_buy():
    rec = _build(_rate(BASE + BUY_MARGIN + 0.03))
    assert rec.rating == "BUY"


def test_strongly_positive_cohort_is_a_strong_buy():
    rec = _build(_rate(BASE + STRONG_BUY_MARGIN + 0.03), quality_score=80)
    assert rec.rating == "STRONG_BUY"


def test_clearly_negative_cohort_is_a_sell():
    rec = _build(_rate(BASE - SELL_MARGIN - 0.03))
    assert rec.rating == "SELL"


def test_strongly_negative_cohort_is_a_strong_sell():
    rec = _build(_rate(BASE - STRONG_SELL_MARGIN - 0.03), quality_score=80)
    assert rec.rating == "STRONG_SELL"


def test_typical_cohort_holds():
    rec = _build(_rate(BASE))
    assert rec.rating == "HOLD"
    assert rec.abstain_reason == "INTERVAL_STRADDLES_BASE_RATE"


# --- the base rate is not 0.50 -------------------------------------------


def test_a_stock_above_half_but_at_the_base_rate_is_not_a_buy():
    """The trap this whole design exists to avoid.

    The measured base rate is 0.472, so p = 0.50 is merely *typical*. A naive
    'p > 0.5 -> BUY' would issue a buy for an unremarkable stock.
    """
    rec = _build(_rate(0.50, half_width=0.02))
    assert rec.rating == "HOLD"
    assert rec.base_rate == pytest.approx(BASE)


def test_a_stock_below_half_can_still_be_a_buy():
    """Symmetrically: 0.49 is above the 0.472 base rate."""
    rec = _build(_rate(BASE + BUY_MARGIN + 0.02, half_width=0.005))
    assert rec.p < 0.55
    assert rec.rating in {"BUY", "STRONG_BUY"}


# --- the whole interval must clear ---------------------------------------


def test_wide_interval_abstains_even_with_a_promising_point_estimate():
    """Uncertainty must cost you the call, not be rounded away."""
    confident = _build(_rate(BASE + 0.08, half_width=0.02))
    uncertain = _build(_rate(BASE + 0.08, half_width=0.15))
    assert confident.rating in {"BUY", "STRONG_BUY"}
    assert uncertain.rating == "HOLD"


def test_buys_are_judged_on_the_lower_bound():
    rec = _build(_rate(BASE + STRONG_BUY_MARGIN + 0.001, half_width=0.05),
                 quality_score=90)
    # Point estimate clears the strong bar; the lower bound does not.
    assert rec.rating != "STRONG_BUY"


def test_sells_are_judged_on_the_upper_bound():
    rec = _build(_rate(BASE - STRONG_SELL_MARGIN - 0.001, half_width=0.05),
                 quality_score=90)
    assert rec.rating != "STRONG_SELL"


# --- asymmetry ------------------------------------------------------------


def test_sell_side_bar_is_easier_than_buy_side():
    """The pilot measured the reversal effect running mostly through the short
    side (holdout: winners -2.52%, losers +0.47%), so sell calls face a smaller
    margin. A symmetric deviation must therefore reach SELL before it reaches BUY.
    """
    assert SELL_MARGIN < BUY_MARGIN
    assert STRONG_SELL_MARGIN < STRONG_BUY_MARGIN

    # A deviation strictly between the two bars, with an interval tight enough
    # that the bound-vs-bar comparison is not decided at the boundary.
    delta = (BUY_MARGIN + SELL_MARGIN) / 2
    up = _build(_rate(BASE + delta, half_width=0.002))
    down = _build(_rate(BASE - delta, half_width=0.002))
    assert down.rating == "SELL"
    assert up.rating == "HOLD", "the same deviation upward must not yet buy"


def test_recommendation_declares_its_asymmetry():
    assert _build(_rate(BASE)).asymmetric is True


# --- guards ---------------------------------------------------------------


def test_thin_cohort_cannot_produce_a_call():
    rec = _build(_rate(0.90, half_width=0.01, n=MIN_SAMPLE_FOR_CALL - 1))
    assert rec.rating == "HOLD"
    assert rec.abstain_reason == "INSUFFICIENT_COHORT"


def test_strong_rungs_require_a_clean_measurement():
    poor = _build(_rate(BASE + STRONG_BUY_MARGIN + 0.05),
                  quality_score=MIN_QUALITY_FOR_STRONG - 10)
    good = _build(_rate(BASE + STRONG_BUY_MARGIN + 0.05),
                  quality_score=MIN_QUALITY_FOR_STRONG + 10)
    assert poor.rating == "BUY"
    assert good.rating == "STRONG_BUY"


def test_missing_calibration_holds_rather_than_guessing():
    rec = build_recommendation(base_rate=None, global_rate=BASE)
    assert rec.rating == "HOLD"
    assert rec.abstain_reason == "NO_CALIBRATION_DATA"


def test_missing_global_rate_holds():
    rec = build_recommendation(base_rate=_rate(0.9), global_rate=None)
    assert rec.rating == "HOLD"
    assert rec.abstain_reason == "NO_CALIBRATION_DATA"


# --- payload --------------------------------------------------------------


def test_recommendation_carries_its_evidence():
    rec = _build(_rate(BASE + 0.10), round_trip_cost=0.0096,
                 suggested_stop_pct=0.08, quality_score=80)
    assert rec.sample_size == 2000
    assert rec.basis and "recent decline" in rec.basis
    assert rec.event.startswith("rose over the next")
    assert rec.round_trip_cost == pytest.approx(0.0096)
    assert rec.suggested_stop_pct == pytest.approx(0.08)
    assert rec.expected_move == pytest.approx(0.01)


def test_every_hold_states_a_reason():
    for p in (BASE, BASE + 0.01, BASE - 0.01):
        rec = _build(_rate(p, half_width=0.005))
        if rec.rating == "HOLD":
            assert rec.abstain_reason, f"HOLD at p={p} must explain itself"


def test_probabilities_stay_in_range():
    for p in (0.01, 0.5, 0.99):
        rec = _build(_rate(p, half_width=0.3))
        assert 0.0 <= rec.p_lower <= rec.p <= rec.p_upper <= 1.0
