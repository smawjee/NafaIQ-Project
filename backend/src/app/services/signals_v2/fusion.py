from __future__ import annotations

from app.services.signals_v2.constants import (
    PARTIAL_HISTORY_CONFIDENCE_CAP,
    TECHNICAL_CONFIDENCE_CAP,
    TECHNICAL_MODEL_VERSION,
)
from app.services.signals_v2.labels import SignalLabel, cap_signal, score_to_signal
from app.services.signals_v2.schemas import DataQuality, MlPrediction, RegimeAssessment, RiskAssessment, TechnicalRating


def fuse_signal(
    *,
    technical: TechnicalRating,
    ml: MlPrediction,  # parked in v3.0: retained for call/schema compatibility, not used
    risk: RiskAssessment,
    regime: RegimeAssessment,
    data_quality: DataQuality,
    features: dict,
) -> tuple[SignalLabel, float, float, str]:
    """Blend the technical rating with market context into a directional signal.

    v3.0: the technical rating drives the call. There is no ML fusion and no
    actionability gate that suppresses BUYs — bullish reads surface as BUY.
    Risk caps still bind: illiquid names cap at HOLD, extreme-volatility names
    cap at BUY (never STRONG BUY), stale data yields NO_SIGNAL.
    """
    if not data_quality.eligible or "NO_SIGNAL_STALE_DATA" in risk.caps:
        return SignalLabel.NO_SIGNAL, 0.0, 0.0, TECHNICAL_MODEL_VERSION

    rel = _bounded(float(features.get("relative_strength_kse20") or 0) * 8)
    volume = _bounded((float(features.get("volume_vs_20d") or 1) - 1) * 0.6)
    fundamentals = _fundamental_score(features)

    raw = (
        0.55 * technical.score
        + 0.20 * rel
        + 0.10 * volume
        + 0.10 * regime.score
        + 0.05 * fundamentals
    )

    label = score_to_signal(raw)
    if "MAX_HOLD_LOW_LIQUIDITY" in risk.caps:
        label = cap_signal(label, SignalLabel.HOLD)
    elif "MAX_BUY_EXTREME_VOLATILITY" in risk.caps:
        label = cap_signal(label, SignalLabel.BUY)

    rank_score = (raw + 1) * 50
    confidence = min(TECHNICAL_CONFIDENCE_CAP, 38 + abs(raw) * 45)
    confidence -= max(0.0, 40.0 - risk.liquidity_score) * 0.35
    confidence -= max(0.0, risk.volatility_score - 55.0) * 0.25
    if data_quality.status == "PARTIAL":
        confidence = min(confidence, PARTIAL_HISTORY_CONFIDENCE_CAP)
    if data_quality.freshness == "DELAYED":
        confidence = min(confidence, 60.0)
    confidence = max(0.0, min(95.0, confidence))
    if label == SignalLabel.HOLD:
        confidence = min(confidence, 60.0)
    return label, confidence, max(0.0, min(100.0, rank_score)), TECHNICAL_MODEL_VERSION


def _bounded(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _fundamental_score(features: dict) -> float:
    score = 0.0
    pe = features.get("pe")
    roe = features.get("roe")
    div_yield = features.get("div_yield")
    if isinstance(pe, (int, float)) and pe > 0:
        score += 0.25 if pe < 8 else -0.25 if pe > 25 else 0.0
    if isinstance(roe, (int, float)):
        score += 0.25 if roe > 15 else -0.15 if roe < 5 else 0.0
    if isinstance(div_yield, (int, float)) and div_yield > 5:
        score += 0.15
    return _bounded(score)
