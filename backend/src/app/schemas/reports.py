"""AI report schemas — flat, compliance-by-construction (§4, §19.3, §19.10).

Design constraints:
- **No free-text `action`/`recommendation` field.** Reports expose structured
  `observations[]` and (where relevant) `considerations[]` — each consideration
  REQUIRES a `hedge` — plus a mandatory `disclaimer`. Imperative directives are
  therefore structurally impossible; the §7 phrase-scan is defense-in-depth.
- **Extras forbidden** (`extra='forbid'`): a caller cannot smuggle in an
  `action=`/`recommendation=` field.
- **Shallow** — top-level string sections + a flat `citations[]` list. Deeply
  nested schemas raise LLM error rates.
- Every report records its `schema_version` and `lang`.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Bump when the report shape changes; stored inside `content` so cached rows stay
# backward-readable (§19.10).
SCHEMA_VERSION = 1

DEFAULT_DISCLAIMER = "Educational information only. Not financial advice."


class Citation(BaseModel):
    """A single proof-carrying claim: the value the narrative cites, the bundle
    field it came from, and when it was current. The spine of §5 verification."""

    model_config = ConfigDict(extra="forbid")

    value: Union[float, str]
    source_key: str = Field(min_length=1)
    as_of: str


class Consideration(BaseModel):
    """An educational scenario. The `hedge` is mandatory so the framing stays
    non-directive by construction ("one approach investors consider…")."""

    model_config = ConfigDict(extra="forbid")

    consideration: str = Field(min_length=1)
    hedge: str = Field(min_length=1)


class ReportMetric(BaseModel):
    """Display-ready metric grounded in the fact bundle."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    value: Any
    source_key: Optional[str] = None
    interpretation: Optional[str] = None

    @model_validator(mode="after")
    def _normalize_source_key(self) -> "ReportMetric":
        self.source_key = self.source_key or ""
        return self


class ReportSection(BaseModel):
    """Detailed report section used by the v2 finance/portfolio reports."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    summary: str = Field(min_length=1)
    key_findings: list[str] = Field(default_factory=list)
    supporting_metrics: list[ReportMetric] = Field(default_factory=list)


class ActionItem(BaseModel):
    """Hedged, educational next step. Backend facts decide the amount."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    timeframe: Literal["now", "next_30_days", "next_90_days", "ongoing"] = "ongoing"
    priority: Literal["low", "medium", "high"] = "medium"
    source_keys: list[str] = Field(default_factory=list)


class HoldingReview(BaseModel):
    """Portfolio holding-level review, without ML prediction claims."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = ""
    summary: str = Field(min_length=1)
    risk_note: Optional[str] = None
    source_keys: list[str] = Field(default_factory=list)


class ReportBase(BaseModel):
    """Shared, flat report contract. All five surfaces extend it."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    lang: Literal["en", "ur"] = "en"
    as_of: Optional[str] = None
    headline: Optional[str] = None
    observations: Optional[list[str]] = None
    considerations: Optional[list[Consideration]] = None
    # Mandatory and non-empty: rendered, never optional (§7).
    disclaimer: str = Field(min_length=1)
    citations: Optional[list[Citation]] = None

    @model_validator(mode="after")
    def _normalize_base_fields(self) -> "ReportBase":
        self.headline = self.headline or "AI Report"
        self.observations = self.observations or []
        self.considerations = self.considerations or []
        self.citations = self.citations or []
        return self


class NarrativeReport(ReportBase):
    """A surface whose entire body IS `observations` — market brief, dashboard
    nudge. Unlike finance/portfolio, these have no sections to fall back on.

    So `observations` cannot be empty here. It has no floor on ReportBase (where
    Optional/None is right, because the section-based surfaces don't use it), and
    the result was a report that renders as a headline, a disclaimer, and nothing
    else — served, and then CACHED for the rest of the day. Observed live on
    2026-07-16: a dashboard_rec came back with 0 observations and 7 citations,
    and passed §5 verification trivially, because a narrative with no numbers in
    it has no numbers to catch.

    This raises inside Instructor's retry budget, so a thin draft is re-asked
    with the error attached rather than 503-ing the surface. One observation is
    always possible: an empty bundle still supports "no activity recorded yet",
    which needs no number and so invents nothing.
    """

    @model_validator(mode="after")
    def _require_a_narrative(self) -> "NarrativeReport":
        if not self.observations:
            raise ValueError(
                "observations must not be empty: this report has no other body, "
                "so an empty list renders as a headline with no content. Write "
                "at least one factual observation grounded in the bundle."
            )
        return self


