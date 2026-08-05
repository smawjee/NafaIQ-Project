"""Tests for the Tier 1 base-rate probability engine.

This module is the one that ships a number to users labelled as a probability,
so the properties that make that number honest are pinned here: intervals that
widen with uncertainty, thin cells that refuse to shout, and a fallback that
reports what it actually rested on.
"""
from __future__ import annotations

import math

import pytest

from app.services.signals.base_rates import (
    MIN_CELL_N,
    BaseRateTable,
    Sample,
    aggregate,
    cell_key,
    reversal_bucket,
    shrink,
    summarize,
    volatility_band,
    wilson_interval,
)


# --- Wilson interval ------------------------------------------------------


def test_wilson_interval_brackets_the_point_estimate():
    lo, hi = wilson_interval(60, 100)
    assert lo < 0.60 < hi


def test_wilson_interval_narrows_as_evidence_grows():
    """More samples must buy a tighter claim — this is what 'confidence' means."""
    narrow = wilson_interval(600, 1000)
    wide = wilson_interval(6, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_wilson_interval_stays_inside_zero_one_at_the_extremes():
    """The normal approximation fails here; Wilson is used precisely for this."""
    for successes, n in ((0, 5), (5, 5), (0, 1), (1, 1)):
        lo, hi = wilson_interval(successes, n)
        assert 0.0 <= lo <= hi <= 1.0


def test_wilson_interval_with_no_data_claims_nothing():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_perfect_record_on_tiny_sample_does_not_claim_certainty():
    """3-for-3 must not read as 100%."""
    lo, hi = wilson_interval(3, 3)
    assert lo < 0.6, "a 3-sample perfect record should admit real downside"
    assert hi <= 1.0


# --- shrinkage ------------------------------------------------------------


def test_thin_cell_shrinks_toward_parent():
    assert shrink(1.0, 3, 0.5) == pytest.approx(0.5 + 0.5 * (3 / 203), abs=1e-9)


def test_rich_cell_keeps_its_own_estimate():
    assert shrink(0.70, 100_000, 0.50) == pytest.approx(0.70, abs=0.01)


def test_shrinkage_is_monotone_in_sample_size():
    parent, cell = 0.50, 0.90
    values = [shrink(cell, n, parent) for n in (10, 100, 1000, 10_000)]
    assert all(a < b for a, b in zip(values, values[1:]))


def test_empty_cell_returns_the_parent():
    assert shrink(0.9, 0, 0.42) == 0.42


# --- bucketing ------------------------------------------------------------


def test_reversal_buckets_span_the_percentile_range():
    assert reversal_bucket(5) == "big_losers"
    assert reversal_bucket(30) == "losers"
    assert reversal_bucket(50) == "flat"
    assert reversal_bucket(70) == "winners"
    assert reversal_bucket(95) == "big_winners"
    assert reversal_bucket(None) is None


def test_volatility_bands_match_the_trend_state_thresholds():
    assert volatility_band(0.10) == "LOW"
    assert volatility_band(0.35) == "MODERATE"
    assert volatility_band(0.90) == "HIGH"
    assert volatility_band(None) is None


def test_cell_key_is_stable_and_depth_aware():
    kw = dict(reversal="flat", trend="RANGE", volatility="LOW", regime="BULLISH")
    assert cell_key(**kw) == cell_key(**kw)
    assert cell_key(**kw, axes=("reversal",)) == "reversal=flat"
    assert cell_key(**kw, axes=()) == "GLOBAL"
    # A level that omits reversal must key on what it actually conditions on,
    # not on a prefix of the canonical axis order.
    assert cell_key(**kw, axes=("trend", "volatility")) == "trend=RANGE|volatility=LOW"


def test_missing_axis_is_explicit_not_silently_dropped():
    key = cell_key(reversal="flat", trend=None, volatility="LOW", regime=None)
    assert "trend=NA" in key and "regime=NA" in key


# --- summarize / aggregate ------------------------------------------------


def test_summarize_counts_hits_and_returns():
    s = summarize([True, True, False, True], [0.1, 0.2, -0.1, 0.3])
    assert s["n"] == 4 and s["hits"] == 3
    assert s["p"] == pytest.approx(0.75)
    assert s["p_lower"] < 0.75 < s["p_upper"]


def test_summarize_of_nothing_reports_nothing():
    assert summarize([], []) == {"n": 0}


def _samples(n: int, *, reversal: str, outcome_rate: float) -> list[Sample]:
    out = []
    for i in range(n):
        out.append(Sample(
            reversal=reversal, trend="RANGE", volatility="LOW", regime="NEUTRAL",
            outcome=(i % 100) < int(outcome_rate * 100),
            forward_return=0.01 if (i % 100) < int(outcome_rate * 100) else -0.01,
        ))
    return out


def test_aggregate_builds_every_coarsening_level():
    table = aggregate(_samples(500, reversal="big_losers", outcome_rate=0.6))
    assert table["total_samples"] == 500
    assert len(table["levels"]) == 8
    assert table["levels"][-1]["GLOBAL"]["n"] == 500


def test_aggregate_separates_distinct_cells():
    rows = (_samples(400, reversal="big_losers", outcome_rate=0.7)
            + _samples(400, reversal="big_winners", outcome_rate=0.3))
    table = aggregate(rows)
    finest = table["levels"][0]
    losers = [v for k, v in finest.items() if "big_losers" in k][0]
    winners = [v for k, v in finest.items() if "big_winners" in k][0]
    assert losers["p"] > winners["p"]


# --- lookup ---------------------------------------------------------------


def _table(rows: list[Sample]) -> BaseRateTable:
    return BaseRateTable(aggregate(rows))


def test_lookup_uses_the_finest_cell_when_it_has_support():
    t = _table(_samples(2000, reversal="big_losers", outcome_rate=0.62))
    br = t.lookup(reversal="big_losers", trend="RANGE",
                  volatility="LOW", regime="NEUTRAL")
    assert br is not None
    assert br.depth == 4
    assert br.p == pytest.approx(0.62, abs=0.02)
    assert br.n == 2000


def test_lookup_falls_back_when_the_finest_cell_is_thin():
    """A rare combination must borrow strength, and say that it did."""
    rows = _samples(2000, reversal="big_losers", outcome_rate=0.6)
    # One observation in an otherwise unseen regime.
    rows.append(Sample(reversal="big_losers", trend="RANGE", volatility="LOW",
                       regime="HIGH_VOLATILITY", outcome=True, forward_return=0.5))
    t = _table(rows)
    br = t.lookup(reversal="big_losers", trend="RANGE",
                  volatility="LOW", regime="HIGH_VOLATILITY")
    assert br is not None
    assert br.depth < 4, "must not report a 1-sample cell as if it were the answer"
    assert br.n >= MIN_CELL_N


def test_lookup_reports_what_the_number_rests_on():
    t = _table(_samples(2000, reversal="big_losers", outcome_rate=0.6))
    br = t.lookup(reversal="big_losers", trend="RANGE",
                  volatility="LOW", regime="NEUTRAL")
    assert "large recent decline" in br.basis


def test_lookup_returns_none_when_there_is_no_table():
    assert BaseRateTable({}).lookup(reversal="flat", trend="RANGE",
                                    volatility="LOW", regime="NEUTRAL") is None


def test_missing_reversal_axis_still_uses_trend_and_volatility():
    """The reversal percentile comes from a daily precompute and can be absent.

    A symbol ranked after the last cross-section run, or outside the ranked
    universe, has no percentile. That must not throw away the trend, volatility
    and regime information we do have — which is exactly what a prefix-only
    fallback chain did before the axis sets were made explicit.
    """
    t = _table(_samples(3000, reversal="big_losers", outcome_rate=0.62))
    br = t.lookup(reversal=None, trend="RANGE", volatility="LOW", regime="NEUTRAL")
    assert br is not None
    assert br.depth >= 2, "must condition on trend/volatility rather than fall to global"
    assert "trading range" in br.basis
    assert "recent" not in br.basis, "must not claim a reversal cohort it never had"


def test_lookup_on_a_wholly_unknown_state_degrades_to_global():
    t = _table(_samples(1000, reversal="flat", outcome_rate=0.5))
    br = t.lookup(reversal="big_winners", trend="UPTREND",
                  volatility="HIGH", regime="BEARISH")
    assert br is not None
    assert br.depth == 0
    assert "no comparable cohort" in br.basis


def test_interval_is_always_a_valid_probability_range():
    t = _table(_samples(1000, reversal="flat", outcome_rate=0.55))
    br = t.lookup(reversal="flat", trend="RANGE", volatility="LOW", regime="NEUTRAL")
    assert 0.0 <= br.p_lower <= br.p <= br.p_upper <= 1.0 or br.shrunk


def test_load_missing_artifact_returns_none_rather_than_raising(tmp_path):
    assert BaseRateTable.load(tmp_path / "nope.json") is None


def test_load_corrupt_artifact_returns_none_rather_than_raising(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"{not json")
    assert BaseRateTable.load(bad) is None
