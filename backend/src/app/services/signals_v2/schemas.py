from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.services.signals_v2.labels import SignalLabel, display


Horizon = Literal["5D", "20D", "60D"]


class IndicatorVote(BaseModel):
    name: str
    vote: int = Field(ge=-1, le=1)
    weight: float = Field(default=1.0, ge=0)
    value: Optional[float] = None
    reason: str


class DataQuality(BaseModel):
    eligible: bool
    status: Literal["OK", "PARTIAL", "NO_SIGNAL"]
    history_days: int
    latest_ohlcv_date: Optional[date] = None
    snapshot_age_seconds: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    liquidity_score: float = Field(default=0, ge=0, le=100)
    freshness: Literal["LIVE", "DELAYED", "STALE", "UNKNOWN"] = "UNKNOWN"


class TechnicalRating(BaseModel):
    signal: SignalLabel
    score: float
    votes: list[IndicatorVote]
    reasons: list[str]
    warnings: list[str]


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


class MlPrediction(BaseModel):
    signal: Optional[SignalLabel] = None
    confidence: Optional[float] = None
    probabilities: Optional[dict[str, float]] = None
    model_version: Optional[str] = None
    status: Literal["UNAVAILABLE", "SHADOW", "VALIDATED"] = "UNAVAILABLE"
    eligible_for_fusion: bool = False
    source: str = "unknown"


class SignalV2Response(BaseModel):
    symbol: str
    horizon: Horizon
    signal: str
    confidence: float
    rank_score: float
    technical_signal: str
    technical_score: float
    ml_signal: Optional[str] = None
    ml_confidence: Optional[float] = None
    risk_level: str
    regime: str
    freshness: str
    reasons: list[str]
    warnings: list[str]
    indicator_votes: list[dict[str, Any]]
    probabilities: Optional[dict[str, float]] = None
    consensus: Optional[dict[str, Any]] = None          # TradingView technical-rating block
    consensus_agreement: Optional[str] = None           # AGREES | MIXED | DISAGREES
    trend_state: Optional[str] = None                   # UPTREND | WEAKENING | DOWNTREND | BASING | RANGE | UNKNOWN
    trend_score: Optional[float] = None
    risk_metrics: Optional[dict[str, Any]] = None
    features_snapshot: dict[str, Any] = Field(default_factory=dict)
    model_version: str
    engine_version: str
    predicted_at: datetime

    @classmethod
    def from_parts(
        cls,
        *,
        symbol: str,
        horizon: Horizon,
        signal: SignalLabel,
        confidence: float,
        rank_score: float,
        technical: TechnicalRating,
        ml: MlPrediction,
        risk: RiskAssessment,
        regime: RegimeAssessment,
        freshness: str,
        reasons: list[str],
        warnings: list[str],
        features_snapshot: dict[str, Any],
        model_version: str,
        engine_version: str,
        predicted_at: datetime,
    ) -> "SignalV2Response":
        return cls(
            symbol=symbol.upper(),
            horizon=horizon,
            signal=display(signal),
            confidence=round(confidence, 1),
            rank_score=round(rank_score, 1),
            technical_signal=display(technical.signal),
            technical_score=round(technical.score, 4),
            ml_signal=display(ml.signal) if ml.signal else None,
            ml_confidence=round(ml.confidence, 1) if ml.confidence is not None else None,
            risk_level=risk.risk_level,
            regime=regime.regime,
            freshness=freshness,
            reasons=reasons,
            warnings=warnings,
            indicator_votes=[v.model_dump() for v in technical.votes],
            probabilities=ml.probabilities,
            features_snapshot=features_snapshot,
            model_version=model_version,
            engine_version=engine_version,
            predicted_at=predicted_at,
        )


class SignalV1Compat(BaseModel):
    symbol: str
    signal: str
    confidence: float
    probabilities: dict[str, float]
    features_used: list[str]
    model_version: str


def to_v1(response: SignalV2Response) -> SignalV1Compat:
    return SignalV1Compat(
        symbol=response.symbol,
        signal="HOLD" if response.signal == "NO SIGNAL" else response.signal,
        confidence=response.confidence,
        probabilities=response.probabilities or {},
        features_used=["technical_rating", "relative_strength", "volume_confirmation"],
        model_version=response.engine_version,
    )
