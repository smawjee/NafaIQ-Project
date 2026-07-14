"""Context assemblers — pull the exact rows each surface needs into a plain
JSON-serializable bundle. Each build_*_context applies cheap data-sanity guards
and folds in the deterministic confidence metrics (with None sentinels for
sparse data). The engine injects the bundle; verify.py resolves citations against it.

Key points:
- Every citable value sits at a stable dot-path (e.g. networth.total_market_value).
- conn_or_session is accepted for interface stability but unused — the data
  services manage their own DB connections.
- The EvidenceRetriever handles all unstructured text (today returns []);
  numerics never go through it.
- Pure/deterministic given fixed service outputs (tests mock the services).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Optional

import importlib

from app.schemas.market import OHLCVBar
from app.services import calculations as calc
from app.services.ai import confidence as conf
from app.services.ai.evidence import EvidenceRetriever, NullEvidenceRetriever

# Bind the submodule objects, not the re-exported functions. `from a.b import c`
# would grab the function the package re-exports (summary/history/heatmap/networth)
# and shadow the module; import_module always returns the module, so tests can
# monkeypatch the service functions on it.
finance_budgets = importlib.import_module("app.services.finance.budgets")
finance_goals = importlib.import_module("app.services.finance.goals")
finance_summary = importlib.import_module("app.services.finance.summary")
indicators_mod = importlib.import_module("app.services.indicators")
market_heatmap = importlib.import_module("app.services.market.heatmap")
market_history = importlib.import_module("app.services.market.history")
market_quotes = importlib.import_module("app.services.market.quotes")
portfolio_svc = importlib.import_module("app.services.portfolio.networth")
sector_map_mod = importlib.import_module("app.services.psx.sector_map")

# Sane bounds for the avg_cost/last-price ratio. A cost basis outside this band
# vs the live price is almost certainly bad data (the avg_cost=23 bug), so drop
# it rather than narrate it.
_SANE_RATIO_LOW = 0.01
_SANE_RATIO_HIGH = 100.0

# Savings-rate baseline. Fixed here (a product decision) so the LLM never
# invents the threshold.
_SAVINGS_BASELINE_PCT = 20.0

_STOCK_INDICATORS = ["rsi14", "macd", "sma20", "sma50", "sma200", "bollinger", "atr14"]


# helpers
def _today_str() -> str:
    return date.today().isoformat()


def _finite(x: Any) -> Optional[float]:
    """Return x as a finite float, else None (drops inf/nan/None/garbage)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _sane_avg_cost(avg_cost: Any, price: Any) -> Optional[float]:
    """avg_cost, only if finite, non-negative, and within a sane multiple of the
    last price. Otherwise None so the narrative omits it."""
    avg = _finite(avg_cost)
    if avg is None or avg < 0:
        return None
    p = _finite(price)
    if p is not None and p > 0:
        ratio = avg / p
        if ratio < _SANE_RATIO_LOW or ratio > _SANE_RATIO_HIGH:
            return None
    return avg


def _guard_holding(h: dict[str, Any]) -> dict[str, Any]:
    """Sanity-guarded projection of a holding row for the bundle."""
    shares = _finite(h.get("shares"))
    if shares is not None and shares < 0:  # drop negative shares
        shares = None
    return {
        "symbol": h.get("symbol"),
        "shares": shares,
        "avg_cost": _sane_avg_cost(h.get("avg_cost"), h.get("current_price")),
        "current_price": _finite(h.get("current_price")),
        "market_value": _finite(h.get("market_value")),
        "cost_basis": _finite(h.get("cost_basis")),
        "unrealized_pnl": _finite(h.get("unrealized_pnl")),
        "pnl_pct": _finite(h.get("pnl_pct")),
    }


