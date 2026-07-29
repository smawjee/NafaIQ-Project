"""ReportSpec configs — the 5 report surfaces as data, not duplicated logic.

Each surface binds its report_type, Pydantic schema, prompt template,
confidential routing flag, guardrail profile, and context builder. The one
tested engine.generate_report path consumes these.

The prompt templates are plain strings the engine fills (no LLM here). Each
hard-wires the trust-engineering rules: output language, the bundle injected as
JSON with a "use only these values" guard, a delimited untrusted-data block,
per-number citations, and educational/no-directive framing with a disclaimer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from app.schemas.reports import (
    DEFAULT_DISCLAIMER,
    DashboardRecReport,
    FinanceReport,
    MarketBriefReport,
    PortfolioReport,
    StockAnalysisReport,
)
from app.services.ai import context as ctx
from app.services.ai.prompts import load_prompt, security_rules

ContextBuilder = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class ReportSpec:
    """Immutable config for one report surface."""

    report_type: str
    schema: type[BaseModel]
    prompt_template: str
    confidential: bool
    guardrail_profile: str
    context_builder: ContextBuilder


# Shared prompt scaffold every surface carries, loaded from
# prompts/report_scaffold.txt. Two-stage fill: {role}/{surface_instructions}/
# {DEFAULT_DISCLAIMER} are filled here; {lang}/{bundle_json}/{untrusted_data}
# are left literal (double-braced in the file) for the engine to fill at
# generation time. Surface bodies must stay brace-free so that second .format
# stays safe.
def _prompt(role: str, surface_instructions: str) -> str:
    return (security_rules() + "\n\n" + load_prompt("report_scaffold")).format(
        role=role,
        surface_instructions=surface_instructions,
        DEFAULT_DISCLAIMER=DEFAULT_DISCLAIMER,
    )


# The 5 specs.
REPORT_SPECS: dict[str, ReportSpec] = {
    "market_brief": ReportSpec(
        report_type="market_brief",
        schema=MarketBriefReport,
        confidential=False,  # shared, no user data
        guardrail_profile="shared_market",
        context_builder=ctx.build_market_brief_context,
        prompt_template=_prompt("daily market analyst", load_prompt("market_brief")),
    ),
    "stock_analysis": ReportSpec(
        report_type="stock_analysis",
        schema=StockAnalysisReport,
        confidential=False,  # shared, public data
        guardrail_profile="shared_stock",
        context_builder=ctx.build_stock_analysis_context,
        prompt_template=_prompt("equity research explainer", load_prompt("stock_analysis")),
    ),
    "portfolio": ReportSpec(
        report_type="portfolio",
        schema=PortfolioReport,
        confidential=True,  # per-user financial data -> Groq only
        guardrail_profile="confidential_portfolio",
        context_builder=ctx.build_portfolio_context,
        prompt_template=_prompt("portfolio educator", load_prompt("portfolio")),
    ),
    "finance": ReportSpec(
        report_type="finance",
        schema=FinanceReport,
        confidential=True,  # per-user financial data -> Groq only
        guardrail_profile="confidential_finance",
        context_builder=ctx.build_finance_context,
        prompt_template=_prompt("personal-finance educator", load_prompt("finance")),
    ),
    "dashboard_rec": ReportSpec(
        report_type="dashboard_rec",
        schema=DashboardRecReport,
        confidential=True,  # per-user financial data -> Groq only
        guardrail_profile="confidential_dashboard",
        context_builder=ctx.build_dashboard_rec_context,
        prompt_template=_prompt("financial wellbeing coach", load_prompt("dashboard_rec")),
    ),
}
