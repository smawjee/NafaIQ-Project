"""Signal-quality meta-score — how reliable is the *reading*, not the direction.

This deliberately replaces the old 'confidence %', which implied predictive
confidence the system cannot honestly claim. Quality answers a different,
answerable question: given coverage, indicator agreement, liquidity, history
depth and volatility, how much should you trust that the technical posture is a
*clean measurement* (vs noise)? It says nothing about what price will do next.
"""
from __future__ import annotations

from typing import Any, Optional


def measurement_quality(
    *,
    coverage: float,
    bullish: int,
    bearish: int,
    neutral: int,
    history_days: int,
    liquidity_score: Optional[float],
    volatility_score: Optional[float],
) -> dict[str, Any]:
    total = max(1, bullish + bearish + neutral)
    drivers: list[str] = []

    # 1. Coverage — how many of the 26 components actually computed.
    cov = _clamp01(coverage)
    if cov < 0.9:
        drivers.append("some indicators unavailable")

    # 2. Agreement — a lopsided vote is a cleaner reading than a 50/50 split.
    decisive = abs(bullish - bearish) / total
    if decisive < 0.25:
        drivers.append("indicators are mixed")

    # 3. History depth — MAs/oscillators stabilise with more confirmed bars.
    depth = _clamp01((history_days - 200) / 200) if history_days else 0.0
    if history_days < 260:
        drivers.append("limited confirmed history")

    # 4. Liquidity — thin names produce noisy indicators.
    liq = _clamp01((liquidity_score or 0) / 100)
    if (liquidity_score or 0) < 40:
        drivers.append("low liquidity adds noise")

    # 5. Volatility — extreme vol destabilises every reading (penalty).
    vol_pen = _clamp01(((volatility_score or 0) - 55) / 45)
    if (volatility_score or 0) >= 60:
        drivers.append("high volatility reduces stability")

    score = 100.0 * (
        0.30 * cov + 0.25 * decisive + 0.15 * depth + 0.15 * liq + 0.15 * (1 - vol_pen)
    )
    score = round(max(0.0, min(100.0, score)), 0)
    label = "High" if score >= 70 else "Moderate" if score >= 45 else "Low"
    return {"score": score, "label": label, "drivers": drivers[:3]}


def _clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0
