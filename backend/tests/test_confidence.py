"""Deterministic confidence + risk engine (§6, §19.8).

Every value the user sees comes from a pure function here; insufficient data
returns a typed sentinel (None) rather than a garbage number.
"""
from __future__ import annotations

import math

from app.services.ai import confidence as conf


# --------------------------- diversification (HHI) ------------------------- #
def test_diversification_two_equal_holdings():
    # Two equal holdings: HHI = 0.5 -> (1 - 0.5) * 100 = 50.
    holdings = [{"market_value": 100.0}, {"market_value": 100.0}]
    assert abs(conf.diversification_score(holdings) - 50.0) < 1e-6


def test_diversification_single_holding_fully_concentrated():
    assert conf.diversification_score([{"market_value": 500.0}]) == 0.0


def test_diversification_four_equal_holdings():
    holdings = [{"market_value": 25.0} for _ in range(4)]
    # HHI = 4 * 0.25^2 = 0.25 -> 75.
    assert abs(conf.diversification_score(holdings) - 75.0) < 1e-6


def test_diversification_insufficient_data_sentinel():
    assert conf.diversification_score([]) is None
    assert conf.diversification_score([{"market_value": 0.0}]) is None


# --------------------------- spending deviation ---------------------------- #
def test_spending_deviation_confidence():
    # 50% over baseline.
    assert abs(conf.spending_deviation_confidence(150, 100) - 50.0) < 1e-6


def test_spending_deviation_caps_at_100():
    assert conf.spending_deviation_confidence(1000, 100) == 100.0


def test_spending_deviation_zero_baseline_sentinel():
    assert conf.spending_deviation_confidence(100, 0) is None


# --------------------------- budget health --------------------------------- #
def test_budget_health_all_within_is_100():
    budgets = [{"spent": 50, "limit_amount": 100}, {"spent": 80, "limit_amount": 100}]
    assert conf.budget_health_score(budgets) == 100.0


def test_budget_health_penalizes_overspend():
    # One budget 150% -> 50% over -> 100 - 50 = 50.
    budgets = [{"spent": 150, "limit_amount": 100}]
    assert abs(conf.budget_health_score(budgets) - 50.0) < 1e-6


def test_budget_health_insufficient_data_sentinel():
    assert conf.budget_health_score([]) is None
    assert conf.budget_health_score([{"spent": 10, "limit_amount": 0}]) is None


# --------------------------- months to goal -------------------------------- #
def test_months_to_goal_basic():
    # need 5000 more at 1000/mo -> 5 months.
    assert conf.months_to_goal(saved=5000, target=10000, monthly_rate=1000) == 5


def test_months_to_goal_rounds_up():
    assert conf.months_to_goal(saved=0, target=1000, monthly_rate=300) == 4  # 3.33 -> 4


def test_months_to_goal_already_reached():
    assert conf.months_to_goal(saved=10000, target=10000, monthly_rate=100) == 0


def test_months_to_goal_zero_rate_sentinel():
    assert conf.months_to_goal(saved=0, target=1000, monthly_rate=0) is None


# --------------------------- portfolio volatility -------------------------- #
def test_portfolio_volatility_known_series():
    # values 100,110,99 -> returns +0.1, -0.1 -> sample std = 0.1414... * 100.
    history = [{"value": 100.0}, {"value": 110.0}, {"value": 99.0}]
    vol = conf.portfolio_volatility(history)
    assert abs(vol - 14.142135) < 1e-3


def test_portfolio_volatility_insufficient_sentinel():
    assert conf.portfolio_volatility([{"value": 100.0}]) is None
    assert conf.portfolio_volatility([{"value": 100.0}, {"value": 110.0}]) is None


# --------------------------- portfolio beta -------------------------------- #
def test_portfolio_beta_known_series_is_one_point_five():
    # port returns are exactly 1.5x the benchmark returns => beta = 1.5.
    bench = [{"value": 100.0}, {"value": 110.0}, {"value": 99.0}]     # +0.1, -0.1
    port = [{"value": 100.0}, {"value": 115.0}, {"value": 97.75}]     # +0.15, -0.15
    beta = conf.portfolio_beta(port, bench)
    assert abs(beta - 1.5) < 1e-3


def test_portfolio_beta_insufficient_sentinel():
    assert conf.portfolio_beta([{"value": 1}], [{"value": 1}]) is None


def test_portfolio_beta_zero_variance_benchmark_sentinel():
    flat = [{"value": 100.0}, {"value": 100.0}, {"value": 100.0}]
    port = [{"value": 100.0}, {"value": 110.0}, {"value": 99.0}]
    assert conf.portfolio_beta(port, flat) is None


# --------------------------- risk band ------------------------------------- #
def test_risk_band_high():
    assert conf.risk_band(diversification=15.0, volatility=30.0, beta=1.6) == "High"


def test_risk_band_low():
    assert conf.risk_band(diversification=85.0, volatility=4.0, beta=0.8) == "Low"


def test_risk_band_moderate_single_trigger():
    assert conf.risk_band(diversification=85.0, volatility=30.0, beta=0.8) == "Moderate"


def test_risk_band_all_none_is_unknown():
    assert conf.risk_band(diversification=None, volatility=None, beta=None) == "Unknown"
