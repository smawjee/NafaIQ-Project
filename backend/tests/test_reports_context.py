"""Context-assembler tests (§3, §19.7, §19.8).

Each assembler is a pure async function over the existing data services: given
fixed (mocked) service outputs it must produce a stable, JSON-serializable
bundle dict with numerics parked at known dot-path keys, fold in the
deterministic confidence-engine metrics, apply the §19.7 data-sanity guards, and
omit metrics (§19.8 sentinels) when inputs are too sparse.

The data services self-manage their DB connections, so these tests monkeypatch
the service functions the assemblers call — no DB, no network.
"""
from __future__ import annotations

import json

from app.schemas.finance import (
    FinanceSummaryResponse,
    IncomeExpensePoint,
    IncomeExpenseResponse,
    SpendingByCategoryResponse,
    SpendingCategory,
)
from app.services.ai import context as ctx
from app.services.ai.evidence import NullEvidenceRetriever


def _async(value):
    async def _f(*a, **k):
        return value

    return _f


def _assert_json_serializable(bundle: dict) -> None:
    # The shared contract: the bundle is a plain JSON-serializable dict.
    json.dumps(bundle)


# --------------------------------------------------------------------------- #
# Market Brief (§3.1) — shared, no user data                                  #
# --------------------------------------------------------------------------- #
async def test_market_brief_bundle_shape(monkeypatch):
    cards = [
        {"code": "KSE100", "date": "2026-07-14", "close": 78500.0,
         "prev_close": 78000.0, "change": 500.0, "change_pct": 0.64},
        {"code": "KSE30", "date": "2026-07-14", "close": 24000.0,
         "prev_close": 24100.0, "change": -100.0, "change_pct": -0.41},
    ]
    snapshot = [
        {"symbol": "OGDC", "price": 150.0, "change_pct": 5.0, "volume": 1000},
        {"symbol": "HBL", "price": 100.0, "change_pct": -3.0, "volume": 800},
        {"symbol": "PSO", "price": 200.0, "change_pct": 0.0, "volume": 500},
    ]
    sectors = [{"name": "Oil & Gas", "pct": 1.2}, {"name": "Banking", "pct": -0.5}]
    ann = [{"id": "1", "symbol": "OGDC", "title": "Board meeting", "posted_at": "2026-07-13"}]

    monkeypatch.setattr(ctx.market_quotes, "index_cards", _async(cards))
    monkeypatch.setattr(ctx.market_quotes, "market_snapshot", _async(snapshot))
    monkeypatch.setattr(ctx.market_heatmap, "sector_averages", _async(sectors))
    monkeypatch.setattr(ctx.market_quotes, "announcements", _async(ann))

    bundle = await ctx.build_market_brief_context(None, evidence=NullEvidenceRetriever())

    _assert_json_serializable(bundle)
    assert bundle["indices"]["kse100"]["close"] == 78500.0
    assert bundle["indices"]["kse100"]["change_pct"] == 0.64
    assert bundle["indices"]["kse30"]["close"] == 24000.0
    # breadth: 1 up, 1 down, 1 flat
    assert bundle["breadth"]["advancers"] == 1
    assert bundle["breadth"]["decliners"] == 1
    assert bundle["breadth"]["unchanged"] == 1
    # top gainer / loser
    assert bundle["movers"]["gainers"][0]["symbol"] == "OGDC"
    assert bundle["movers"]["losers"][0]["symbol"] == "HBL"
    assert bundle["sectors"][0]["name"] == "Oil & Gas"
    assert bundle["announcements"][0]["title"] == "Board meeting"
    # evidence key present (NullEvidenceRetriever -> [])
    assert bundle["evidence"] == []


# --------------------------------------------------------------------------- #
# Stock Analysis (§3.2) — shared, public data                                 #
# --------------------------------------------------------------------------- #
def _ohlcv_series(n: int = 30) -> list[dict]:
    bars = []
    price = 100.0
    for i in range(n):
        price += 1.0 if i % 2 == 0 else -0.5
        bars.append({
            "symbol": "OGDC", "date": f"2026-06-{(i % 28) + 1:02d}",
            "open": price, "high": price + 2, "low": price - 2,
            "close": price, "volume": 1000 + i,
        })
    return bars


