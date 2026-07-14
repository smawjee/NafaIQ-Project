"""Report schema tests: compliance-by-construction (§19.3).

A directive-style construction must be structurally impossible (no free-text
action/recommendation field; extras forbidden), the disclaimer is mandatory, and
every consideration must carry a hedge.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _base_kwargs(**over):
    kw = {
        "disclaimer": "Educational information only. Not financial advice.",
        "headline": "Markets were mixed today.",
        "observations": ["KSE-100 closed at 78500."],
    }
    kw.update(over)
    return kw


def test_market_brief_valid_construction():
    from app.schemas.reports import MarketBriefReport

    r = MarketBriefReport(**_base_kwargs())
    assert r.report_type == "market_brief"
    assert r.schema_version == 1
    assert r.lang == "en"
    assert r.considerations == []


def test_no_free_text_action_field_extras_forbidden():
    from app.schemas.reports import MarketBriefReport

    with pytest.raises(ValidationError):
        MarketBriefReport(**_base_kwargs(action="Sell 20% of HBL"))
    with pytest.raises(ValidationError):
        MarketBriefReport(**_base_kwargs(recommendation="Buy OGDC now"))


def test_disclaimer_is_required():
    from app.schemas.reports import MarketBriefReport

    kw = _base_kwargs()
    del kw["disclaimer"]
    with pytest.raises(ValidationError):
        MarketBriefReport(**kw)


def test_disclaimer_must_be_non_empty():
    from app.schemas.reports import MarketBriefReport

    with pytest.raises(ValidationError):
        MarketBriefReport(**_base_kwargs(disclaimer=""))


def test_consideration_requires_hedge():
    from app.schemas.reports import Consideration

    Consideration(consideration="Concentrated portfolios carry more risk",
                  hedge="one approach investors consider is diversification")
    with pytest.raises(ValidationError):
        Consideration(consideration="Sell HBL")  # missing hedge
    with pytest.raises(ValidationError):
        Consideration(consideration="x", hedge="")  # empty hedge


def test_citation_accepts_float_and_str_values():
    from app.schemas.reports import Citation

    c1 = Citation(value=12.5, source_key="networth.total", as_of="2026-07-14")
    c2 = Citation(value="Banking", source_key="allocation.top_sector", as_of="2026-07-14")
    assert c1.value == 12.5
    assert c2.value == "Banking"


def test_lang_literal_rejects_invalid():
    from app.schemas.reports import MarketBriefReport

    with pytest.raises(ValidationError):
        MarketBriefReport(**_base_kwargs(lang="fr"))
    assert MarketBriefReport(**_base_kwargs(lang="ur")).lang == "ur"


def test_all_five_report_models_exist_and_carry_type():
    from app.schemas.reports import (
        DashboardRecReport,
        FinanceReport,
        MarketBriefReport,
        PortfolioReport,
        StockAnalysisReport,
    )

    assert MarketBriefReport(**_base_kwargs()).report_type == "market_brief"
    assert StockAnalysisReport(**_base_kwargs(symbol="OGDC")).report_type == "stock_analysis"
    assert PortfolioReport(**_base_kwargs(period_days=30)).report_type == "portfolio"
    assert FinanceReport(**_base_kwargs()).report_type == "finance"
    assert DashboardRecReport(**_base_kwargs()).report_type == "dashboard_rec"


def test_verification_result_model():
    from app.schemas.reports import Mismatch, VerificationResult

    vr = VerificationResult(verified=False, mismatches=[
        Mismatch(field="obs[0]", source_key="x", expected=1.0, actual=2.0),
    ])
    assert vr.verified is False
    assert vr.mismatches[0].source_key == "x"
