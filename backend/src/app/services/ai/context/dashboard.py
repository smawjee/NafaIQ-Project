"""Dashboard Recommendation context — confidential; cross-domain."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from ._shared import (
    EvidenceRetriever,
    NullEvidenceRetriever,
    _finite,
    conf,
    market_quotes,
)
from .finance import build_finance_context


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
