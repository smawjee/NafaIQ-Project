"""Tests for the Tier 2 validation machinery.

Every failure mode this module guards against inflates a score rather than
depressing it, so a bug here produces a model that looks good and is not. The
tests are written as adversarial checks: construct leakage and assert it is
caught, construct pure noise and assert nothing is claimed.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.signals.validation import (
    average_uniqueness,
    brier_skill_score,
    deflated_sharpe_ratio,
    expected_calibration_error,
    probability_of_backtest_overfitting,
    purged_kfold,
    rank_ic,
)


# --- purged k-fold --------------------------------------------------------


def test_folds_cover_the_sample_without_overlapping_each_other():
    times = np.arange(500)
    folds = list(purged_kfold(times, n_splits=5, horizon=20))
    assert len(folds) == 5
    seen = np.concatenate([f.test for f in folds])
    assert len(seen) == len(set(seen.tolist())), "test folds must be disjoint"


def test_training_samples_whose_label_touches_the_test_window_are_purged():
    """The core defence: a 20-day label ending inside the test window shares
    prices with it, and would let the model partly see the answer."""
    times = np.arange(300)
    horizon = 20
    for fold in purged_kfold(times, n_splits=3, horizon=horizon, embargo=0):
        test_start, test_end = times[fold.test].min(), times[fold.test].max()
        train_times = times[fold.train]
        label_end = train_times + horizon
        overlapping = (label_end >= test_start) & (train_times <= test_end)
        assert not overlapping.any(), "a training label overlapped the test window"


def test_embargo_removes_the_band_immediately_after_the_test_window():
    times = np.arange(300)
    embargo = 15
    for fold in purged_kfold(times, n_splits=3, horizon=5, embargo=embargo):
        test_end = times[fold.test].max()
        train_times = times[fold.train]
        in_band = (train_times > test_end) & (train_times <= test_end + embargo)
        assert not in_band.any()


def test_zero_horizon_still_produces_usable_folds():
    folds = list(purged_kfold(np.arange(100), n_splits=4, horizon=0, embargo=0))
    assert len(folds) == 4
    assert all(f.train.size > 0 for f in folds)


def test_empty_or_degenerate_input_yields_nothing():
    assert list(purged_kfold(np.asarray([]), n_splits=5, horizon=20)) == []
    assert list(purged_kfold(np.arange(10), n_splits=1, horizon=5)) == []


def test_negative_horizon_is_rejected():
    with pytest.raises(ValueError):
        list(purged_kfold(np.arange(10), horizon=-1))


# --- average uniqueness ---------------------------------------------------


def test_non_overlapping_labels_are_fully_unique():
    times = np.arange(0, 100, 20)
    weights = average_uniqueness(times, horizon=19)
    assert np.allclose(weights, 1.0, atol=1e-9)


def test_heavily_overlapping_labels_are_heavily_discounted():
    """20 consecutive daily samples with a 20-day label share nearly all of
    their outcome; treating them as 20 independent observations is what
    overstates every downstream statistic."""
    times = np.arange(200)
    weights = average_uniqueness(times, horizon=20)
    assert weights.mean() < 0.15, f"expected heavy discount, got {weights.mean():.3f}"
    assert (weights > 0).all() and (weights <= 1.0 + 1e-9).all()


def test_uniqueness_increases_as_overlap_falls():
    times = np.arange(200)
    dense = average_uniqueness(times, horizon=40).mean()
    sparse = average_uniqueness(times, horizon=5).mean()
    assert sparse > dense


def test_uniqueness_handles_empty_and_zero_horizon():
    assert average_uniqueness(np.asarray([]), horizon=20).size == 0
    assert np.allclose(average_uniqueness(np.arange(5), horizon=0), 1.0)


# --- deflated Sharpe ------------------------------------------------------


# Sharpe must be in the SAME frequency as the observation count. These use
# per-day values: 0.05/day is roughly 0.8 annualised, a strong but believable
# result. Passing an annualised figure against daily counts overstates
# significance by ~sqrt(252) and saturates the function at 1.0.
DAILY_SHARPE = 0.05


def test_single_trial_with_a_strong_sharpe_is_credible():
    dsr = deflated_sharpe_ratio(DAILY_SHARPE, n_trials=1, n_observations=2000)
    assert dsr > 0.95


def test_the_same_sharpe_is_discounted_after_many_trials():
    """Best-of-many is biased upward by construction; that is the whole point."""
    few = deflated_sharpe_ratio(DAILY_SHARPE, n_trials=1, n_observations=500)
    many = deflated_sharpe_ratio(DAILY_SHARPE, n_trials=500, n_observations=500)
    assert many < few
    assert many < 0.95, "a best-of-500 result must not pass the gate on its own"


def test_more_trials_monotonically_reduce_credibility():
    values = [
        deflated_sharpe_ratio(DAILY_SHARPE, n_trials=t, n_observations=1000)
        for t in (1, 10, 100, 1000)
    ]
    assert all(a >= b for a, b in zip(values, values[1:])), values


def test_zero_sharpe_is_never_credible():
    assert deflated_sharpe_ratio(0.0, n_trials=50, n_observations=500) < 0.5


def test_degenerate_inputs_return_zero_rather_than_a_pass():
    assert deflated_sharpe_ratio(2.0, n_trials=1, n_observations=1) == 0.0
    assert deflated_sharpe_ratio(2.0, n_trials=0, n_observations=100) == 0.0


# --- PBO ------------------------------------------------------------------


def test_pure_noise_configurations_have_high_overfitting_probability():
    rng = np.random.default_rng(0)
    performance = rng.normal(size=(200, 20))
    pbo = probability_of_backtest_overfitting(performance, n_partitions=6)
    assert pbo > 0.3, f"noise should look overfit, got {pbo:.2f}"


def test_a_genuinely_superior_configuration_has_low_overfitting_probability():
    rng = np.random.default_rng(1)
    performance = rng.normal(size=(200, 10)) * 0.2
    performance[:, 3] += 1.0          # one config is really better
    pbo = probability_of_backtest_overfitting(performance, n_partitions=6)
    assert pbo < 0.1


def test_pbo_of_a_single_configuration_is_uninformative():
    assert probability_of_backtest_overfitting(np.zeros((10, 1))) == 1.0


# --- calibration ----------------------------------------------------------


def test_perfectly_calibrated_probabilities_score_near_zero_error():
    rng = np.random.default_rng(2)
    p = rng.uniform(0.05, 0.95, 20000)
    y = rng.uniform(size=20000) < p
    assert expected_calibration_error(p, y) < 0.02


def test_systematically_overconfident_probabilities_are_caught():
    rng = np.random.default_rng(3)
    p = np.full(5000, 0.9)
    y = rng.uniform(size=5000) < 0.5      # claims 90%, delivers 50%
    assert expected_calibration_error(p, y) > 0.3


def test_calibration_error_of_nothing_claims_nothing():
    assert expected_calibration_error([], []) == 1.0


# --- Brier skill ----------------------------------------------------------


def test_beating_the_reference_scores_positive():
    y = np.asarray([True] * 70 + [False] * 30)
    good = np.full(100, 0.7)
    assert brier_skill_score(good, y, 0.5) > 0


def test_losing_to_the_reference_scores_negative():
    y = np.asarray([True] * 70 + [False] * 30)
    bad = np.full(100, 0.2)
    assert brier_skill_score(bad, y, 0.7) < 0


def test_reference_may_be_a_per_sample_forecast():
    """Tier 2 must beat Tier 1's *conditional* rates, not a flat constant."""
    y = np.asarray([True, False, True, False])
    reference = np.asarray([0.6, 0.4, 0.6, 0.4])
    model = np.asarray([0.9, 0.1, 0.9, 0.1])
    assert brier_skill_score(model, y, reference) > 0


