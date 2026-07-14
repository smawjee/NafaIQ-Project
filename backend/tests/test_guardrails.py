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
