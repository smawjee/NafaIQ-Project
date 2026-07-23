"""Publication contract shared by shadow and production scoring jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.signals_v4.events import validate_live_features
from app.services.signals_v4.policy import apply_forecast_policy

HORIZON_SESSIONS = 20


def prepare_forecast_row(
    *, symbol: str, event_id: str, issued_at: datetime, expires_at: datetime,
    p_outperform: float, expected_excess_net: float, interval_lower: float,
    interval_upper: float, model_version: str, feature_version: str,
    features: dict[str, Any], shadow: bool = False,
) -> dict[str, Any]:
    """Create a publishable or shadow row without accepting realized data."""
    validate_live_features(features)
    if expires_at <= issued_at or issued_at.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("forecast timestamps must be timezone-aware and ordered")
    decision = apply_forecast_policy(
        p_outperform=p_outperform,
        expected_excess_net=expected_excess_net,
        interval_lower=interval_lower,
        interval_upper=interval_upper,
    )
    status = "SHADOW" if shadow else "PUBLISHED" if decision.direction else "ABSTAINED"
    return {
        "symbol": symbol.upper(), "event_id": event_id, "issued_at": issued_at.astimezone(timezone.utc).isoformat(),
        "expires_at": expires_at.astimezone(timezone.utc).isoformat(), "horizon_sessions": HORIZON_SESSIONS,
        "status": status, "direction": decision.direction, "p_outperform": p_outperform,
        "expected_excess_net": expected_excess_net, "interval_lower": interval_lower,
        "interval_upper": interval_upper, "abstain_reason": decision.abstain_reason,
        "model_version": model_version, "feature_version": feature_version,
    }
