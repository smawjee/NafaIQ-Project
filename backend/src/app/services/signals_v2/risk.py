from __future__ import annotations

from typing import Any

from app.services.signals_v2.constants import EXTREME_VOLATILITY_SCORE, LOW_LIQUIDITY_SCORE
from app.services.signals_v2.schemas import RiskAssessment


def liquidity_score(features: dict[str, Any]) -> float:
    turnover = float(features.get("turnover") or 0)
    volume = float(features.get("volume") or 0)
    turnover_score = min(70.0, turnover / 5_000_000 * 70.0)
    volume_score = min(30.0, volume / 100_000 * 30.0)
    return round(max(0.0, min(100.0, turnover_score + volume_score)), 1)


def assess_risk(features: dict[str, Any], *, freshness: str, liquidity: float) -> RiskAssessment:
    atr_pct = float(features.get("atr14_pct") or 0)
    vol20 = float(features.get("volatility_20d") or 0)
    volatility_score = min(100.0, atr_pct * 700 + vol20 * 80)
    caps: list[str] = []
    warnings: list[str] = []

    if liquidity < LOW_LIQUIDITY_SCORE:
        caps.append("MAX_HOLD_LOW_LIQUIDITY")
        warnings.append("Low liquidity reduces signal reliability")
    if volatility_score >= EXTREME_VOLATILITY_SCORE:
        caps.append("MAX_BUY_EXTREME_VOLATILITY")
        warnings.append("Extreme volatility caps bullish conviction")
    if freshness == "STALE":
        caps.append("NO_SIGNAL_STALE_DATA")
        warnings.append("Stale data blocks signal generation")

    if volatility_score >= 85:
        level = "EXTREME"
    elif volatility_score >= 60:
        level = "HIGH"
    elif volatility_score >= 30:
        level = "MODERATE"
    else:
        level = "LOW"

    return RiskAssessment(
        risk_level=level,
        liquidity_score=round(liquidity, 1),
        volatility_score=round(volatility_score, 1),
        caps=caps,
        warnings=warnings,
    )
