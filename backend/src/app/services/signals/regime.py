from __future__ import annotations

import numpy as np

from app.services.signals.schemas import RegimeAssessment


def assess_regime(kse_close: np.ndarray) -> RegimeAssessment:
    if len(kse_close) < 60:
        return RegimeAssessment(regime="NEUTRAL", score=0.0, reason="Market regime has limited benchmark history")
    close = kse_close[-1]
    sma50 = float(np.mean(kse_close[-50:]))
    sma200 = float(np.mean(kse_close[-200:])) if len(kse_close) >= 200 else sma50
    ret20 = close / kse_close[-21] - 1 if len(kse_close) > 21 and kse_close[-21] > 0 else 0.0
    vol = float(np.std(np.diff(np.log(kse_close[-21:]))) * np.sqrt(252)) if np.all(kse_close[-21:] > 0) else 0.0
    if vol > 0.35:
        return RegimeAssessment(regime="HIGH_VOLATILITY", score=-0.2, reason="KSE-100 volatility is elevated")
    if close > sma50 > sma200 and ret20 > 0:
        return RegimeAssessment(regime="BULLISH", score=0.35, reason="KSE-100 trend is bullish")
    if close < sma50 < sma200 and ret20 < 0:
        return RegimeAssessment(regime="BEARISH", score=-0.35, reason="KSE-100 trend is bearish")
    return RegimeAssessment(regime="NEUTRAL", score=0.0, reason="KSE-100 regime is neutral")
