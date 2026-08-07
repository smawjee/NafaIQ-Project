"""Compliance guardrails (§7, §19.3): compliance-by-construction assertion plus
a deterministic phrase-scan for imperative buy/sell/allocate directives."""
from __future__ import annotations

from app.schemas.reports import Consideration, MarketBriefReport
from app.services.ai import guardrails as g

DISC = "Educational information only. Not financial advice."


def test_imperative_sell_directive_flagged():
    hits = g.find_directives("Sell 20% of HBL immediately.")
    assert hits


def test_imperative_buy_directive_flagged():
    assert g.find_directives("You should buy OGDC now.")


def test_allocate_directive_flagged():
    assert g.find_directives("Allocate 30% of your portfolio to cement stocks.")


def test_hedged_consideration_passes_scan():
    text = ("Historically, concentrated portfolios carry higher risk; "
            "diversification is one approach investors consider.")
    assert g.find_directives(text) == []


def test_educational_observation_passes_scan():
    assert g.find_directives("KSE-100 closed 1.2% higher today.") == []


def test_assert_compliance_flags_missing_disclaimer_and_unhedged():
    violations = g.assert_compliance_by_construction(
        {"disclaimer": "", "considerations": [{"consideration": "x", "hedge": ""}]}
    )
    assert violations  # both the empty disclaimer and empty hedge flagged


def test_assert_compliance_passes_valid_report():
    r = MarketBriefReport(
        disclaimer=DISC,
        headline="Mixed session.",
        observations=["KSE-100 closed at 78500."],
        considerations=[Consideration(
            consideration="Concentrated portfolios carry more risk",
            hedge="diversification is one approach investors consider",
        )],
    )
    assert g.assert_compliance_by_construction(r) == []


def test_check_report_combines_scan_and_construction():
    # A directive smuggled into an observation is caught by the phrase-scan.
    r = MarketBriefReport(
        disclaimer=DISC,
        headline="Sell all your HBL shares now.",
        observations=["Buy 50% more OGDC today."],
    )
    assert g.check_report(r)  # non-empty => violations found


def test_dashboard_confidence_language_rejected():
    violations = g.check_report({
        "report_type": "dashboard_rec",
        "disclaimer": DISC,
        "observations": ["Dining is above baseline with confidence of 100."],
        "considerations": [{"consideration": "Review the pattern.", "hedge": "One option is to observe it over time."}],
    })
    assert "forbidden_confidence_language" in violations


def test_stock_signal_and_broken_day_label_rejected():
    violations = g.check_report({
        "report_type": "stock_analysis",
        "disclaimer": DISC,
        "symbol": "HBL",
        "observations": ["The —-day moving average supports a STRONG BUY label."],
        "considerations": [{"consideration": "Technical readings are historical.", "hedge": "They may not forecast future prices."}],
    })
    assert "broken_indicator_period_label" in violations
    assert "forbidden_signal_language" in violations


def test_thin_finance_v2_rejected():
    section = {
        "summary": "Expenses are high.",
        "key_findings": ["One finding"],
        "supporting_metrics": [{"label": "Expenses", "value": 10, "source_key": "summary.expenses"}],
    }
    violations = g.check_report({
        "report_type": "finance",
        "schema_version": 2,
        "disclaimer": DISC,
        "executive_summary": "Short summary.",
        "financial_health": section,
        "income_analysis": section,
        "expense_analysis": section,
        "cashflow_analysis": section,
        "savings_analysis": section,
        "budget_analysis": section,
        "goal_progress": section,
        "emergency_fund_review": section,
        "action_plan": [{"title": "Review", "rationale": "Review data.", "timeframe": "ongoing", "priority": "medium"}],
    })
    assert "thin_v2_report:executive_summary" in violations
    assert "thin_v2_section:financial_health" in violations


def test_missing_metric_source_rejected():
    section = {
        "summary": "This section has enough words to pass the short summary check for testing.",
        "key_findings": ["Finding one", "Finding two"],
        "supporting_metrics": [{"label": "Metric", "value": 10, "source_key": ""}],
    }
    violations = g.check_report({
        "report_type": "finance",
        "schema_version": 2,
        "disclaimer": DISC,
        "executive_summary": "This executive summary contains enough words to avoid the short summary failure and isolate missing source behavior in the test case.",
        "financial_health": section,
        "income_analysis": section,
        "expense_analysis": section,
        "cashflow_analysis": section,
        "savings_analysis": section,
        "budget_analysis": section,
        "goal_progress": section,
        "emergency_fund_review": section,
        "action_plan": [{"title": "Review", "rationale": "Review data.", "timeframe": "ongoing", "priority": "medium"}],
    })
    assert "missing_metric_source:financial_health[0]" in violations


def test_portfolio_holding_symbol_and_sources_required():
    section = {
        "summary": "This section has enough words to pass the short summary check for testing.",
        "key_findings": ["Finding one", "Finding two"],
        "supporting_metrics": [{"label": "Metric", "value": 10, "source_key": "networth.total_market_value"}],
    }
    violations = g.check_report({
        "report_type": "portfolio",
        "schema_version": 2,
        "disclaimer": DISC,
        "executive_summary": "This executive summary contains enough words to avoid the short summary failure and isolate holding validation behavior in this test case.",
        "portfolio_health": section,
        "profit_loss_analysis": section,
        "allocation_analysis": section,
        "risk_analysis": section,
        "holdings_analysis": [{"symbol": "", "summary": "This holding summary is long enough for the word-count guardrail but has no symbol or source keys."}],
        "action_plan": [{"title": "Review", "rationale": "Review data.", "timeframe": "ongoing", "priority": "medium"}],
        "ml_signal_status": "not_available",
    })
    assert "missing_v2_holding_symbol:0" in violations
    assert "missing_v2_holding_sources:0" in violations


# --------------------------------------------------------------------------- #
# descriptive prose is not a directive                                        #
# --------------------------------------------------------------------------- #
def test_descriptive_market_prose_is_not_flagged_as_advice():
    """`imperative-verb-amount` matched the NOUN forms too.

    Any sentence containing "increase", "move", "shift" or "reduce" alongside a
    number was rejected as a directive — which on a market brief is the entire
    job. A live brief failed outright on "an increase, while the KSE-30 …".
    """
    for text in (
        "The index posted an increase, while the KSE-30 gained 1.06%.",
        "Spending saw a reduction of 12% versus last month.",
        "A shift toward banking accounted for 40% of the move.",
        "Your savings rate moved to 83.8% this month.",
        "The 30-day trend shows a 2.5% increase in volume.",
    ):
        assert g.find_directives(text) == [], text


def test_genuine_directives_are_still_caught():
    for text in (
        "You should reduce dining by 5000.",
        "Increase your allocation to banks by 10%.",
        "Sell 100 shares of HBL.",
        "We recommend increasing your exposure.",
        "You should buy 50 shares.",
        "Buy OGDC.",
    ):
        assert g.find_directives(text), text
