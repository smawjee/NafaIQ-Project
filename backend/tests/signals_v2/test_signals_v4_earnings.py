import math

from app.services.signals_v4.earnings_features import (
    compute_earnings_features,
    eps_series,
    parse_period,
)


def _q(period, eps):
    return {"symbol": "T", "period": period, "eps": eps}


# 9 consecutive quarters with a clean YoY structure.
QUARTERLY = [
    _q("2024Q1", 1.0), _q("2024Q2", 1.2), _q("2024Q3", 1.1), _q("2024Q4", 1.3),
    _q("2025Q1", 1.5), _q("2025Q2", 1.4), _q("2025Q3", 1.6), _q("2025Q4", 1.8),
    _q("2026Q1", 2.0),
]
ANNUAL = [{"year": 2025, "roe": 20.0, "npm": 12.0}, {"year": 2024, "roe": 15.0}]


def test_parse_period():
    assert parse_period("2026Q3") == (2026, 3)
    assert parse_period(" 2026 Q 1 ") == (2026, 1)
    assert parse_period("bad") is None
    assert parse_period(None) is None


def test_eps_series_is_point_in_time():
    # As-of an earlier quarter must exclude everything reported later (no leakage).
    s = eps_series(QUARTERLY, as_of=(2025, 3))
    assert s[-1][0] == (2025, 3)
    assert all(pq <= (2025, 3) for pq, _ in s)
    assert (2026, 1) not in [pq for pq, _ in s]


def test_eps_change_yoy():
    f = compute_earnings_features(QUARTERLY, ANNUAL)
    assert f["as_of_period"] == "2026Q1"
    assert f["eps_latest"] == 2.0
    # (2.0 - 1.5) / (1.5 + eps) ≈ 0.3333
    assert math.isclose(f["eps_change"], 0.5 / (1.5 + 1e-6), rel_tol=1e-3)


def test_earnings_surprise_is_standardized():
    f = compute_earnings_features(QUARTERLY, ANNUAL)
    # Latest YoY change 0.5 vs history [0.5,0.2,0.5,0.5] (mean .425, sd .15) → SUE 0.5.
    assert math.isclose(f["earnings_surprise"], 0.5, abs_tol=1e-2)


def test_ttm_and_growth():
    f = compute_earnings_features(QUARTERLY, ANNUAL)
    assert math.isclose(f["eps_ttm"], 1.4 + 1.6 + 1.8 + 2.0, abs_tol=1e-6)
    # (6.8 - 5.1) / 5.1
    assert math.isclose(f["eps_ttm_growth"], 1.7 / 5.1, rel_tol=1e-3)


def test_profitability_quality_prefers_latest_roe_as_fraction():
    f = compute_earnings_features(QUARTERLY, ANNUAL)
    assert f["profitability_quality"] == 0.20  # 2025 ROE 20% → 0.20


def test_as_of_period_recomputes_without_future_quarters():
    f = compute_earnings_features(QUARTERLY, ANNUAL, as_of_period="2025Q3")
    assert f["as_of_period"] == "2025Q3"
    assert f["eps_latest"] == 1.6
    # YoY vs 2024Q3 (1.1)
    assert math.isclose(f["eps_change"], 0.5 / (1.1 + 1e-6), rel_tol=1e-3)


def test_insufficient_data_returns_none_not_crash():
    f = compute_earnings_features([_q("2026Q1", 2.0)], [])
    assert f["eps_latest"] == 2.0
    assert f["eps_change"] is None
    assert f["earnings_surprise"] is None
    assert f["eps_ttm"] is None
    assert f["quarters_available"] == 1


def test_empty_is_safe():
    f = compute_earnings_features([], [])
    assert f["eps_latest"] is None
    assert f["quarters_available"] == 0