async def test_stock_analysis_bundle_shape(monkeypatch):
    quote = {"symbol": "OGDC", "price": 150.0, "change": 2.0, "change_pct": 1.35,
             "volume": 1000, "day_high": 152.0, "day_low": 148.0}
    fundamentals = {"symbol": "OGDC", "eps": 25.0, "pe": 6.0, "pb": 1.2,
                    "div_yield": 8.0, "payout": 40.0, "roe": 20.0}
    hist = _ohlcv_series(30)
    ann = [{"id": "1", "symbol": "OGDC", "title": "Dividend declared", "posted_at": "2026-07-10"}]
    divs = [{"announcement_id": "1", "symbol": "OGDC", "ex_date": "2026-07-20",
             "payout_type": "cash", "per_share": 5.0}]

    monkeypatch.setattr(ctx.market_quotes, "quote", _async(quote))
    monkeypatch.setattr(ctx.market_quotes, "fundamentals", _async(fundamentals))
    monkeypatch.setattr(ctx.market_history, "history", _async(hist))
    monkeypatch.setattr(ctx.market_quotes, "announcements", _async(ann))
    monkeypatch.setattr(ctx.market_quotes, "dividends", _async(divs))

    bundle = await ctx.build_stock_analysis_context(None, subject="ogdc")

    _assert_json_serializable(bundle)
    assert bundle["symbol"] == "OGDC"
    assert bundle["quote"]["price"] == 150.0
    assert bundle["fundamentals"]["pe"] == 6.0
    # indicators computed deterministically from the OHLCV history
    assert "indicators" in bundle
    assert "rsi14" in bundle["indicators"]
    assert bundle["indicator_labels"]["sma20"] == "20-day simple moving average"
    assert bundle["indicator_periods"]["sma20"] == 20
    assert bundle["price_range"]["bars"] == 30
    assert bundle["announcements"][0]["title"] == "Dividend declared"
    assert bundle["dividends"][0]["per_share"] == 5.0


async def test_stock_analysis_omits_non_finite_fundamentals(monkeypatch):
    # §19.7: a non-finite ratio must be dropped, not narrated.
    fundamentals = {"symbol": "OGDC", "eps": 25.0, "pe": float("inf"),
                    "pb": None, "div_yield": 8.0, "payout": 40.0, "roe": 20.0}
    monkeypatch.setattr(ctx.market_quotes, "quote",
                        _async({"symbol": "OGDC", "price": 150.0}))
    monkeypatch.setattr(ctx.market_quotes, "fundamentals", _async(fundamentals))
    monkeypatch.setattr(ctx.market_history, "history", _async(_ohlcv_series(20)))
    monkeypatch.setattr(ctx.market_quotes, "announcements", _async([]))
    monkeypatch.setattr(ctx.market_quotes, "dividends", _async([]))

    bundle = await ctx.build_stock_analysis_context(None, subject="OGDC")
    _assert_json_serializable(bundle)
    assert bundle["fundamentals"]["pe"] is None  # inf dropped
    assert bundle["fundamentals"]["eps"] == 25.0


# --------------------------------------------------------------------------- #
# Portfolio (§3.3) — confidential; risk metrics folded in                     #
# --------------------------------------------------------------------------- #
def _networth(holdings: list[dict]) -> dict:
    return {
        "total_market_value": 300.0,
        "total_cost_basis": 250.0,
        "total_unrealized_pnl": 50.0,
        "total_unrealized_pnl_pct": 20.0,
        "today_pnl": 5.0,
        "today_pnl_pct": 1.7,
        "portfolio_count": 1,
        "holding_count": len(holdings),
        "by_holding": holdings,
    }