def _as_dict(obj: Any) -> dict[str, Any]:
    """Coerce a pydantic response (or dict) into a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj) if obj else {}


# Market Brief — shared, no user data.
async def build_market_brief_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    cards = await market_quotes.index_cards()
    snapshot = await market_quotes.market_snapshot()
    sectors = await market_heatmap.sector_averages()
    announcements = await market_quotes.announcements(None, 10)
    ev = await evidence.retrieve("market news", None)

    by_code = {str(c.get("code", "")).upper(): c for c in cards}

    def _index(*codes: str) -> Optional[dict[str, Any]]:
        for code in codes:
            c = by_code.get(code)
            if c:
                return {
                    "close": _finite(c.get("close")),
                    "prev_close": _finite(c.get("prev_close")),
                    "change": _finite(c.get("change")),
                    "change_pct": _finite(c.get("change_pct")),
                    "date": c.get("date"),
                }
        return None

    priced = [s for s in snapshot if _finite(s.get("change_pct")) is not None]
    by_move = sorted(priced, key=lambda s: float(s["change_pct"]))

    def _mover(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": s.get("symbol"),
            "change_pct": _finite(s.get("change_pct")),
            "price": _finite(s.get("price")),
            "volume": s.get("volume"),
        }

    gainers = [_mover(s) for s in reversed(by_move[-5:])]
    losers = [_mover(s) for s in by_move[:5]]

    return {
        "as_of": _today_str(),
        "indices": {
            "kse100": _index("KSE100", "KSE-100", "KSE 100"),
            "kse30": _index("KSE30", "KSE-30", "KSE 30"),
        },
        "movers": {"gainers": gainers, "losers": losers},
        "breadth": {
            "advancers": sum(1 for s in priced if float(s["change_pct"]) > 0),
            "decliners": sum(1 for s in priced if float(s["change_pct"]) < 0),
            "unchanged": sum(1 for s in priced if float(s["change_pct"]) == 0),
        },
        "sectors": [
            {"name": s.get("name"), "pct": _finite(s.get("pct"))} for s in sectors
        ],
        "announcements": [
            {
                "title": a.get("title"),
                "symbol": a.get("symbol"),
                "as_of": a.get("posted_at"),
            }
            for a in announcements
        ],
        "evidence": ev,
    }


# Stock Analysis — shared, public data.
async def build_stock_analysis_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    symbol = (subject or "").upper()
    bars_n = int(days or 60)

    quote = await market_quotes.quote(symbol)
    fundamentals = await market_quotes.fundamentals(symbol)
    hist = await market_history.history(symbol, bars_n)
    announcements = await market_quotes.announcements(symbol, 10)
    dividends = await market_quotes.dividends(symbol)
    ev = await evidence.retrieve(f"{symbol} announcements", symbol)

    # Deterministic technical indicators from the OHLCV bars.
    bars: list[OHLCVBar] = []
    for b in hist:
        try:
            bars.append(OHLCVBar(**b))
        except Exception:
            continue
    ind = indicators_mod.compute_indicators(bars, _STOCK_INDICATORS)
    indicators = ind.indicators if ind else {}

    highs = [_finite(b.get("high")) for b in hist]
    lows = [_finite(b.get("low")) for b in hist]
    highs = [h for h in highs if h is not None]
    lows = [low for low in lows if low is not None]

    q = _as_dict(quote)
    f = _as_dict(fundamentals)

    return {
        "symbol": symbol,
        "as_of": _today_str(),
        "quote": {
            "price": _finite(q.get("price")),
            "change": _finite(q.get("change")),
            "change_pct": _finite(q.get("change_pct")),
            "volume": q.get("volume"),
            "day_high": _finite(q.get("day_high")),
            "day_low": _finite(q.get("day_low")),
        },
        "fundamentals": {
            "eps": _finite(f.get("eps")),
            "pe": _finite(f.get("pe")),
            "pb": _finite(f.get("pb")),
            "div_yield": _finite(f.get("div_yield")),
            "payout": _finite(f.get("payout")),
            "roe": _finite(f.get("roe")),
        },
        "indicators": indicators,
        "price_range": {
            "period_high": max(highs) if highs else None,
            "period_low": min(lows) if lows else None,
            "bars": len(hist),
        },
        "announcements": [
            {"title": a.get("title"), "as_of": a.get("posted_at")}
            for a in announcements
        ],
        "dividends": [
            {
                "per_share": _finite(d.get("per_share")),
                "payout_type": d.get("payout_type"),
                "ex_date": d.get("ex_date"),
                "bonus_pct": _finite(d.get("bonus_pct")),
            }
            for d in dividends
        ],
        "evidence": ev,
    }


# Portfolio — confidential; risk metrics folded in.
async def build_portfolio_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    window = int(days or 180)
    nw = await portfolio_svc.networth(user_id)
    hist = await portfolio_svc.portfolio_history(user_id, window)
    perf = await portfolio_svc.performance_vs_kse100(user_id, window)
    sector_map = await sector_map_mod.get_sector_map()
    ev = await evidence.retrieve("portfolio holdings", None)

    by_holding = nw.get("by_holding", []) or []
    guarded = [_guard_holding(h) for h in by_holding]

    # Allocation from the net-worth by_holding rows: the allocation() service is
    # portfolio-scoped but this report is user-scoped, so we reuse the same pure
    # calc functions over the user's holdings.
    alloc_stock = calc.allocation_by_stock(by_holding)
    alloc_sector = calc.allocation_by_sector(by_holding, sector_map)

    points = hist.get("points", []) if isinstance(hist, dict) else []
    # perf is date-aligned {value, benchmark}; split into two series.
    port_series = [{"value": _finite(p.get("value"))} for p in perf]
    bench_series = [{"value": _finite(p.get("benchmark"))} for p in perf]

    diversification = conf.diversification_score(guarded)
    volatility = conf.portfolio_volatility(
        [{"value": _finite(p.get("value"))} for p in points]
    )
    beta = conf.portfolio_beta(port_series, bench_series)
    band = conf.risk_band(diversification, volatility, beta)

    valued = [p for p in points if _finite(p.get("value")) is not None]
    peak = max(valued, key=lambda p: float(p["value"])) if valued else None
    trough = min(valued, key=lambda p: float(p["value"])) if valued else None

    networth = {
        k: nw.get(k)
        for k in (
            "total_market_value",
            "total_cost_basis",
            "total_unrealized_pnl",
            "total_unrealized_pnl_pct",
            "today_pnl",
            "today_pnl_pct",
            "portfolio_count",
            "holding_count",
        )
    }

    return {
        "as_of": _today_str(),
        "period_days": window,
        "networth": networth,
        "holdings": guarded,
        "allocation": {"by_stock": alloc_stock, "by_sector": alloc_sector},
        "history": {
            "start_value": _finite(valued[0]["value"]) if valued else None,
            "end_value": _finite(valued[-1]["value"]) if valued else None,
            "peak": {"date": peak.get("date"), "value": _finite(peak.get("value"))}
            if peak
            else None,
            "trough": {"date": trough.get("date"), "value": _finite(trough.get("value"))}
            if trough
            else None,
            "points_count": len(points),
        },
        "risk": {
            "diversification": diversification,
            "volatility": volatility,
            "beta": beta,
            "band": band,
        },
        "evidence": ev,
    }


# Finance — confidential; budget-health folded in.
async def build_finance_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    summ = _as_dict(await finance_summary.summary(user_id))
    series = _as_dict(await finance_summary.income_expense_series(user_id, 6))
    spend = _as_dict(await finance_summary.spending_by_category(user_id, 30))
    budgets = await finance_budgets.list_budgets(user_id)
    goals = await finance_goals.list_goals(user_id)
    ev = await evidence.retrieve("finance notes", None)

    budget_rows = [
        {
            "category": b.get("category"),
            "spent": _finite(b.get("spent")),
            "limit_amount": _finite(b.get("limit_amount") or b.get("limit")),
            "utilization_pct": calc.budget_usage(
                _finite(b.get("spent")) or 0.0,
                _finite(b.get("limit_amount") or b.get("limit")) or 0.0,
            ),
            "period": b.get("period"),
            # free text -> flows to the prompt's untrusted block.
            "tip": b.get("tip"),
        }
        for b in budgets
    ]
    goal_rows = [
        {
            "name": g.get("name"),
            "target": _finite(g.get("target")),
            "saved": _finite(g.get("saved")),
            "progress_pct": calc.goal_progress(
                _finite(g.get("saved")) or 0.0, _finite(g.get("target")) or 0.0
            ),
            "ai_tip": g.get("ai_tip"),
        }
        for g in goals
    ]

    categories = spend.get("categories", []) or []
    categories_sorted = sorted(
        categories, key=lambda c: _finite(c.get("amount")) or 0.0, reverse=True
    )
    top_category = categories_sorted[0] if categories_sorted else None

    budget_health = conf.budget_health_score(budgets)
    savings_rate = _finite(summ.get("savings_rate")) or 0.0
    assessment = (
        "at_or_above_baseline"
        if savings_rate >= _SAVINGS_BASELINE_PCT
        else "below_baseline"
    )

    return {
        "as_of": _today_str(),
        "summary": {
            "month": summ.get("month"),
            "income": _finite(summ.get("income")),
            "expenses": _finite(summ.get("expenses")),
            "savings": _finite(summ.get("savings")),
            "savings_rate": _finite(summ.get("savings_rate")),
            "last_month_income": _finite(summ.get("last_month_income")),
            "last_month_expense": _finite(summ.get("last_month_expense")),
            "last_month_savings": _finite(summ.get("last_month_savings")),
        },
        "income_expense_series": series.get("series", []),
        "spending_by_category": {
            "total": _finite(spend.get("total")),
            "categories": categories,
            "top_category": top_category,
        },
        "budgets": budget_rows,
        "goals": goal_rows,
        "metrics": {
            "budget_health": budget_health,
            "savings_rate": _finite(summ.get("savings_rate")),
            "savings_baseline": _SAVINGS_BASELINE_PCT,
            "savings_assessment": assessment,
        },
        "evidence": ev,
    }


# Dashboard Recommendation — confidential; cross-domain.
async def build_dashboard_rec_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    summ = _as_dict(await finance_summary.summary(user_id))
    spend = _as_dict(await finance_summary.spending_by_category(user_id, 30))
    goals = await finance_goals.list_goals(user_id)
    snapshot = await market_quotes.market_snapshot()
    ev = await evidence.retrieve("dashboard nudge", None)

    # Top spending category + deviation from a deterministic baseline (mean
    # category spend this period — no fabricated threshold).
    categories = spend.get("categories", []) or []
    amounts = [_finite(c.get("amount")) or 0.0 for c in categories]
    categories_sorted = sorted(
        categories, key=lambda c: _finite(c.get("amount")) or 0.0, reverse=True
    )
    top = categories_sorted[0] if categories_sorted else None
    baseline = (sum(amounts) / len(amounts)) if amounts else 0.0
    top_amount = _finite(top.get("amount")) if top else None
    deviation = (
        conf.spending_deviation_confidence(top_amount, baseline)
        if top_amount is not None
        else None
    )

    # Most-urgent goal: reachable soonest at the current savings rate.
    monthly_rate = _finite(summ.get("savings")) or 0.0
    best_goal: Optional[dict[str, Any]] = None
    best_months: Optional[int] = None
    for g in goals:
        saved = _finite(g.get("saved")) or 0.0
        target = _finite(g.get("target")) or 0.0
        months = conf.months_to_goal(saved, target, monthly_rate)
        if months is None:
            continue
        if best_months is None or months < best_months:
            best_months = months
            best_goal = g
    if best_goal is None and goals:
        best_goal = goals[0]  # none projectable -> just use the first

    goal_block = None
    if best_goal is not None:
        saved = _finite(best_goal.get("saved")) or 0.0
        target = _finite(best_goal.get("target")) or 0.0
        goal_block = {
            "name": best_goal.get("name"),
            "saved": _finite(best_goal.get("saved")),
            "target": _finite(best_goal.get("target")),
            "monthly_rate": monthly_rate,
            "months_to_target": best_months,
            "progress_pct": calc.goal_progress(saved, target),
            "ai_tip": best_goal.get("ai_tip"),
        }

    # Notable market mover — price/volume only, never a signal label.
    priced = [s for s in snapshot if _finite(s.get("change_pct")) is not None]
    mover = None
    if priced:
        m = max(priced, key=lambda s: abs(float(s["change_pct"])))
        mover = {
            "symbol": m.get("symbol"),
            "change_pct": _finite(m.get("change_pct")),
            "price": _finite(m.get("price")),
            "volume": m.get("volume"),
        }

    return {
        "as_of": _today_str(),
        "spending": {
            "top_category": top.get("category") if top else None,
            "amount": top_amount,
            "baseline": round(baseline, 4),
            "deviation_confidence": deviation,
        },
        "goal": goal_block,
        "market_mover": mover,
        "evidence": ev,
    }
