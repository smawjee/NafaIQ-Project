"""Portfolio context — confidential; risk metrics folded in."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from ._shared import (
    EvidenceRetriever,
    NullEvidenceRetriever,
    _finite,
    _guard_holding,
    _risk_label,
    _today_str,
    calc,
    conf,
    portfolio_svc,
    portfolio_trades,
    sector_map_mod,
)


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