async def test_portfolio_bundle_folds_risk_metrics(monkeypatch):
    holdings = [
        {"symbol": "OGDC", "shares": 1.0, "avg_cost": 100.0, "current_price": 150.0,
         "market_value": 150.0, "cost_basis": 100.0, "unrealized_pnl": 50.0, "pnl_pct": 50.0},
        {"symbol": "HBL", "shares": 1.0, "avg_cost": 150.0, "current_price": 150.0,
         "market_value": 150.0, "cost_basis": 150.0, "unrealized_pnl": 0.0, "pnl_pct": 0.0},
    ]
    # perf/history: 3 aligned points -> beta & volatility computable
    perf = [
        {"date": "d1", "value": 100.0, "benchmark": 100.0},
        {"date": "d2", "value": 115.0, "benchmark": 110.0},
        {"date": "d3", "value": 97.75, "benchmark": 99.0},
    ]
    hist = {"days": 30, "points": [
        {"date": "d1", "value": 100.0, "benchmark": 100.0},
        {"date": "d2", "value": 110.0, "benchmark": 105.0},
        {"date": "d3", "value": 99.0, "benchmark": 101.0},
    ]}

    monkeypatch.setattr(ctx.portfolio_svc, "networth", _async(_networth(holdings)))
    monkeypatch.setattr(ctx.portfolio_svc, "portfolio_history", _async(hist))
    monkeypatch.setattr(ctx.portfolio_svc, "performance_vs_kse100", _async(perf))
    monkeypatch.setattr(ctx.portfolio_trades, "list_stock_transactions", _async([]))
    monkeypatch.setattr(ctx.sector_map_mod, "get_sector_map",
                        _async({"OGDC": "Oil & Gas", "HBL": "Banking"}))

    bundle = await ctx.build_portfolio_context(None, user_id="u1", days=30)

    _assert_json_serializable(bundle)
    assert bundle["period_days"] == 30
    assert bundle["networth"]["total_market_value"] == 300.0
    # diversification of two equal holdings -> 50
    assert abs(bundle["risk"]["diversification"] - 50.0) < 1e-6
    assert bundle["risk"]["volatility"] is not None
    assert bundle["risk"]["beta"] is not None
    assert bundle["risk"]["band"] in {"Low", "Moderate", "High", "Unknown"}
    assert bundle["allocation"]["by_stock"][0]["symbol"] in {"OGDC", "HBL"}
    assert bundle["allocation"]["by_sector"]  # non-empty


async def test_portfolio_sanity_guard_omits_bad_avg_cost(monkeypatch):
    # §19.7: avg_cost wildly out of range vs last price is dropped, not narrated.
    holdings = [
        {"symbol": "OGDC", "shares": 10.0, "avg_cost": 100000.0, "current_price": 100.0,
         "market_value": 1000.0, "cost_basis": 1000000.0, "unrealized_pnl": -999000.0,
         "pnl_pct": -99.9},
    ]
    monkeypatch.setattr(ctx.portfolio_svc, "networth", _async(_networth(holdings)))
    monkeypatch.setattr(ctx.portfolio_svc, "portfolio_history",
                        _async({"days": 30, "points": []}))
    monkeypatch.setattr(ctx.portfolio_svc, "performance_vs_kse100", _async([]))
    monkeypatch.setattr(ctx.portfolio_trades, "list_stock_transactions", _async([]))
    monkeypatch.setattr(ctx.sector_map_mod, "get_sector_map", _async({"OGDC": "Oil & Gas"}))

    bundle = await ctx.build_portfolio_context(None, user_id="u1", days=30)
    _assert_json_serializable(bundle)
    assert bundle["holdings"][0]["avg_cost"] is None      # bad value omitted
    assert bundle["holdings"][0]["current_price"] == 100.0  # good value kept


