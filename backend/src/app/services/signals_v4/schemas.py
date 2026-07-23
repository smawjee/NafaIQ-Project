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


class SignalV4Response(BaseModel):
    symbol: str
    as_of: date
    technical_setup: TechnicalSetup
    forecast: ForecastOutlook
    data_quality: dict[str, Any] = Field(default_factory=dict)


class PromotionDecision(BaseModel):
    allowed: bool
    status: Literal["VALIDATED", "RED"]
    reasons: list[str] = Field(default_factory=list)

