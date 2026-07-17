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

import asyncio
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
finance_bills = importlib.import_module("app.services.finance.bills")
finance_budgets = importlib.import_module("app.services.finance.budgets")
finance_goals = importlib.import_module("app.services.finance.goals")
finance_summary = importlib.import_module("app.services.finance.summary")
indicators_mod = importlib.import_module("app.services.indicators")
market_heatmap = importlib.import_module("app.services.market.heatmap")
market_history = importlib.import_module("app.services.market.history")
market_quotes = importlib.import_module("app.services.market.quotes")
portfolio_svc = importlib.import_module("app.services.portfolio.networth")
portfolio_trades = importlib.import_module("app.services.portfolio.trades")
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

_STOCK_INDICATOR_LABELS = {
    "rsi14": "14-day RSI",
    "macd": "MACD",
    "sma20": "20-day simple moving average",
    "sma50": "50-day simple moving average",
    "sma200": "200-day simple moving average",
    "bollinger": "20-day Bollinger Bands",
    "atr14": "14-day average true range",
}

_STOCK_INDICATOR_PERIODS = {
    "rsi14": 14,
    "sma20": 20,
    "sma50": 50,
    "sma200": 200,
    "bollinger": 20,
    "atr14": 14,
}

_EMERGENCY_FUND_REFERENCE_MONTHS = 3


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
        "previous_close": _finite(h.get("previous_close")),
        "market_value": _finite(h.get("market_value")),
        "cost_basis": _finite(h.get("cost_basis")),
        "unrealized_pnl": _finite(h.get("unrealized_pnl")),
        "pnl_pct": _finite(h.get("pnl_pct")),
        "today_pnl": _finite(h.get("today_pnl")),
        "today_base": _finite(h.get("today_base")),
    }


