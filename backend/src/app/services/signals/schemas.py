from __future__ import annotations

from datetime import date, datetime
from typing import Any, Final, Literal

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


class Recommendation(BaseModel):
    """A directional call with a probability the engine can actually defend.

    ``p`` is the measured frequency with which stocks in this cohort rose over
    the horizon — a counted rate with a Wilson interval, not a model score. The
    rating is derived from whether the *whole* interval clears an asymmetric
    threshold, so a wide interval abstains to HOLD by construction.
    """
    rating: Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
    horizon_sessions: int = 20
    p: float | None = Field(default=None, ge=0, le=1)
    p_lower: float | None = Field(default=None, ge=0, le=1)
    p_upper: float | None = Field(default=None, ge=0, le=1)
    #: The base rate the call is measured against — never assume 0.50, the
    #: measured PSX 20-session base rate is ~0.47.
    base_rate: float | None = Field(default=None, ge=0, le=1)
    #: Plain-language statement of what `p` is the probability OF.
    event: str = "rose over the next 20 trading sessions"
    #: Which historical cohort answered, e.g. "stocks after a large recent decline".
    basis: str | None = None
    sample_size: int = 0
    #: Median 20-session move of that cohort, relative to the universe.
    expected_move: float | None = None
    round_trip_cost: float | None = None
    suggested_stop_pct: float | None = None
    drivers: list[str] = Field(default_factory=list)
    #: Set whenever the rating is HOLD, explaining which bar was not cleared.
    abstain_reason: str | None = None
    #: True when the sell-side asymmetry was applied (sell evidence is stronger
    #: on PSX, so buy calls face a higher bar). Surfaced for transparency.
    asymmetric: bool = True


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


class SignalResponse(BaseModel):
    symbol: str
    as_of: date
    technical_setup: TechnicalSetup
    quality: QualityScore | None = None
    #: Tier 1 calibrated base-rate call. Present whenever the calibration
    #: artifact is loaded and the stock's cohort could be identified.
    recommendation: Recommendation | None = None
    forecast: ForecastOutlook
    context: MarketContext = Field(default_factory=MarketContext)
    # Explicit contract for the UI. The technical setup describes present
    # posture; the recommendation is a measured historical frequency. Neither
    # is a forecast, and the wording must not imply one.
    disclosure: str = (
        "Technical posture plus measured historical base rates — not a forecast."
    )
    data_quality: dict[str, Any] = Field(default_factory=dict)


class PromotionDecision(BaseModel):
    allowed: bool
    status: Literal["VALIDATED", "RED"]
    reasons: list[str] = Field(default_factory=list)


# --- Risk / regime value objects -------------------------------------------
# Carried over from the retired V2 package, which `risk.py` and `regime.py`
# still depend on. Only these two models and two thresholds survived; the rest
# of that module described V2 response shapes that no longer exist.

LOW_LIQUIDITY_SCORE: Final = 25.0
EXTREME_VOLATILITY_SCORE: Final = 85.0


class RiskAssessment(BaseModel):
    risk_level: Literal["LOW", "MODERATE", "HIGH", "EXTREME"]
    liquidity_score: float = Field(ge=0, le=100)
    volatility_score: float = Field(ge=0, le=100)
    caps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RegimeAssessment(BaseModel):
    regime: Literal["BULLISH", "NEUTRAL", "BEARISH", "HIGH_VOLATILITY"]
    score: float = Field(ge=-1, le=1)
    reason: str

