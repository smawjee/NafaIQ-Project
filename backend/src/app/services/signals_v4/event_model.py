"""Small, predeclared event-model boundary.

The model is intentionally not loaded by the API. Training jobs create an
artifact only after promotion.py accepts a complete holdout manifest; the API
reads the resulting published forecast rows.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.services.signals_v4.events import validate_live_features

EVENT_FEATURES = (
    "earnings_surprise",
    "eps_change",
    "profitability_quality",
    "investment_quality",
    "dividend_change",
    "insider_net_purchase",
    "material_event_score",
    "liquidity_log",
    "sector_relative_strength",
    "market_regime",
)


def vectorize_event(features: dict[str, Any]) -> np.ndarray:
    validate_live_features(features)
    return np.asarray([_number(features.get(name), 0.0) for name in EVENT_FEATURES], dtype=np.float64).reshape(1, -1)


def score_event(model: Any, features: dict[str, Any]) -> dict[str, float]:
    """Score a live event model; no realized-return field is accepted."""
    vector = vectorize_event(features)
    probability = float(model.predict_proba(vector)[0, 1])
    expected = float(model.predict(vector)[0])
    return {
        "p_outperform": probability,
        "expected_excess_net": expected,
    }


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else default
    except (TypeError, ValueError):
        return default