async def test_portfolio_sparse_history_omits_beta_and_volatility(monkeypatch):
    # §19.8: too few points -> confidence sentinels -> metric omitted.
    holdings = [
        {"symbol": "OGDC", "shares": 1.0, "avg_cost": 100.0, "current_price": 150.0,
         "market_value": 150.0, "cost_basis": 100.0, "unrealized_pnl": 50.0, "pnl_pct": 50.0},
    ]
    monkeypatch.setattr(ctx.portfolio_svc, "networth", _async(_networth(holdings)))
    monkeypatch.setattr(ctx.portfolio_svc, "portfolio_history",
                        _async({"days": 30, "points": [{"date": "d1", "value": 100.0}]}))
    monkeypatch.setattr(ctx.portfolio_svc, "performance_vs_kse100",
                        _async([{"date": "d1", "value": 100.0, "benchmark": 100.0}]))
    monkeypatch.setattr(ctx.portfolio_trades, "list_stock_transactions", _async([]))
    monkeypatch.setattr(ctx.sector_map_mod, "get_sector_map", _async({"OGDC": "Oil & Gas"}))

    bundle = await ctx.build_portfolio_context(None, user_id="u1", days=30)
    _assert_json_serializable(bundle)
    assert bundle["risk"]["beta"] is None
    assert bundle["risk"]["volatility"] is None


# --------------------------------------------------------------------------- #
# Finance (§3.4) — confidential; budget-health folded in                      #
# --------------------------------------------------------------------------- #
async def test_finance_bundle_shape(monkeypatch):
    summ = FinanceSummaryResponse(
        month="2026-07", income=100000.0, expenses=70000.0, savings=30000.0,
        savings_rate=30.0, last_month_income=95000.0, last_month_expense=72000.0,
        last_month_savings=23000.0,
    )
    series = IncomeExpenseResponse(months=2, series=[
        IncomeExpensePoint(month="2026-06", income=95000.0, expense=72000.0),
        IncomeExpensePoint(month="2026-07", income=100000.0, expense=70000.0),
    ])
    spend = SpendingByCategoryResponse(days=30, total=70000.0, categories=[
        SpendingCategory(category="food", amount=40000.0, pct=57.1),
        SpendingCategory(category="transport", amount=30000.0, pct=42.9),
    ])
    budgets = [
        {"category": "food", "spent": 40000.0, "limit_amount": 35000.0, "period": "month", "tip": "eat in"},
        {"category": "transport", "spent": 20000.0, "limit_amount": 30000.0, "period": "month", "tip": None},
    ]
    goals = [
        {"name": "Hajj", "target": 500000.0, "saved": 100000.0, "ai_tip": "save more", "emoji": "🕋"},
    ]
    bills = [
        {"name": "Electricity", "amount": 8000.0, "due_date": "2099-01-31",
         "status": "UPCOMING", "recurring": True},
        {"name": "Internet", "amount": 5000.0, "due_date": "2000-01-01",
         "status": "UPCOMING", "recurring": True},  # far past due -> overdue
        {"name": "Rent", "amount": 60000.0, "due_date": "2099-02-01",
         "status": "PAID", "recurring": True},
    ]

    monkeypatch.setattr(ctx.finance_summary, "summary", _async(summ))
    monkeypatch.setattr(ctx.finance_summary, "income_expense_series", _async(series))
    monkeypatch.setattr(ctx.finance_summary, "spending_by_category", _async(spend))
    monkeypatch.setattr(ctx.finance_budgets, "list_budgets", _async(budgets))
    monkeypatch.setattr(ctx.finance_goals, "list_goals", _async(goals))
    monkeypatch.setattr(ctx.finance_bills, "list_bills", _async(bills))

    bundle = await ctx.build_finance_context(None, user_id="u1")

    _assert_json_serializable(bundle)
    # Bills folded in: unpaid = Electricity + Internet; Internet is overdue.
    assert bundle["bill_insights"]["bill_count"] == 3
    assert bundle["bill_insights"]["unpaid_count"] == 2
    assert bundle["bill_insights"]["overdue_count"] == 1
    assert bundle["bill_insights"]["total_unpaid"] == 13000.0
    assert bundle["summary"]["income"] == 100000.0
    assert bundle["summary"]["savings_rate"] == 30.0
    assert bundle["spending_by_category"]["top_category"]["category"] == "food"
    assert bundle["budgets"][0]["utilization_pct"] is not None
    assert bundle["budget_insights"]["over_budget"][0]["over_by"] == 5000.0
    assert bundle["goals"][0]["progress_pct"] == 20.0  # 100k/500k
    # budget_health folded in (one budget over -> < 100)
    assert bundle["metrics"]["budget_health"] is not None
    assert bundle["metrics"]["savings_rate"] == 30.0
    assert bundle["metrics"]["savings_assessment"] in {"below_baseline", "at_or_above_baseline"}
    assert bundle["finance_reference"]["emergency_fund_reference_months"] == 3


