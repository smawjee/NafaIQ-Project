from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TechnicalComponent(BaseModel):
    name: str
    vote: Literal[-1, 0, 1]
    value: float | None = None
    reason: str


class TechnicalSetup(BaseModel):
    status: Literal["available", "unavailable"]
    rating: str | None = None
    score: float | None = None
    bar_date: date | None = None
    coverage: float = Field(default=0.0, ge=0, le=1)
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    components: list[TechnicalComponent] = Field(default_factory=list)
    version: str
    reason_code: str | None = None


class ForecastOutlook(BaseModel):
    status: Literal["published", "shadow", "abstained", "stale", "unavailable"]
    direction: Literal["OUTPERFORM", "UNDERPERFORM"] | None = None
    horizon_sessions: int = 20
    event_source: dict[str, Any] | None = None
    p_outperform: float | None = Field(default=None, ge=0, le=1)
    expected_excess_net: float | None = None
    interval: dict[str, float] | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    model_version: str | None = None
    abstain_reason: str | None = None
    # Plain-language line for the UI when no validated model is promoted.
    headline: str = "No validated forecast yet"


class CorporateEvent(BaseModel):
    """A point-in-time disclosure — factual context, never a prediction."""
    event_type: str                           # EARNINGS | DIVIDEND | INSIDER | MATERIAL | OTHER
    title: str = ""
    published_at: datetime | None = None
    period_end: date | None = None
    source_url: str | None = None


class EarningsSummary(BaseModel):
    """Descriptive point-in-time earnings facts — never a prediction."""
    as_of_period: str | None = None           # fiscal quarter the figures are for, e.g. '2026Q3'
    eps_latest: float | None = None
    eps_change: float | None = None           # YoY change vs same quarter last year (fraction)
    earnings_surprise: float | None = None    # SUE: std devs from the firm's own YoY history
    eps_ttm: float | None = None
    eps_ttm_growth: float | None = None
    profitability_quality: float | None = None  # latest ROE/net-margin (fraction)
    quarters_available: int = 0


class RelativeRank(BaseModel):
    """Where this stock sits vs the liquid universe today — descriptive, not a call."""
    composite_percentile: float | None = None   # 0..100 across the ranked universe
    universe_size: int | None = None
    as_of: date | None = None
    factors: dict[str, float] = Field(default_factory=dict)  # factor -> percentile


class QualityScore(BaseModel):
    """Reliability of the *measurement* (not the direction). Replaces confidence %."""
    score: float                              # 0..100
    label: str                                # High | Moderate | Low
    drivers: list[str] = Field(default_factory=list)


class MarketContext(BaseModel):
    """Honest, deterministic context — descriptive posture, never a prediction."""
    trend_state: str | None = None            # UPTREND | DOWNTREND | BASING | WEAKENING | RANGE | UNKNOWN
    trend_score: float | None = None
    regime: str | None = None                 # BULLISH | BEARISH | NEUTRAL | HIGH_VOLATILITY
    risk_level: str | None = None             # LOW | MODERATE | HIGH | EXTREME
    liquidity_score: float | None = None
    volatility_score: float | None = None
    flow: dict[str, Any] | None = None        # market-wide FIPI foreign-flow summary
    relative_rank: RelativeRank | None = None
    # Vol / suggested-stop / expected-move + PSX-calibrated historical base rates
    # (continuation = empirical "of such setups, X% did Y over 20 sessions, n=…").
    risk_metrics: dict[str, Any] | None = None
    # Measured base rate for THIS rating over PSX history {p_up, median_return, n, …}.
    rating_base_rate: dict[str, Any] | None = None
    recent_events: list[CorporateEvent] = Field(default_factory=list)
    earnings: EarningsSummary | None = None
    warnings: list[str] = Field(default_factory=list)


class SignalV4Response(BaseModel):
    symbol: str
    as_of: date
    technical_setup: TechnicalSetup
    quality: QualityScore | None = None
    forecast: ForecastOutlook
    context: MarketContext = Field(default_factory=MarketContext)
    # Explicit contract for the UI: this response is descriptive analysis.
    disclosure: str = "Technical analysis and market context — not a forecast."
    data_quality: dict[str, Any] = Field(default_factory=dict)


class PromotionDecision(BaseModel):
    allowed: bool
    status: Literal["VALIDATED", "RED"]
    reasons: list[str] = Field(default_factory=list)