class MarketBriefReport(NarrativeReport):
    report_type: Literal["market_brief"] = "market_brief"


class StockAnalysisReport(ReportBase):
    report_type: Literal["stock_analysis"] = "stock_analysis"
    symbol: str = Field(min_length=1)


class PortfolioReport(ReportBase):
    model_config = ConfigDict(extra="ignore")

    report_type: Literal["portfolio"] = "portfolio"
    schema_version: int = 2
    period_days: int = Field(gt=0)
    executive_summary: Union[str, ReportSection, None] = None
    portfolio_health: Optional[ReportSection] = None
    profit_loss_analysis: Optional[ReportSection] = None
    allocation_analysis: Optional[ReportSection] = None
    risk_analysis: Optional[ReportSection] = None
    holdings_analysis: list[HoldingReview] = Field(default_factory=list)
    action_plan: Union[list[ActionItem], ActionItem, ReportSection] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    ml_signal_status: Literal["not_available", "available"] = "not_available"
    ml_signal_note: Optional[str] = None

    @model_validator(mode="after")
    def _normalize_action_plan(self) -> "PortfolioReport":
        if isinstance(self.executive_summary, ReportSection):
            self.executive_summary = self.executive_summary.summary
        if isinstance(self.action_plan, ActionItem):
            self.action_plan = [self.action_plan]
        if isinstance(self.action_plan, ReportSection):
            self.action_plan = [
                ActionItem(
                    title=self.action_plan.title or "Portfolio review",
                    rationale=self.action_plan.summary,
                    timeframe="next_30_days",
                    priority="medium",
                    source_keys=[
                        m.source_key for m in self.action_plan.supporting_metrics
                    ],
                )
            ]
        return self


class FinanceReport(ReportBase):
    model_config = ConfigDict(extra="ignore")

    report_type: Literal["finance"] = "finance"
    schema_version: int = 2
    executive_summary: Union[str, ReportSection, None] = None
    financial_health: Optional[ReportSection] = None
    income_analysis: Optional[ReportSection] = None
    expense_analysis: Optional[ReportSection] = None
    cashflow_analysis: Optional[ReportSection] = None
    savings_analysis: Optional[ReportSection] = None
    budget_analysis: Optional[ReportSection] = None
    goal_progress: Optional[ReportSection] = None
    emergency_fund_review: Optional[ReportSection] = None
    action_plan: Union[list[ActionItem], ActionItem, ReportSection] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_action_plan(self) -> "FinanceReport":
        if isinstance(self.executive_summary, ReportSection):
            self.executive_summary = self.executive_summary.summary
        if isinstance(self.action_plan, ActionItem):
            self.action_plan = [self.action_plan]
        if isinstance(self.action_plan, ReportSection):
            self.action_plan = [
                ActionItem(
                    title=self.action_plan.title or "Finance review",
                    rationale=self.action_plan.summary,
                    timeframe="next_30_days",
                    priority="medium",
                    source_keys=[
                        m.source_key for m in self.action_plan.supporting_metrics
                    ],
                )
            ]
        return self


class DashboardRecReport(NarrativeReport):
    report_type: Literal["dashboard_rec"] = "dashboard_rec"
    confidence: Optional[float] = None
    view_target: Optional[str] = None


# --------------------------------------------------------------------------- #
# Verification result (§5)                                                    #
# --------------------------------------------------------------------------- #
class Mismatch(BaseModel):
    field: str
    source_key: Optional[str] = None
    expected: Optional[Union[float, str]] = None
    actual: Optional[Union[float, str]] = None


class VerificationResult(BaseModel):
    verified: bool
    mismatches: list[Mismatch] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Served-report envelope (§9) — the API response DTO                           #
# --------------------------------------------------------------------------- #
class ReportResponse(BaseModel):
    """What a client receives from every /ai/report/* endpoint.

    ``content`` is the validated LLM report serialized to a plain dict (one of
    the five surface schemas above) — kept as a dict because it is persisted as
    JSON and served back verbatim from cache, and because the surface type is
    already carried inside it via ``content["report_type"]``.
    """

    report_type: str
    content: dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    verified: bool = False
    created_at: Optional[str] = None