# --------------------------------------------------------------------------- #
# Dashboard Recommendation (§3.5) — confidential; cross-domain                 #
# --------------------------------------------------------------------------- #
async def test_dashboard_rec_bundle_shape(monkeypatch):
    summ = FinanceSummaryResponse(
        month="2026-07", income=100000.0, expenses=70000.0, savings=30000.0,
        savings_rate=30.0, last_month_income=95000.0, last_month_expense=72000.0,
        last_month_savings=23000.0,
    )
    spend = SpendingByCategoryResponse(days=30, total=70000.0, categories=[
        SpendingCategory(category="food", amount=50000.0, pct=71.4),
        SpendingCategory(category="transport", amount=20000.0, pct=28.6),
    ])
    goals = [
        {"name": "Hajj", "target": 500000.0, "saved": 100000.0, "ai_tip": "save", "emoji": "🕋"},
        {"name": "Car", "target": 60000.0, "saved": 30000.0, "ai_tip": "save", "emoji": "🚗"},
    ]
    snapshot = [
        {"symbol": "OGDC", "price": 150.0, "change_pct": 6.0, "volume": 5000},
        {"symbol": "HBL", "price": 100.0, "change_pct": -1.0, "volume": 800},
    ]
    # The nudge now reuses build_finance_context, so its extra reads must be
    # mocked too (income/expense series + budgets).
    series = IncomeExpenseResponse(months=1, series=[
        IncomeExpensePoint(month="2026-07", income=100000.0, expense=70000.0),
    ])
    budgets = [
        {"category": "food", "spent": 50000.0, "limit_amount": 50000.0, "period": "month", "tip": None},
    ]

    monkeypatch.setattr(ctx.finance_summary, "summary", _async(summ))
    monkeypatch.setattr(ctx.finance_summary, "income_expense_series", _async(series))
    monkeypatch.setattr(ctx.finance_summary, "spending_by_category", _async(spend))
    monkeypatch.setattr(ctx.finance_budgets, "list_budgets", _async(budgets))
    monkeypatch.setattr(ctx.finance_goals, "list_goals", _async(goals))
    monkeypatch.setattr(ctx.finance_bills, "list_bills", _async([]))
    monkeypatch.setattr(ctx.market_quotes, "market_snapshot", _async(snapshot))

    bundle = await ctx.build_dashboard_rec_context(None, user_id="u1")

    _assert_json_serializable(bundle)
    # Focus blocks (the pre-picked lead) still present.
    assert bundle["spending"]["top_category"] == "food"
    assert bundle["spending"]["amount"] == 50000.0
    assert "deviation_confidence" not in bundle["spending"]
    # most-urgent goal is the one reachable soonest (Car: 30k more at 30k/mo -> 1 month)
    assert bundle["goal"]["name"] == "Car"
    assert bundle["goal"]["months_to_target"] == 1
    # market mover by absolute % move (price/volume only, no signal)
    assert bundle["market_mover"]["symbol"] == "OGDC"
    assert "signal" not in bundle["market_mover"]
    # The FULL finance picture now flows in, not just the focus slices.
    assert bundle["summary"]["income"] == 100000.0
    assert bundle["summary"]["expenses"] == 70000.0
    assert isinstance(bundle["budgets"], list)
    assert len(bundle["goals"]) == 2  # every goal, not only the focus one
    assert "spending_by_category" in bundle
    assert "budget_insights" in bundle
    assert "bills" in bundle and "bill_insights" in bundle
