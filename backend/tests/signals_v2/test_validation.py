import numpy as np
import pytest

from app.services.signals_v2.validation import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probability_of_backtest_overfitting,
    sharpe_ratio,
)


def test_sharpe_ratio_basics():
    rng = np.random.default_rng(1)
    steady = rng.normal(0.002, 0.005, 250)          # strong, consistent edge
    assert sharpe_ratio(steady) > 0.2
    assert sharpe_ratio(np.zeros(50)) == 0.0
    assert sharpe_ratio(np.asarray([0.01])) == 0.0  # undefined for < 2 points


def test_expected_max_sharpe_grows_with_trials():
    v = 0.01
    assert expected_max_sharpe(1, v) == 0.0
    e10 = expected_max_sharpe(10, v)
    e100 = expected_max_sharpe(100, v)
    assert 0 < e10 < e100


def test_dsr_high_for_real_edge_low_for_noise():
    rng = np.random.default_rng(7)
    edge = rng.normal(0.003, 0.004, 300)            # per-period SR ~ 0.75
    noise = rng.normal(0.0, 0.01, 300)
    dsr_edge = deflated_sharpe_ratio(edge, n_trials=3)
    dsr_noise = deflated_sharpe_ratio(noise, n_trials=3)
    assert dsr_edge > 0.95
    assert dsr_noise < dsr_edge
    # more trials -> harsher deflation
    assert deflated_sharpe_ratio(edge, n_trials=1000) <= dsr_edge
    assert deflated_sharpe_ratio(np.zeros(5), n_trials=3) == 0.0


def test_pbo_low_when_one_trial_dominates_high_when_antipersistent():
    rng = np.random.default_rng(3)
    T = 64
    # trial 0 dominates every period -> IS winner stays OOS winner -> PBO ~ 0
    dominant = np.column_stack([
        rng.normal(0.01, 0.001, T), rng.normal(0.0, 0.001, T), rng.normal(0.0, 0.001, T)])
    assert probability_of_backtest_overfitting(dominant) <= 0.1
    # anti-persistent: winner in first half is loser in second half -> PBO ~ 1
    a = np.concatenate([np.full(T // 2, 0.01), np.full(T // 2, -0.01)])
    b = -a
    anti = np.column_stack([a, b])
    assert probability_of_backtest_overfitting(anti) >= 0.4
    # degenerate: single trial -> cannot assess -> 1.0 (worst case)
    assert probability_of_backtest_overfitting(np.ones((10, 1))) == 1.0