def _as_dict(obj: Any) -> dict[str, Any]:
    """Coerce a pydantic response (or dict) into a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj) if obj else {}


def _pct_change(current: Any, previous: Any) -> Optional[float]:
    cur = _finite(current)
    prev = _finite(previous)
    if cur is None or prev is None or prev == 0:
        return None
    return round(((cur - prev) / abs(prev)) * 100.0, 2)


def _sum_finite(values: list[Any]) -> float:
    return round(sum(v for v in (_finite(x) for x in values) if v is not None), 2)


def _risk_label(value: Optional[float], *, high_at: float, medium_at: float) -> str:
    if value is None:
        return "unknown"
    if value >= high_at:
        return "high"
    if value >= medium_at:
        return "medium"
    return "low"


# Market Brief — shared, no user data.
async def build_market_brief_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    # gather, not sequential awaits: these reads are independent, and run one
    # after another they summed to the user's whole wait. The dashboard nudge
    # measured 15.7s of context for a ~1s LLM call — the spinner WAS this.
    cards, snapshot, sectors, announcements, ev = await asyncio.gather(
        market_quotes.index_cards(),
        market_quotes.market_snapshot(),
        market_heatmap.sector_averages(),
        market_quotes.announcements(None, 10),
        evidence.retrieve("market news", None),
    )

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

    # Every PSX index card, not just KSE100/KSE30 — index_cards() already
    # returns them all (KMI30, sector/all-share indices, ...).
    all_indices = [
        {
            "code": c.get("code"),
            "close": _finite(c.get("close")),
            "prev_close": _finite(c.get("prev_close")),
            "change": _finite(c.get("change")),
            "change_pct": _finite(c.get("change_pct")),
            "date": c.get("date"),
        }
        for c in cards
    ]

    return {
        "as_of": _today_str(),
        "indices": {
            "kse100": _index("KSE100", "KSE-100", "KSE 100"),
            "kse30": _index("KSE30", "KSE-30", "KSE 30"),
        },
        "all_indices": all_indices,
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
                "category": a.get("category"),
                "url": a.get("url"),
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
    profile = await market_quotes.profile(symbol)
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
    p = _as_dict(profile)

    # Market cap = listed shares x current price. Computed here so it is a real
    # citable bundle value (the model may not do arithmetic).
    listed_shares = _finite(p.get("listed_shares"))
    price = _finite(q.get("price"))
    market_cap = (
        round(listed_shares * price, 2)
        if listed_shares is not None and price is not None
        else None
    )
    # Recent daily closes — the trend behind the indicators. Capped so the
    # bundle stays lean; the full high/low over the window is in price_range.
    price_history = [
        {"date": b.get("date"), "close": _finite(b.get("close")), "volume": b.get("volume")}
        for b in hist[-30:]
    ]

    return {
        "symbol": symbol,
        "as_of": _today_str(),
        "profile": {
            "name": p.get("name"),
            "sector": p.get("sector"),
            "listed_shares": listed_shares,
            "free_float": _finite(p.get("free_float")),
            "market_cap": market_cap,
        },
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
        "indicator_labels": {
            key: label for key, label in _STOCK_INDICATOR_LABELS.items() if key in indicators
        },
        "indicator_periods": {
            key: period for key, period in _STOCK_INDICATOR_PERIODS.items() if key in indicators
        },
        "price_range": {
            "period_high": max(highs) if highs else None,
            "period_low": min(lows) if lows else None,
            "bars": len(hist),
        },
        "price_history": price_history,
        "announcements": [
            {
                "title": a.get("title"),
                "symbol": a.get("symbol"),
                "category": a.get("category"),
                "url": a.get("url"),
                "as_of": a.get("posted_at"),
            }
            for a in announcements
        ],
        "dividends": [
            {
                "per_share": _finite(d.get("per_share")),
                "payout_type": d.get("payout_type"),
                "ex_date": d.get("ex_date"),
                "announcement_date": d.get("announcement_date"),
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
    # gather, not sequential awaits: these reads are independent, and run one
    # after another they summed to the user's whole wait. The dashboard nudge
    # measured 15.7s of context for a ~1s LLM call — the spinner WAS this.
    nw, hist, perf, sector_map, txns, ev = await asyncio.gather(
        portfolio_svc.networth(user_id),
        portfolio_svc.portfolio_history(user_id, window),
        portfolio_svc.performance_vs_kse100(user_id, window),
        sector_map_mod.get_sector_map(),
        portfolio_trades.list_stock_transactions(user_id, 20),
        evidence.retrieve("portfolio holdings", None),
    )

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
    holdings_with_value = [
        h for h in guarded if (_finite(h.get("market_value")) or 0.0) > 0
    ]
    pnl_leaders = sorted(
        holdings_with_value,
        key=lambda h: _finite(h.get("unrealized_pnl")) or 0.0,
        reverse=True,
    )
    stock_alloc_values = [
        v for v in (_finite(a.get("value")) for a in alloc_stock if isinstance(a, dict))
        if v is not None
    ]
    sector_alloc_values = [
        v for v in (_finite(a.get("value")) for a in alloc_sector if isinstance(a, dict))
        if v is not None
    ]
    top_stock_alloc = max(stock_alloc_values, default=None)
    top_sector_alloc = max(sector_alloc_values, default=None)
    concentration_risk = _risk_label(top_stock_alloc, high_at=40.0, medium_at=25.0)
    missing_prices = [
        h.get("symbol") for h in guarded if h.get("symbol") and h.get("current_price") is None
    ]

    return {
        "as_of": _today_str(),
        "period_days": window,
        "networth": networth,
        "holdings": guarded,
        "allocation": {"by_stock": alloc_stock, "by_sector": alloc_sector},
        "portfolio_insights": {
            "holding_count": len(holdings_with_value),
            "largest_holding_pct": top_stock_alloc,
            "largest_sector_pct": top_sector_alloc,
            "concentration_risk": concentration_risk,
            "biggest_gainers": pnl_leaders[:3],
            "biggest_losers": list(reversed(pnl_leaders[-3:])),
            "missing_price_symbols": missing_prices,
            "ml_signal_status": "not_available",
            "ml_signal_note": (
                "ML prediction signals are not enabled yet; this report uses "
                "holdings, current prices, allocation, history and rule-based risk metrics."
            ),
        },
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
            # Recent value points (capped) — the path behind start/end/peak/trough.
            "recent_points": [
                {"date": p.get("date"), "value": _finite(p.get("value"))}
                for p in points[-30:]
            ],
        },
        # Portfolio value vs the KSE-100 benchmark, date-aligned (capped).
        "performance_vs_benchmark": [
            {
                "date": p.get("date"),
                "value": _finite(p.get("value")),
                "benchmark": _finite(p.get("benchmark")),
            }
            for p in perf[-30:]
        ],
        # Recent trades — how the current position was built.
        "transactions": [
            {
                "symbol": t.get("symbol"),
                "side": t.get("side"),
                "quantity": t.get("quantity"),
                "price": _finite(t.get("price")),
                "fees": _finite(t.get("fees")),
                "executed_at": t.get("executed_at"),
            }
            for t in (txns or [])
        ],
        "risk": {
            "diversification": diversification,
            "volatility": volatility,
            "beta": beta,
            "band": band,
            "concentration": concentration_risk,
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
    # gather, not sequential awaits: these reads are independent, and run one
    # after another they summed to the user's whole wait. The dashboard nudge
    # measured 15.7s of context for a ~1s LLM call — the spinner WAS this.
    summ_r, series_r, spend_r, budgets, goals, bills, ev = await asyncio.gather(
        finance_summary.summary(user_id),
        finance_summary.income_expense_series(user_id, 6),
        finance_summary.spending_by_category(user_id, 30),
        finance_budgets.list_budgets(user_id),
        finance_goals.list_goals(user_id),
        finance_bills.list_bills(user_id),
        evidence.retrieve("finance notes", None),
    )
    summ, series, spend = _as_dict(summ_r), _as_dict(series_r), _as_dict(spend_r)

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
    over_budget_rows = []
    for b in budget_rows:
        if (
            b.get("spent") is not None
            and b.get("limit_amount") is not None
            and float(b["spent"]) > float(b["limit_amount"])
        ):
            row = dict(b)
            row["over_by"] = round(float(b["spent"]) - float(b["limit_amount"]), 2)
            over_budget_rows.append(row)
    goal_rows = [
        {
            "name": g.get("name"),
            "target": _finite(g.get("target")),
            "saved": _finite(g.get("saved")),
            "remaining": max(
                (_finite(g.get("target")) or 0.0) - (_finite(g.get("saved")) or 0.0),
                0.0,
            ),
            "progress_pct": calc.goal_progress(
                _finite(g.get("saved")) or 0.0, _finite(g.get("target")) or 0.0
            ),
            "ai_tip": g.get("ai_tip"),
        }
        for g in goals
    ]

    today = date.today()
    bill_rows = []
    for bl in bills:
        raw_due = bl.get("due_date")
        due_d = None
        if raw_due:
            try:
                due_d = date.fromisoformat(str(raw_due)[:10])
            except ValueError:
                due_d = None
        status = (bl.get("status") or "").upper()
        is_paid = status == "PAID"
        days_until_due = (due_d - today).days if due_d else None
        bill_rows.append({
            "name": bl.get("name"),
            "amount": _finite(bl.get("amount")),
            "due_date": str(raw_due) if raw_due else None,
            "status": status or None,
            "recurring": bool(bl.get("recurring")),
            "days_until_due": days_until_due,
            "is_overdue": bool(due_d is not None and not is_paid and due_d < today),
        })
    unpaid_bills = [b for b in bill_rows if b.get("status") != "PAID"]
    overdue_bills = [b for b in bill_rows if b.get("is_overdue")]
    due_soon_bills = [
        b for b in unpaid_bills
        if b.get("days_until_due") is not None and 0 <= b["days_until_due"] <= 7
    ]
    next_bill = min(
        (b for b in unpaid_bills if (b.get("days_until_due") or -1) >= 0),
        key=lambda b: b["days_until_due"],
        default=None,
    )

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
    income = _finite(summ.get("income")) or 0.0
    expenses = _finite(summ.get("expenses")) or 0.0
    savings = _finite(summ.get("savings")) or 0.0
    emergency_months = round(savings / expenses, 2) if expenses > 0 else None
    category_amounts = [
        c.get("amount") for c in categories if isinstance(c, dict)
    ]
    top_categories = categories_sorted[:5]
    total_goal_remaining = _sum_finite([g.get("remaining") for g in goal_rows])
    savings_gap_to_baseline = (
        round(max((income * (_SAVINGS_BASELINE_PCT / 100.0)) - savings, 0.0), 2)
        if income > 0
        else None
    )
    action_candidates: list[dict[str, Any]] = []
    if top_category and _finite(top_category.get("amount")) is not None:
        action_candidates.append({
            "type": "review_top_category",
            "category": top_category.get("category"),
            "amount": _finite(top_category.get("amount")),
            "source_keys": ["spending_by_category.top_category.amount"],
        })
    if over_budget_rows:
        over_by = round(
            float(over_budget_rows[0].get("spent") or 0.0)
            - float(over_budget_rows[0].get("limit_amount") or 0.0),
            2,
        )
        action_candidates.append({
            "type": "review_over_budget",
            "category": over_budget_rows[0].get("category"),
            "over_by": over_by,
            "source_keys": [
                "budget_insights.over_budget.0.spent",
                "budget_insights.over_budget.0.limit_amount",
            ],
        })
    if savings_gap_to_baseline and savings_gap_to_baseline > 0:
        action_candidates.append({
            "type": "savings_baseline_gap",
            "amount": savings_gap_to_baseline,
            "source_keys": ["finance_insights.savings_gap_to_baseline"],
        })

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
            "top_categories": top_categories,
            "category_count": len(categories),
            "largest_category_share_pct": (
                round(
                    ((_finite(top_category.get("amount")) or 0.0)
                     / (_sum_finite(category_amounts) or 1.0))
                    * 100.0,
                    2,
                )
                if top_category
                else None
            ),
        },
        "budgets": budget_rows,
        "budget_insights": {
            "over_budget": over_budget_rows,
            "over_budget_count": len(over_budget_rows),
            "within_budget_count": max(len(budget_rows) - len(over_budget_rows), 0),
        },
        "goals": goal_rows,
        "goal_insights": {
            "goal_count": len(goal_rows),
            "total_remaining": total_goal_remaining,
            "lowest_progress_goal": (
                min(goal_rows, key=lambda g: _finite(g.get("progress_pct")) or 0.0)
                if goal_rows
                else None
            ),
        },
        "bills": bill_rows,
        "bill_insights": {
            "bill_count": len(bill_rows),
            "unpaid_count": len(unpaid_bills),
            "overdue_count": len(overdue_bills),
            "due_within_7_days_count": len(due_soon_bills),
            "total_unpaid": _sum_finite([b.get("amount") for b in unpaid_bills]),
            "total_overdue": _sum_finite([b.get("amount") for b in overdue_bills]),
            "next_bill": next_bill,
        },
        "metrics": {
            "budget_health": budget_health,
            "savings_rate": _finite(summ.get("savings_rate")),
            "savings_baseline": _SAVINGS_BASELINE_PCT,
            "savings_assessment": assessment,
        },
        "finance_insights": {
            "income_change_pct": _pct_change(
                summ.get("income"), summ.get("last_month_income")
            ),
            "expense_change_pct": _pct_change(
                summ.get("expenses"), summ.get("last_month_expense")
            ),
            "savings_change_pct": _pct_change(
                summ.get("savings"), summ.get("last_month_savings")
            ),
            "emergency_fund_months": emergency_months,
            "savings_gap_to_baseline": savings_gap_to_baseline,
            "action_candidates": action_candidates,
        },
        "finance_reference": {
            "emergency_fund_reference_months": _EMERGENCY_FUND_REFERENCE_MONTHS,
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
    """Context for the daily nudge.

    Passes the user's FULL finance picture (the same bundle the finance report
    reasons over — income, expenses, savings vs baseline, every budget with
    over-budget flags, every goal with progress, emergency-fund cover, top
    spending) so the model can choose what actually matters, plus a notable
    market mover. On top of that it adds three pre-picked focus blocks
    (`spending`, `goal`, `market_mover`) so the prompt has a clear lead without
    re-deriving them. Reusing build_finance_context keeps every citation
    source_key identical to the finance report — no drift, no divergence.
    """
    # Run the finance bundle and the market snapshot concurrently.
    fin, snapshot = await asyncio.gather(
        build_finance_context(user_id=user_id, evidence=evidence),
        market_quotes.market_snapshot(),
    )

    # Focus block: top spending category vs a deterministic baseline (mean
    # category spend this period — no fabricated threshold).
    sbc = fin.get("spending_by_category", {}) or {}
    categories = sbc.get("categories", []) or []
    amounts = [_finite(c.get("amount")) or 0.0 for c in categories]
    categories_sorted = sorted(
        categories, key=lambda c: _finite(c.get("amount")) or 0.0, reverse=True
    )
    top = categories_sorted[0] if categories_sorted else None
    baseline = (sum(amounts) / len(amounts)) if amounts else 0.0
    top_amount = _finite(top.get("amount")) if top else None

    # Focus block: most-urgent goal — reachable soonest at the current savings
    # rate. Goals already carry progress_pct from the finance bundle.
    monthly_rate = _finite((fin.get("summary") or {}).get("savings")) or 0.0
    goals = fin.get("goals", []) or []
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
        goal_block = {
            "name": best_goal.get("name"),
            "saved": _finite(best_goal.get("saved")),
            "target": _finite(best_goal.get("target")),
            "monthly_rate": monthly_rate,
            "months_to_target": best_months,
            "progress_pct": best_goal.get("progress_pct"),
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

    # Full finance data + the three focus blocks. dict(fin) already carries
    # summary / budgets / budget_insights / goals / goal_insights /
    # spending_by_category / income_expense_series / as_of / evidence.
    bundle = dict(fin)
    bundle["spending"] = {
        "top_category": top.get("category") if top else None,
        "amount": top_amount,
        "baseline": round(baseline, 4),
    }
    bundle["goal"] = goal_block
    bundle["market_mover"] = mover
    return bundle
