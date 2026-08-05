"""Tests for the pilot's research math.

The pilot decides whether the whole signals programme proceeds, so its metric
code is tested like production code. In particular the vectorised
Corwin-Schultz used across the panel must agree with the scalar reference in
``app.services.signals.costs`` — the scalar one is unit-tested, the vectorised
one exists only because the scalar version would be called ~10^8 times.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "signals"
sys.path.insert(0, str(SCRIPTS))

pilot = pytest.importorskip("pilot_reversal")
panel_mod = pytest.importorskip("panel")

from app.services.signals.costs import (  # noqa: E402
    CostParams,
    corwin_schultz_spread,
    round_trip_cost,
)


def _panel(close: np.ndarray, high=None, low=None, volume=None) -> "panel_mod.Panel":
    import pandas as pd
    n_dates, n_syms = close.shape
    return panel_mod.Panel(
        dates=pd.DatetimeIndex(pd.date_range("2020-01-01", periods=n_dates, freq="B")),
        symbols=np.asarray([f"S{i}" for i in range(n_syms)]),
        close=close,
        high=close * 1.01 if high is None else high,
        low=close * 0.99 if low is None else low,
        volume=np.full_like(close, 1e6) if volume is None else volume,
        ex_cash=np.zeros_like(close),   # v2: attributed-yield matrix (none here)
    )


# --- vectorised vs scalar Corwin-Schultz ----------------------------------


def test_vectorised_spread_matches_scalar_reference():
    """The optimisation must not change the number the gate is judged on."""
    rng = np.random.default_rng(11)
    n = 300
    price = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    half = price * 0.004
    high = (price + half).reshape(-1, 1)
    low = (price - half).reshape(-1, 1)
    p = _panel(price.reshape(-1, 1), high=high, low=low)

    window = 60
    vec = pilot.rolling_cs_spread(p, window=window)

    # Compare the last row against the scalar estimator over the same window.
    # The vectorised version attributes pair (t-1,t) to t, so a window ending at
    # the last row covers exactly the last `window` pairs.
    expected = corwin_schultz_spread(high[-window - 1:, 0], low[-window - 1:, 0])
    assert expected is not None
    assert vec[-1, 0] == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_vectorised_spread_is_nan_before_the_window_fills():
    p = _panel(np.full((10, 2), 100.0))
    vec = pilot.rolling_cs_spread(p, window=60)
    assert np.all(np.isnan(vec))


# --- vectorised cost matrix vs scalar reference ---------------------------


def test_cost_matrix_matches_the_scalar_cost_model():
    """The panel-wide cost must equal what costs.round_trip_cost would say.

    This is the check that would have caught the first cost model's problem
    only if the scalar model were right too — so it is paired with the
    structural tests in test_costs.py, not a substitute for them.
    """
    n = 120
    close = np.column_stack([
        np.full(n, 100.0),      # liquid, mid-priced
        np.full(n, 3.0),        # low-priced, tick-floored
    ])
    volume = np.column_stack([
        np.full(n, 1_000_000.0),
        np.full(n, 1_000.0),
    ])
    p = _panel(close, volume=volume)
    params = CostParams()
    mat = pilot.cost_matrix(p, params)

    for col in (0, 1):
        expected = round_trip_cost(
            price=float(close[-1, col]),
            turnover_pkr=float(np.median(close[:, col] * volume[:, col])),
            daily_volatility=None,          # constant price -> zero vol
            params=params,
        )
        assert mat[-1, col] == pytest.approx(expected.total, rel=1e-9)


def test_cost_matrix_is_decreasing_in_turnover():
    n = 120
    close = np.full((n, 3), 100.0)
    volume = np.column_stack([
        np.full(n, 100.0), np.full(n, 100_000.0), np.full(n, 10_000_000.0),
    ])
    mat = pilot.cost_matrix(_panel(close, volume=volume), CostParams())
    assert mat[-1, 0] > mat[-1, 1] > mat[-1, 2]


# --- rank / IC machinery ---------------------------------------------------


def test_spearman_ic_recovers_a_perfect_ranking():
    signal = np.arange(60, dtype=np.float64).reshape(1, 60)
    label = signal.copy()
    valid = np.ones((1, 60), dtype=bool)
    ic = pilot.spearman_ic(signal, label, valid)
    assert ic[0] == pytest.approx(1.0, abs=1e-9)


def test_spearman_ic_recovers_a_perfect_inversion():
    signal = np.arange(60, dtype=np.float64).reshape(1, 60)
    valid = np.ones((1, 60), dtype=bool)
    ic = pilot.spearman_ic(signal, -signal, valid)
    assert ic[0] == pytest.approx(-1.0, abs=1e-9)


def test_spearman_ic_skips_dates_with_too_few_names():
    """Thin dates must not contribute a noisy IC to the fold average."""
    n = pilot.MIN_NAMES_PER_DATE - 1
    signal = np.arange(n, dtype=np.float64).reshape(1, n)
    valid = np.ones((1, n), dtype=bool)
    assert np.isnan(pilot.spearman_ic(signal, signal, valid)[0])


def test_ranks_handle_ties_without_bias():
    x = np.asarray([[1.0, 1.0, 2.0, 2.0]])
    valid = np.ones((1, 4), dtype=bool)
    ranks = pilot._rankdata_rows(x, valid)
    assert ranks[0, 0] == pytest.approx(ranks[0, 1])
    assert ranks[0, 2] == pytest.approx(ranks[0, 3])
    assert ranks[0, 2] > ranks[0, 0]


# --- decile profile --------------------------------------------------------


def test_decile_profile_detects_a_monotone_signal():
    rng = np.random.default_rng(3)
    n_dates, n_syms = 40, 200
    signal = rng.normal(size=(n_dates, n_syms))
    # Label is the signal plus noise -> deciles must increase monotonically.
    label = signal * 0.02 + rng.normal(scale=0.005, size=(n_dates, n_syms))
    valid = np.ones((n_dates, n_syms), dtype=bool)
    cost = np.zeros((n_dates, n_syms))

    prof = pilot.decile_profile(signal, label, cost, valid, np.arange(n_dates))
    assert prof["monotonicity"] > 0.95
    assert prof["top_minus_bottom_gross"] > 0


def test_decile_profile_reports_no_edge_for_pure_noise():
    rng = np.random.default_rng(5)
    n_dates, n_syms = 60, 200
    signal = rng.normal(size=(n_dates, n_syms))
    label = rng.normal(scale=0.02, size=(n_dates, n_syms))
    valid = np.ones((n_dates, n_syms), dtype=bool)
    cost = np.zeros((n_dates, n_syms))

    prof = pilot.decile_profile(signal, label, cost, valid, np.arange(n_dates))
    assert abs(prof["top_minus_bottom_gross"]) < 0.005


def test_cost_reduces_the_net_spread():
    rng = np.random.default_rng(9)
    n_dates, n_syms = 30, 150
    signal = rng.normal(size=(n_dates, n_syms))
    label = signal * 0.02
    valid = np.ones((n_dates, n_syms), dtype=bool)

    free = pilot.decile_profile(signal, label, np.zeros((n_dates, n_syms)),
                                valid, np.arange(n_dates))
    costly = pilot.decile_profile(signal, label, np.full((n_dates, n_syms), 0.01),
                                  valid, np.arange(n_dates))
    assert costly["top_decile_net"] < free["top_decile_net"]


# --- the decision rule -----------------------------------------------------


def _result(*, mono, tmb_net, ic_years, ho_ic, ex_ic):
    return {
        "explore": {
            "monotonicity": mono,
            "top_minus_bottom_net": tmb_net,
            "ic_by_year": ic_years,
            "ic_mean": ex_ic,
        },
        "holdout": {"ic_mean": ho_ic},
    }


def test_green_requires_every_condition():
    res = _result(mono=0.95, tmb_net=0.01,
                  ic_years={"2016": 0.02, "2017": 0.01, "2018": 0.03, "2019": 0.01},
                  ho_ic=0.02, ex_ic=0.02)
    assert pilot.verdict(res)[0] == "GREEN"


def test_holdout_sign_flip_downgrades_from_green():
    res = _result(mono=0.95, tmb_net=0.01,
                  ic_years={"2016": 0.02, "2017": 0.01, "2018": 0.03, "2019": 0.01},
                  ho_ic=-0.02, ex_ic=0.02)
    v, reasons = pilot.verdict(res)
    assert v == "AMBER"
    assert any("holdout" in r for r in reasons)


def test_non_monotone_downgrades_from_green():
    res = _result(mono=0.2, tmb_net=0.01,
                  ic_years={"2016": 0.02, "2017": 0.01, "2018": 0.03, "2019": 0.01},
                  ho_ic=0.02, ex_ic=0.02)
    assert pilot.verdict(res)[0] == "AMBER"


def test_negative_after_cost_spread_is_red():
    res = _result(mono=0.95, tmb_net=-0.002,
                  ic_years={"2016": 0.02, "2017": 0.01, "2018": 0.03, "2019": 0.01},
                  ho_ic=0.02, ex_ic=0.02)
    assert pilot.verdict(res)[0] == "RED"


def test_unstable_folds_downgrade_from_green():
    res = _result(mono=0.95, tmb_net=0.01,
                  ic_years={"2016": 0.02, "2017": -0.01, "2018": -0.03, "2019": 0.01},
                  ho_ic=0.02, ex_ic=0.02)
    v, reasons = pilot.verdict(res)
    assert v == "AMBER"
    assert any("positive IC" in r for r in reasons)


# --- panel semantics -------------------------------------------------------


def test_forward_and_trailing_returns_are_aligned_and_leak_free():
    close = np.asarray([[100.0], [110.0], [121.0], [133.1]])
    p = _panel(close)

    fwd = p.forward_return(1)
    assert fwd[0, 0] == pytest.approx(0.10)
    assert np.isnan(fwd[-1, 0]), "last row cannot know a future bar"

    trail = p.trailing_return(1)
    assert np.isnan(trail[0, 0]), "first row has no prior bar"
    assert trail[1, 0] == pytest.approx(0.10)


def test_contamination_mask_covers_the_window_around_a_limit_move():
    close = np.full((21, 1), 100.0)
    close[10, 0] = 50.0          # -50% one-day move = corporate action or bad row
    p = _panel(close)
    mask = p.contamination_mask(back=2, forward=2)
    # The move is recorded as the return at row 10; window covers rows 8..12.
    assert mask[8:13, 0].all()
    assert not mask[0, 0]
    assert not mask[20, 0]


def test_investable_mask_excludes_penny_and_short_history():
    n = panel_mod.MIN_HISTORY_BARS + 50
    close = np.column_stack([
        np.full(n, 100.0),                                  # normal
        np.full(n, 0.5),                                    # penny
    ])
    p = _panel(close)
    inv = p.investable_mask()
    assert not inv[-1, 1], "penny stock must be excluded"