# --- rank IC --------------------------------------------------------------


def test_rank_ic_recovers_perfect_and_inverted_orderings():
    x = np.arange(50, dtype=float)
    assert rank_ic(x, x) == pytest.approx(1.0)
    assert rank_ic(x, -x) == pytest.approx(-1.0)


def test_rank_ic_of_noise_is_near_zero():
    rng = np.random.default_rng(4)
    assert abs(rank_ic(rng.normal(size=2000), rng.normal(size=2000))) < 0.1


def test_rank_ic_tolerates_missing_values():
    x = np.asarray([1.0, np.nan, 3.0, 4.0])
    y = np.asarray([1.0, 2.0, np.nan, 4.0])
    assert np.isfinite(rank_ic(x, y))


# --- panel uniqueness -----------------------------------------------------


def test_panel_uniqueness_ignores_same_day_cross_section():
    """148 stocks on one day are 148 observations, not 148 overlaps.

    Feeding a panel to the single-series version reported uniqueness of ~1/2960
    instead of ~1/20 and turned the weights into near-uniform noise.
    """
    from app.services.signals.validation import panel_average_uniqueness

    dates = np.repeat(np.arange(200), 150)          # 150 symbols per day
    panel_w = panel_average_uniqueness(dates, horizon=20)
    naive_w = average_uniqueness(dates, horizon=20)

    assert panel_w.mean() == pytest.approx(1 / 20, abs=0.02)
    assert naive_w.mean() < 0.001
    assert panel_w.mean() > naive_w.mean() * 50


def test_panel_uniqueness_is_constant_within_a_date():
    from app.services.signals.validation import panel_average_uniqueness

    dates = np.repeat(np.arange(50), 10)
    w = panel_average_uniqueness(dates, horizon=5)
    for d in range(50):
        assert len(set(np.round(w[dates == d], 12))) == 1


def test_panel_uniqueness_matches_single_series_when_one_per_date():
    from app.services.signals.validation import panel_average_uniqueness

    times = np.arange(100)
    assert np.allclose(panel_average_uniqueness(times, 10), average_uniqueness(times, 10))


def test_panel_uniqueness_handles_empty():
    from app.services.signals.validation import panel_average_uniqueness

    assert panel_average_uniqueness(np.asarray([]), horizon=20).size == 0
