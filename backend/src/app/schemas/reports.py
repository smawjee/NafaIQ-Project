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

from pydantic import BaseModel, ConfigDict, Field

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


class ReportBase(BaseModel):
    """Shared, flat report contract. All five surfaces extend it."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    lang: Literal["en", "ur"] = "en"
    headline: str = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)
    considerations: list[Consideration] = Field(default_factory=list)
    # Mandatory and non-empty: rendered, never optional (§7).
    disclaimer: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class MarketBriefReport(ReportBase):
    report_type: Literal["market_brief"] = "market_brief"


class StockAnalysisReport(ReportBase):
    report_type: Literal["stock_analysis"] = "stock_analysis"
    symbol: str = Field(min_length=1)


class PortfolioReport(ReportBase):
    report_type: Literal["portfolio"] = "portfolio"
    period_days: int = Field(gt=0)


class FinanceReport(ReportBase):
    report_type: Literal["finance"] = "finance"


class DashboardRecReport(ReportBase):
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
