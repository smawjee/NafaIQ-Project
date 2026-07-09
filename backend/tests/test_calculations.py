"""Unit tests for app.services.calculations.

Pure-function tests; no DB or network access required.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services import calculations as calc


def test_holding_value_zero_safe():
    assert calc.holding_value(None, 100) == 0.0
    assert calc.holding_value(100, None) == 0.0
    assert calc.holding_value(0, 100) == 0.0
    assert calc.holding_value(100, 0) == 0.0


def test_holding_value_normal():
    assert calc.holding_value(100, 12.5) == 1250.0


def test_cost_basis():
    assert calc.cost_basis(200, 10) == 2000.0


def test_pnl_pct_zero_safe():
    assert calc.pnl_pct(100, 0) == 0.0
    assert calc.pnl_pct(50, 100) == 50.0
    assert calc.pnl_pct(-25, 100) == -25.0


def test_today_pnl():
    # 100 shares, latest 110, previous close 100 => 1000
    assert calc.today_pnl(100, 110, 100) == 1000.0
    # 100 shares, latest 95, previous close 100 => -500
    assert calc.today_pnl(100, 95, 100) == -500.0
    # missing previous close
    assert calc.today_pnl(100, 110, None) == 0.0


def test_aggregate_portfolio_totals():
    rows = [
        {
            "symbol": "HBL",
            "shares": 100,
            "market_value": 15000.0,
            "cost_basis": 12000.0,
            "unrealized_pnl": 3000.0,
            "today_pnl": 500.0,
            "previous_close": 145.0,
        },
        {
            "symbol": "OGDC",
            "shares": 200,
            "market_value": 30000.0,
            "cost_basis": 28000.0,
            "unrealized_pnl": 2000.0,
            "today_pnl": 200.0,
            "previous_close": 149.0,
        },
    ]
    totals = calc.aggregate_portfolio_totals(rows)
    assert totals["total_market_value"] == 45000.0
    assert totals["total_cost_basis"] == 40000.0
    assert totals["total_unrealized_pnl"] == 5000.0
    assert totals["total_unrealized_pnl_pct"] == 12.5
    assert totals["today_pnl"] == 700.0
    # prev_value = 145*100 + 149*200 = 14500 + 29800 = 44300
    assert abs(totals["today_pnl_pct"] - round(700.0 / 44300.0 * 100, 2)) < 0.01


def test_allocation_by_stock():
    rows = [
        {"symbol": "A", "market_value": 100.0},
        {"symbol": "B", "market_value": 300.0},
    ]
    out = calc.allocation_by_stock(rows)
    assert out[0]["symbol"] == "B"
    assert out[0]["pct"] == 75.0
    assert out[1]["pct"] == 25.0


def test_allocation_by_sector():
    rows = [
        {"symbol": "HBL", "market_value": 100.0},
        {"symbol": "MCB", "market_value": 200.0},
        {"symbol": "LUCK", "market_value": 100.0},
    ]
    smap = {"HBL": "Banking", "MCB": "Banking", "LUCK": "Cement"}
    out = calc.allocation_by_sector(rows, smap)
    assert out[0]["sector"] == "Banking"
    assert out[0]["value"] == 300.0
    assert out[1]["sector"] == "Cement"


def test_savings_rate():
    assert calc.savings_rate(100, 50) == 50.0
    assert calc.savings_rate(0, 0) == 0.0
    assert calc.savings_rate(100, 100) == 0.0


def test_budget_usage():
    assert calc.budget_usage(50, 100) == 50.0
    assert calc.budget_usage(150, 100) == 150.0
    assert calc.budget_usage(50, 0) == 0.0


def test_goal_progress():
    assert calc.goal_progress(50, 100) == 50.0
    assert calc.goal_progress(150, 100) == 150.0
    assert calc.goal_progress(0, 0) == 0.0


def test_zakat_estimate_under_nisab():
    res = calc.zakat_estimate(total_assets=10000, total_deductions=0, nisab_value=100000, rate_pct=2.5)
    assert res["zakat_due"] == 0.0
    assert res["nisab_met"] is False
    assert res["net_zakatable"] == 10000.0


def test_zakat_estimate_above_nisab():
    res = calc.zakat_estimate(total_assets=200000, total_deductions=0, nisab_value=100000, rate_pct=2.5)
    assert res["zakat_due"] == 5000.0
    assert res["nisab_met"] is True


def test_zakat_estimate_with_deductions():
    res = calc.zakat_estimate(total_assets=200000, total_deductions=50000, nisab_value=100000, rate_pct=2.5)
    assert res["net_zakatable"] == 150000.0
    assert res["zakat_due"] == 3750.0


def test_month_helpers():
    assert calc.month_string() != ""
    assert calc.previous_month_string("2026-01") == "2025-12"
    assert calc.previous_month_string("2026-03") == "2026-02"


def test_performance_vs_kse100_basic():
    portfolio_points = [
        {"date": "2026-01-01", "value": 100.0, "label": "Jan 01"},
        {"date": "2026-01-02", "value": 110.0, "label": "Jan 02"},
    ]
    kse = [
        {"date": "2026-01-01", "close": 1000.0},
        {"date": "2026-01-02", "close": 1100.0},
    ]
    out = calc.performance_vs_kse100(portfolio_points, kse)
    assert len(out) == 2
    # base_port = 100, base_kse = 1000; benchmark = (kse/1000) * 100
    assert out[0]["value"] == 100.0
    assert out[0]["benchmark"] == 100.0
    assert out[1]["value"] == 110.0
    assert out[1]["benchmark"] == 110.0


def test_portfolio_history_from_ohlcv():
    holdings = [{"symbol": "HBL", "shares": 100}]
    ohlcv = {
        "HBL": [
            {"date": "2026-01-01", "close": 100.0},
            {"date": "2026-01-02", "close": 110.0},
        ]
    }
    pts = calc.portfolio_history_from_ohlcv(holdings, ohlcv, days=10)
    assert len(pts) == 2
    assert pts[0]["value"] == 10000.0
    assert pts[1]["value"] == 11000.0
