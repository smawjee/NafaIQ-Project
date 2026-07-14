"""ReportSpec tests (§4.5, §19.1, §19.3, §19.4, §19.6).

The 5 surfaces are DATA, not duplicated code: each is a `ReportSpec` binding a
report_type to its schema, prompt template, confidentiality flag, guardrail
profile, and context builder. The prompt templates carry the trust-engineering
instructions (bundle-only facts, per-value citation, prompt-injection delimiting,
educational framing + mandatory disclaimer, output language).
"""
from __future__ import annotations

import inspect

from app.schemas.reports import (
    DashboardRecReport,
    FinanceReport,
    MarketBriefReport,
    PortfolioReport,
    StockAnalysisReport,
)
from app.services.ai import context as ctx
from app.services.ai.specs import REPORT_SPECS, ReportSpec

EXPECTED = {
    "market_brief": (MarketBriefReport, False),
    "stock_analysis": (StockAnalysisReport, False),
    "portfolio": (PortfolioReport, True),
    "finance": (FinanceReport, True),
    "dashboard_rec": (DashboardRecReport, True),
}


def test_all_five_specs_present():
    assert set(REPORT_SPECS) == set(EXPECTED)
    for rt, spec in REPORT_SPECS.items():
        assert isinstance(spec, ReportSpec)
        assert spec.report_type == rt


def test_schema_matches_report_type():
    for rt, (schema, _conf) in EXPECTED.items():
        assert REPORT_SPECS[rt].schema is schema


def test_confidential_flags_match_routing_policy():
    # §4.5: shared (no user data) reports are not confidential; per-user are.
    for rt, (_schema, confidential) in EXPECTED.items():
        assert REPORT_SPECS[rt].confidential is confidential


def test_context_builder_is_wired_and_async():
    for rt, spec in REPORT_SPECS.items():
        assert callable(spec.context_builder)
        assert inspect.iscoroutinefunction(spec.context_builder)


def test_context_builders_point_at_matching_assembler():
    assert REPORT_SPECS["market_brief"].context_builder is ctx.build_market_brief_context
    assert REPORT_SPECS["stock_analysis"].context_builder is ctx.build_stock_analysis_context
    assert REPORT_SPECS["portfolio"].context_builder is ctx.build_portfolio_context
    assert REPORT_SPECS["finance"].context_builder is ctx.build_finance_context
    assert REPORT_SPECS["dashboard_rec"].context_builder is ctx.build_dashboard_rec_context


def test_guardrail_profile_present():
    for spec in REPORT_SPECS.values():
        assert isinstance(spec.guardrail_profile, str)
        assert spec.guardrail_profile


def test_prompt_templates_carry_language_placeholder():
    # §19.4: the prompt fixes the output language via {lang}.
    for spec in REPORT_SPECS.values():
        assert "{lang}" in spec.prompt_template


def test_prompt_templates_inject_bundle_json_literally():
    # §5: bundle injected as literal JSON with a "use ONLY these values" guard.
    for spec in REPORT_SPECS.values():
        tpl = spec.prompt_template
        assert "{bundle_json}" in tpl
        assert "ONLY" in tpl  # "use ONLY these values"


def test_prompt_templates_have_prompt_injection_guard():
    # §19.6: user text lives in a delimited untrusted block treated as data.
    for spec in REPORT_SPECS.values():
        tpl = spec.prompt_template
        assert "{untrusted_data}" in tpl
        low = tpl.lower()
        assert "never" in low and "instruction" in low  # "never as instructions"
        assert "data" in low


def test_prompt_templates_require_source_key_citations():
    # §4/§5: every number cited with a source_key matching a bundle key.
    for spec in REPORT_SPECS.values():
        assert "source_key" in spec.prompt_template


def test_prompt_templates_enforce_educational_framing_and_disclaimer():
    # §7/§19.3: educational/no-directive framing + mandatory disclaimer.
    for spec in REPORT_SPECS.values():
        low = spec.prompt_template.lower()
        assert "educational" in low
        assert "disclaimer" in low


def test_prompt_templates_forbid_directives():
    # §7: no imperative buy/sell/allocate directives.
    for spec in REPORT_SPECS.values():
        low = spec.prompt_template.lower()
        assert "not financial advice" in low or "not advice" in low
