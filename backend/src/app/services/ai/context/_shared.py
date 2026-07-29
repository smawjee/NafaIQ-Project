"""Shared bindings, constants, and sanity helpers for the context builders.

The submodule objects are bound via ``import_module`` (not ``from a.b import c``)
so tests can monkeypatch the service functions on them; every builder resolves
the same module object, so a patch on ``market_quotes.quote`` is seen everywhere.
"""
from __future__ import annotations

import importlib
import math
from datetime import date
from typing import Any, Optional

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
