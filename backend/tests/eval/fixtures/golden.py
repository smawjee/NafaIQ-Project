"""Golden fixtures for the AI-reports EVAL GATE (spec §12).

Each factory returns a ``GoldenPair`` = ``(bundle, report)`` that represents a
CORRECT report for one surface:

- every numeric token the narrative uses is present in the bundle,
- every ``Citation.source_key`` is a REAL dot-path into the bundle (matching the
  key layouts produced by ``app.services.ai.context``),
- the framing is educational (hedged considerations, no directives),
- the mandatory ``disclaimer`` is set.

These are hand-authored so the eval gate has a deterministic, CI-safe ground
truth to verify against — no live LLM. The mutation helpers at the bottom derive
the FAILING variants (orphan number / bad citation) the gate must catch.

Bundle dot-paths mirror ``context.build_*_context`` exactly, e.g.
``bundle["networth"]["total_market_value"]``, ``bundle["risk"]["beta"]``,
``bundle["quote"]["price"]``, ``bundle["summary"]["savings_rate"]`` — so a golden
citation resolves the same way a real generated report's would.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.schemas.reports import (
    Citation,
    Consideration,
    FinanceReport,
    PortfolioReport,
    StockAnalysisReport,
)

DISCLAIMER = "Educational information only. Not financial advice."
AS_OF = "2026-07-14"


@dataclass
class GoldenPair:
    surface: str
    bundle: dict[str, Any]
    report: BaseModel


def _cite(value: float | str, source_key: str) -> Citation:
    return Citation(value=value, source_key=source_key, as_of=AS_OF)


# --------------------------------------------------------------------------- #
# stock_analysis — shared, public data (spec §3.2)                            #
# --------------------------------------------------------------------------- #
def stock_analysis_golden() -> GoldenPair:
    bundle: dict[str, Any] = {
        "symbol": "OGDC",
        "as_of": AS_OF,
        "quote": {
            "price": 145.30,
            "change": 2.15,
            "change_pct": 1.5,
            "volume": 3_200_000,
            "day_high": 146.0,
            "day_low": 143.1,
        },
        "fundamentals": {
            "eps": 28.4,
            "pe": 5.1,
            "pb": 0.9,
            "div_yield": 8.2,
            "payout": 42.0,
            "roe": 18.5,
        },
        "indicators": {
            "rsi14": 58.3,
            "sma20": 142.0,
            "sma50": 138.5,
            "atr14": 3.2,
        },
        "price_range": {"period_high": 152.0, "period_low": 121.5, "bars": 60},
        "announcements": [{"title": "Board meeting scheduled", "as_of": "2026-07-10"}],
        "dividends": [
            {"per_share": 4.0, "payout_type": "final", "ex_date": "2026-06-30", "bonus_pct": None}
        ],
        "evidence": [],
    }

    report = StockAnalysisReport(
        lang="en",
        symbol="OGDC",
        headline="Technical snapshot for OGDC.",
        observations=[
            "OGDC last traded at 145.30, up 1.5% on the session.",
            "The stock trades at a P/E of 5.1 with an RSI of 58.3.",
            "Over the last 60 bars it ranged between 121.5 and 152.0.",
        ],
        considerations=[
            Consideration(
                consideration="A P/E of 5.1 sits below the broader market average",
                hedge="valuation is one of many factors investors weigh",
            ),
        ],
        disclaimer=DISCLAIMER,
        citations=[
            _cite(145.30, "quote.price"),
            _cite(1.5, "quote.change_pct"),
            _cite(5.1, "fundamentals.pe"),
            _cite(58.3, "indicators.rsi14"),
            _cite(121.5, "price_range.period_low"),
            _cite(152.0, "price_range.period_high"),
            _cite(60, "price_range.bars"),
        ],
    )
    return GoldenPair("stock_analysis", bundle, report)


# --------------------------------------------------------------------------- #
# portfolio — confidential, risk metrics folded in (spec §3.3)                #
# --------------------------------------------------------------------------- #
def portfolio_golden() -> GoldenPair:
    bundle: dict[str, Any] = {
        "as_of": AS_OF,
        "period_days": 90,
        "networth": {
            "total_market_value": 1_250_000.0,
            "total_cost_basis": 1_100_000.0,
            "total_unrealized_pnl": 150_000.0,
            "total_unrealized_pnl_pct": 13.64,
            "today_pnl": 5_200.0,
            "today_pnl_pct": 0.42,
            "portfolio_count": 1,
            "holding_count": 4,
        },
        "holdings": [
            {"symbol": "OGDC", "shares": 500.0, "avg_cost": 120.0, "current_price": 145.3,
             "market_value": 72_650.0, "cost_basis": 60_000.0, "unrealized_pnl": 12_650.0, "pnl_pct": 21.08},
        ],
        "allocation": {
            "by_stock": [{"symbol": "OGDC", "pct": 40.0}],
            "by_sector": [{"sector": "Energy", "pct": 55.0}],
        },
        "history": {
            "start_value": 1_080_000.0,
            "end_value": 1_250_000.0,
            "peak": {"date": "2026-07-11", "value": 1_260_000.0},
            "trough": {"date": "2026-05-02", "value": 1_010_000.0},
            "points_count": 90,
        },
        "risk": {"diversification": 62.5, "volatility": 1.8, "beta": 0.95, "band": "Moderate"},
        "evidence": [],
    }

    report = PortfolioReport(
        lang="en",
        period_days=90,
        headline="Portfolio review over the last 90 days.",
        observations=[
            "Your holdings are worth 1,250,000, up 13.64% against a cost basis of 1,100,000.",
            "Diversification scores 62.5 with a beta of 0.95 versus the KSE-100.",
            "The portfolio started the window at 1,080,000 and ended at 1,250,000.",
        ],
        considerations=[
            Consideration(
                consideration="A moderate risk band reflects balanced concentration",
                hedge="risk bands are heuristics, not guarantees",
            ),
        ],
        disclaimer=DISCLAIMER,
        citations=[
            _cite(1_250_000.0, "networth.total_market_value"),
            _cite(13.64, "networth.total_unrealized_pnl_pct"),
            _cite(1_100_000.0, "networth.total_cost_basis"),
            _cite(62.5, "risk.diversification"),
            _cite(0.95, "risk.beta"),
            _cite(1_080_000.0, "history.start_value"),
            _cite(1_250_000.0, "history.end_value"),
            _cite("Moderate", "risk.band"),
        ],
    )
    return GoldenPair("portfolio", bundle, report)


# --------------------------------------------------------------------------- #
# finance — confidential, budget-health folded in (spec §3.4)                 #
# --------------------------------------------------------------------------- #
def finance_golden() -> GoldenPair:
    bundle: dict[str, Any] = {
        "as_of": AS_OF,
        "summary": {
            "month": "2026-07",
            "income": 350_000.0,
            "expenses": 240_000.0,
            "savings": 110_000.0,
            "savings_rate": 31.4,
            "last_month_income": 340_000.0,
            "last_month_expense": 250_000.0,
            "last_month_savings": 90_000.0,
        },
        "income_expense_series": [
            {"month": "2026-06", "income": 340_000.0, "expense": 250_000.0},
            {"month": "2026-07", "income": 350_000.0, "expense": 240_000.0},
        ],
        "spending_by_category": {
            "total": 240_000.0,
            "categories": [
                {"category": "Groceries", "amount": 60_000.0},
                {"category": "Transport", "amount": 30_000.0},
            ],
            "top_category": {"category": "Groceries", "amount": 60_000.0},
        },
        "budgets": [
            {"category": "Groceries", "spent": 60_000.0, "limit_amount": 75_000.0,
             "utilization_pct": 80.0, "period": "month", "tip": None},
        ],
        "goals": [
            {"name": "Emergency fund", "target": 600_000.0, "saved": 300_000.0,
             "progress_pct": 50.0, "ai_tip": None},
        ],
        "metrics": {
            "budget_health": 78.0,
            "savings_rate": 31.4,
            "savings_baseline": 20.0,
            "savings_assessment": "at_or_above_baseline",
        },
        "evidence": [],
    }

    report = FinanceReport(
        lang="en",
        headline="Monthly finance snapshot.",
        observations=[
            "Income was 350,000 against expenses of 240,000, leaving savings of 110,000.",
            "Your savings rate stood at 31.4%, above the 20.0% baseline.",
            "Budget health is 78 across tracked categories.",
        ],
        considerations=[
            Consideration(
                consideration="Sustaining a savings rate above the baseline supports goal progress",
                hedge="personal circumstances vary and this is not a plan",
            ),
        ],
        disclaimer=DISCLAIMER,
        citations=[
            _cite(350_000.0, "summary.income"),
            _cite(240_000.0, "summary.expenses"),
            _cite(110_000.0, "summary.savings"),
            _cite(31.4, "summary.savings_rate"),
            _cite(20.0, "metrics.savings_baseline"),
            _cite(78.0, "metrics.budget_health"),
        ],
    )
    return GoldenPair("finance", bundle, report)


# All golden surfaces, keyed by surface name.
def all_golden() -> list[GoldenPair]:
    return [stock_analysis_golden(), portfolio_golden(), finance_golden()]


# --------------------------------------------------------------------------- #
# Failing-variant derivations (the gate must CATCH these)                     #
# --------------------------------------------------------------------------- #
def with_orphan_number(pair: GoldenPair) -> BaseModel:
    """Inject a hallucinated number (absent from the bundle) into an observation.

    99_999 appears nowhere in any golden bundle -> a groundedness violation the
    un-cited-number coverage check must flag as a ``narrative`` mismatch.
    """
    obs = list(pair.report.observations) + [
        "An unexpected windfall of 99999 boosted the total this period."
    ]
    return pair.report.model_copy(update={"observations": obs})


def with_bad_citation(pair: GoldenPair) -> tuple[BaseModel, str]:
    """Corrupt the FIRST citation's value so it disagrees with the bundle.

    The narrative is left untouched (still grounded); only the citation lies, so
    this isolates the citation-resolution check. Returns the mutated report and
    the ``source_key`` expected to appear in the mismatches.
    """
    cits = [c.model_copy() for c in pair.report.citations]
    first = cits[0]
    source_key = first.source_key
    # Push the value far outside float tolerance while keeping it a number.
    bad_value = (float(first.value) + 999_999.0) if not isinstance(first.value, str) else "WRONG"
    cits[0] = first.model_copy(update={"value": bad_value})
    return pair.report.model_copy(update={"citations": cits}), source_key
