from __future__ import annotations

from app.services.signals_v2.constants import (
    PARTIAL_HISTORY_CONFIDENCE_CAP,
    TECHNICAL_CONFIDENCE_CAP,
)
from app.services.signals_v2.labels import SignalLabel, cap_signal, score_to_signal, signed_strength
from app.services.signals_v2.schemas import DataQuality, MlPrediction, RegimeAssessment, RiskAssessment, TechnicalRating


def fuse_signal(
    *,
    technical: TechnicalRating,
    ml: MlPrediction,
    risk: RiskAssessment,
    regime: RegimeAssessment,
    data_quality: DataQuality,
    features: dict,
) -> tuple[SignalLabel, float, float, str]:
    if not data_quality.eligible or "NO_SIGNAL_STALE_DATA" in risk.caps:
        return SignalLabel.NO_SIGNAL, 0.0, 0.0, "technical-v2.0"

    rel = _bounded(float(features.get("relative_strength_kse20") or 0) * 8)
    volume = _bounded((float(features.get("volume_vs_20d") or 1) - 1) * 0.6)
    fundamentals = _fundamental_score(features)

    if ml.signal is not None and ml.status == "VALIDATED" and ml.eligible_for_fusion:
        raw = (
            0.35 * signed_strength(ml.signal)
            + 0.25 * technical.score
            + 0.15 * rel
            + 0.10 * volume
            + 0.10 * regime.score
            + 0.05 * fundamentals
        )
        model_version = ml.model_version or "ml-v2"
        agreement_bonus = 8 if signed_strength(ml.signal) * technical.score > 0 else -12
    else:
        raw = (
            0.55 * technical.score
            + 0.20 * rel
            + 0.10 * volume
            + 0.10 * regime.score
            + 0.05 * fundamentals
        )
        model_version = "technical-v2.0"
        agreement_bonus = 0

    label = score_to_signal(raw)
    if "MAX_HOLD_LOW_LIQUIDITY" in risk.caps:
        label = cap_signal(label, SignalLabel.HOLD)
    elif "MAX_BUY_EXTREME_VOLATILITY" in risk.caps:
        label = cap_signal(label, SignalLabel.BUY)
    label = _actionability_gate(label=label, technical=technical, ml=ml, risk=risk, features=features)

    rank_score = (raw + 1) * 50
    confidence = min(TECHNICAL_CONFIDENCE_CAP, 38 + abs(raw) * 45 + agreement_bonus)
    confidence -= max(0.0, 40.0 - risk.liquidity_score) * 0.35
    confidence -= max(0.0, risk.volatility_score - 55.0) * 0.25
    if data_quality.status == "PARTIAL":
        confidence = min(confidence, PARTIAL_HISTORY_CONFIDENCE_CAP)
    if data_quality.freshness == "DELAYED":
        confidence = min(confidence, 60.0)
    confidence = max(0.0, min(95.0, confidence))
    if label == SignalLabel.HOLD:
        confidence = min(confidence, 60.0)
    return label, confidence, max(0.0, min(100.0, rank_score)), model_version


def _bounded(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _actionability_gate(
    *,
    label: SignalLabel,
    technical: TechnicalRating,
    ml: MlPrediction,
    risk: RiskAssessment,
    features: dict,
) -> SignalLabel:
    """Make directional calls harder to earn than HOLD.

    Phase 0 showed price/technical BUY labels had too many false positives and
    negative excess returns after costs. Until a validated, fusion-eligible ML
    model exists, technical-v2 bullish calls are treated as HOLD/setup context.
    SELL/avoidance calls remain available because the historical replay shows
    materially better directional precision on the sell side.
    """
    if label in {SignalLabel.NO_SIGNAL, SignalLabel.HOLD}:
        return label

    if label in {SignalLabel.BUY, SignalLabel.STRONG_BUY}:
        if not (ml.status == "VALIDATED" and ml.eligible_for_fusion):
            return SignalLabel.HOLD
        if risk.risk_level == "EXTREME":
            return SignalLabel.HOLD
        if risk.risk_level == "HIGH" and technical.score < 0.45:
            return SignalLabel.HOLD
        if _num(features.get("relative_strength_kse20")) < -0.02 and _num(features.get("volume_vs_20d"), 1.0) < 1.2:
            return SignalLabel.HOLD if technical.score < 0.55 else SignalLabel.BUY
        if label is SignalLabel.STRONG_BUY and technical.score < 0.55:
            return SignalLabel.BUY
        return label

    if label in {SignalLabel.SELL, SignalLabel.STRONG_SELL}:
        if label is SignalLabel.STRONG_SELL and technical.score > -0.55:
            return SignalLabel.SELL
    return label


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
