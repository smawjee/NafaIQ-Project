"""Tests for the shared inference engine (pilot_lib) and Arm C'' (v3).

Covers the CGM two-way cluster variance, the date-only comparability
statistic, effective-N reporting, ECE, the engine-enforced verdict rules and
the pre-registration sha256 binding. No database access.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "signals"
sys.path.insert(0, str(SCRIPTS))

pilot_lib = pytest.importorskip("pilot_lib")


# --- two-way clustering ----------------------------------------------------


def test_two_way_t_agrees_with_plain_mean():
    rng = np.random.default_rng(7)
    y = rng.normal(0.01, 0.05, 200)
    g1 = np.arange(200) % 40          # 40 dates
    g2 = np.arange(200) % 10          # 10 symbols
    mean, se, t, n_cl = pilot_lib.two_way_t(y, g1, g2)
    assert mean == pytest.approx(float(y.mean()))
    assert se > 0
    assert t == pytest.approx(mean / se)
    assert n_cl == 40                # (date, symbol) pairs repeat every 40 rows


def test_two_way_inflates_variance_within_symbol_shocks():
    rng = np.random.default_rng(11)
    dates = np.repeat(np.arange(30), 3)          # 30 dates
    sym_shock = rng.normal(0, 0.02, 3)           # 3 persistent symbols
    y = np.tile(sym_shock, 30) + rng.normal(0, 0.01, 90)
    g1, g2 = dates, np.tile(np.arange(3), 30)
    mean, se, t, _ = pilot_lib.two_way_t(y, g1, g2)
    _, se_date, t_date = pilot_lib.date_only_t(y, g1)
    # Symbol-level correlation must widen the two-way SE vs date-only.
    assert se > se_date
    assert abs(t) < abs(t_date)


def test_two_way_single_dimension_reduces_to_one_way():
    y = np.arange(20, dtype=float)
    g1 = np.arange(20) % 5
    g2 = np.zeros(20, dtype=int)                 # one symbol only
    mean, se, t, _ = pilot_lib.two_way_t(y, g1, g2)
    _, se1, t1 = pilot_lib.date_only_t(y, g1)
    assert mean == pytest.approx(float(y.mean()))
    assert se == pytest.approx(se1)
    assert t == pytest.approx(t1)


def test_two_way_variance_never_negative():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    g1 = np.array([0, 0, 1, 1])
    g2 = np.array([0, 1, 0, 1])                  # perfect cross
    mean, se, t, _ = pilot_lib.two_way_t(y, g1, g2)
    assert se >= 0
    assert np.isfinite(t)


# --- effective N / codes ---------------------------------------------------


def test_effective_n_counts_each_dimension():
    df = pd.DataFrame({
        "event_date": ["2025-01-02"] * 3 + ["2025-01-03"] * 2,
        "symbol": ["MARI", "MARI", "UBL", "MARI", "UBL"],
    })
    assert pilot_lib.effective_n(df) == {
        "events": 5, "dates": 2, "symbols": 2, "clusters": 4}


def test_cluster_codes_are_integers():
    df = pd.DataFrame({
        "event_date": ["2025-01-02", "2025-01-03", "2025-01-02"],
        "symbol": ["A", "B", "A"],
    })
    g1, g2 = pilot_lib.cluster_codes(df)
    assert g1.dtype == np.int64 and g2.dtype == np.int64
    assert (g1 == g2).all()                      # date aligns with symbol here


# --- ECE -------------------------------------------------------------------


def test_ece_of_uses_positive_net_frequency():
    explore = pd.DataFrame({
        "car_63": [0.05, 0.03, -0.01],
        "cost": [0.01] * 3,
    })
    holdout = pd.DataFrame({
        "car_63": [0.05, -0.01, -0.02],
        "cost": [0.01] * 3,
    })
    e = pilot_lib.ece_of(explore, holdout, (63,))
    # explore P(net>0) = 2/3, holdout P(net>0) = 1/3 -> diff 1/3
    assert e == pytest.approx(1 / 3)


def test_ece_ignores_non_finite_horizons():
    explore = pd.DataFrame({"car_63": [0.1], "cost": [0.0]})
    holdout = pd.DataFrame({"car_63": [0.1], "cost": [0.0]})
    assert pilot_lib.ece_of(explore, holdout, (63, 126)) == 0.0


# --- verdict engine --------------------------------------------------------


PRE_REG = {
    "primary_horizons": [63],
    "t_crit": 1.96,
    "max_ece": 0.05,
    "exclusion_top_n": 4,
    "min_events": 30,
    "min_dates": 10,
    "min_symbols": 8,
    "min_clusters": 15,
}


def _power(**kw):
    base = {"events": 169, "dates": 120, "symbols": 25,
            "clusters": 160, "span_ok": True}
    base.update(kw)
    return base


def _row(net=0.04, t=2.4, cost=0.012):
    return {"net_car": net, "net_t": t, "mean_cost": cost}


def test_verdict_green_when_all_gates_pass():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row()}, 0.03, exclusion_net=0.02)
    assert v == "GREEN" and not reasons


def test_verdict_cannot_conclude_on_any_shortfall():
    for key, got in (("events", 29), ("dates", 9), ("symbols", 7),
                     ("clusters", 14)):
        v, reasons = pilot_lib.verdict(
            PRE_REG, _power(**{key: got}), {63: _row()}, 0.03, 0.02)
        assert v == "CANNOT CONCLUDE", key
        assert any(key in r for r in reasons)


def test_verdict_cannot_conclude_when_span_broken():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(span_ok=False), {63: _row()}, 0.03, 0.02)
    assert v == "CANNOT CONCLUDE"


def test_verdict_cannot_conclude_without_primary_row():
    v, reasons = pilot_lib.verdict(PRE_REG, _power(), {}, 0.03, 0.02)
    assert v == "CANNOT CONCLUDE"


def test_verdict_red_when_net_nonpositive():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row(net=-0.01, t=-1.1)}, 0.03, 0.02)
    assert v == "RED"


def test_verdict_amber_when_t_below_crit():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row(t=1.5)}, 0.03, 0.02)
    assert v == "AMBER"
    assert any("1.96" in r for r in reasons)


def test_verdict_amber_when_ece_above_gate():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row()}, 0.09, 0.02)
    assert v == "AMBER"
    assert any("0.05" in r for r in reasons)


def test_verdict_amber_when_net_below_cost():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row(net=0.008, t=2.4)}, 0.03, 0.02)
    assert v == "AMBER"


def test_verdict_amber_when_exclusion_net_nonpositive():
    v, reasons = pilot_lib.verdict(
        PRE_REG, _power(), {63: _row()}, 0.03, exclusion_net=-0.005)
    assert v == "AMBER"


def test_verdict_ignores_126s_row():
    rows = {63: _row(), 126: _row(net=0.10, t=3.0)}
    v, _ = pilot_lib.verdict(PRE_REG, _power(), rows, 0.03, 0.02)
    assert v == "GREEN"                          # 126s cannot move the verdict


# --- pre-registration binding ----------------------------------------------


def test_sha256_json_is_stable_and_key_sorted():
    a = {"b": 1, "a": [1, 2]}
    b = {"a": [1, 2], "b": 1}
    c = {"b": 2, "a": [1, 2]}
    assert pilot_lib.sha256_json(a) == pilot_lib.sha256_json(b)
    assert pilot_lib.sha256_json(a) != pilot_lib.sha256_json(c)


def test_sha256_json_handles_non_json_types():
    d = {"d": __import__("datetime").date(2026, 8, 5)}
    assert isinstance(pilot_lib.sha256_json(d), str) and len(
        pilot_lib.sha256_json(d)) == 64
