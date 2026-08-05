"""Tests for the live track record.

A track record is only worth having if it cannot flatter itself. These tests
pin the properties that keep it honest: unmeasurable predictions are not scored
as misses, buckets are fixed at prediction time, and counts accumulate rather
than overwrite on a re-run.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.signals.outcomes import (
    BUCKET_WIDTH,
    MaturedOutcome,
    mature_prediction,
    merge_rollup,
    probability_bucket,
    reliability_from_rollup,
    rollup,
)


# --- bucketing ------------------------------------------------------------


def test_probability_rounds_to_the_diagram_bucket():
    assert probability_bucket(0.535) == 0.55
    assert probability_bucket(0.472) == 0.45
    assert probability_bucket(0.50) == 0.50


def test_bucket_rejects_values_outside_a_probability():
    for bad in (None, -0.1, 1.5, "x", float("nan")):
        assert probability_bucket(bad) is None  # type: ignore[arg-type]


def test_bucket_width_is_configurable():
    assert probability_bucket(0.53, width=0.1) == 0.5


# --- maturation -----------------------------------------------------------


def _row(**kw):
    base = {
        "symbol": "hbl",
        "as_of": date(2026, 7, 1),
        "horizon_sessions": 20,
        "prob_bucket": 0.55,
        "close_at_prediction": 100.0,
    }
    base.update(kw)
    return base


def test_rise_is_recorded_as_a_hit():
    out = mature_prediction(_row(), close_now=110.0)
    assert out is not None
    assert out.outcome is True
    assert out.realized_return == pytest.approx(0.10)
    assert out.symbol == "HBL", "symbol is normalised"


def test_fall_is_recorded_as_a_miss():
    out = mature_prediction(_row(), close_now=90.0)
    assert out.outcome is False
    assert out.realized_return == pytest.approx(-0.10)


def test_flat_move_is_not_a_hit():
    """The measured event is 'rose', so unchanged must not count as a rise."""
    out = mature_prediction(_row(), close_now=100.0)
    assert out.outcome is False


def test_unmeasurable_prediction_is_left_pending_not_counted_as_a_miss():
    """Counting 'we could not price it' as a failure would understate
    calibration for reasons that have nothing to do with the model."""
    assert mature_prediction(_row(), close_now=None) is None
    assert mature_prediction(_row(), close_now=0.0) is None
    assert mature_prediction(_row(close_at_prediction=None), close_now=100.0) is None
    assert mature_prediction(_row(close_at_prediction=-5), close_now=100.0) is None


# --- rollup ---------------------------------------------------------------


def _outcome(bucket: float, hit: bool, horizon: int = 20) -> MaturedOutcome:
    return MaturedOutcome(
        symbol="X", as_of=date(2026, 7, 1), horizon_sessions=horizon,
        prob_bucket=bucket, realized_return=0.01 if hit else -0.01, outcome=hit,
    )


def test_rollup_counts_by_horizon_and_bucket():
    rows = rollup([
        _outcome(0.55, True), _outcome(0.55, True), _outcome(0.55, False),
        _outcome(0.45, False),
    ])
    by_bucket = {r["prob_bucket"]: r for r in rows}
    assert by_bucket[0.55]["n"] == 3 and by_bucket[0.55]["hits"] == 2
    assert by_bucket[0.45]["n"] == 1 and by_bucket[0.45]["hits"] == 0


def test_rollup_separates_horizons():
    rows = rollup([_outcome(0.55, True, horizon=5), _outcome(0.55, True, horizon=20)])
    assert len(rows) == 2


def test_rollup_drops_outcomes_without_a_bucket():
    """A prediction with no probability carries no calibration information and
    must not dilute the denominator."""
    rows = rollup([_outcome(0.55, True), MaturedOutcome(
        symbol="X", as_of=date(2026, 7, 1), horizon_sessions=20,
        prob_bucket=None, realized_return=0.5, outcome=True,
    )])
    assert len(rows) == 1
    assert rows[0]["n"] == 1


def test_rollup_of_nothing_is_empty():
    assert rollup([]) == []


# --- merge ----------------------------------------------------------------


def test_merge_accumulates_so_a_rerun_does_not_lose_counts():
    existing = {"n": 10, "hits": 6}
    merged = merge_rollup(existing, {"prob_bucket": 0.55, "n": 4, "hits": 3})
    assert merged["n"] == 14 and merged["hits"] == 9


def test_merge_without_an_existing_row_is_the_addition():
    addition = {"prob_bucket": 0.55, "n": 4, "hits": 3}
    assert merge_rollup(None, addition) == addition


# --- reliability ----------------------------------------------------------


def test_reliability_reports_predicted_against_actual():
    rows = [{"prob_bucket": 0.55, "n": 100, "hits": 52}]
    result = reliability_from_rollup(rows, min_n=30)
    entry = result["reliability"][0]
    assert entry["predicted"] == 0.55
    assert entry["actual"] == pytest.approx(0.52)
    assert entry["gap"] == pytest.approx(-0.03)


def test_reliability_merges_the_same_bucket_across_days():
    rows = [
        {"prob_bucket": 0.55, "n": 50, "hits": 30},
        {"prob_bucket": 0.55, "n": 50, "hits": 20},
    ]
    result = reliability_from_rollup(rows, min_n=30)
    assert result["reliability"][0]["n"] == 100
    assert result["reliability"][0]["actual"] == pytest.approx(0.50)


def test_thin_buckets_are_withheld_rather_than_shown_as_noise():
    rows = [{"prob_bucket": 0.55, "n": 3, "hits": 3}]
    result = reliability_from_rollup(rows, min_n=30)
    assert result["reliability"] == []
    assert result["ece"] is None


def test_ece_is_weighted_by_observation_count():
    """A big well-calibrated bucket must dominate a small badly-calibrated one."""
    rows = [
        {"prob_bucket": 0.50, "n": 1000, "hits": 500},   # perfect
        {"prob_bucket": 0.60, "n": 40, "hits": 8},       # badly off (0.20)
    ]
    result = reliability_from_rollup(rows, min_n=30)
    assert result["ece"] < 0.02, "the 1000-sample bucket should dominate"


def test_reliability_of_nothing_claims_nothing():
    result = reliability_from_rollup([])
    assert result["reliability"] == []
    assert result["n"] == 0
    assert result["ece"] is None


def test_bucket_width_constant_matches_the_rounding():
    assert probability_bucket(0.5 + BUCKET_WIDTH) == pytest.approx(0.5 + BUCKET_WIDTH)


# --- prediction freshness guard -------------------------------------------
# A prediction is dated from the confirmed bar it was computed on. For a
# delisted symbol that bar can be years old, and recording it would write a
# prediction whose outcome already exists — maturation would resolve it
# instantly from history. That is the exact look-ahead the live record exists
# to rule out.

from app.services.signals.track_record_job import MAX_BAR_AGE_DAYS, is_fresh  # noqa: E402


def test_todays_bar_is_fresh():
    today = date(2026, 8, 5)
    assert is_fresh("2026-08-05", today=today) is True
    assert is_fresh("2026-08-04", today=today) is True


def test_bar_at_the_age_limit_is_still_fresh():
    today = date(2026, 8, 5)
    edge = today - timedelta(days=MAX_BAR_AGE_DAYS)
    assert is_fresh(edge.isoformat(), today=today) is True


def test_stale_symbol_is_rejected():
    """The AASM case: last bar 2024-09-26, would back-date a live prediction."""
    assert is_fresh("2024-09-26", today=date(2026, 8, 5)) is False


def test_bar_just_past_the_limit_is_rejected():
    today = date(2026, 8, 5)
    stale = today - timedelta(days=MAX_BAR_AGE_DAYS + 1)
    assert is_fresh(stale.isoformat(), today=today) is False


def test_future_dated_bar_is_a_data_error_not_freshness():
    assert is_fresh("2026-09-01", today=date(2026, 8, 5)) is False


def test_missing_or_malformed_bar_date_is_rejected():
    for bad in (None, "", "not-a-date", 12345):
        assert is_fresh(bad, today=date(2026, 8, 5)) is False


def test_accepts_a_real_date_object():
    assert is_fresh(date(2026, 8, 4), today=date(2026, 8, 5)) is True
