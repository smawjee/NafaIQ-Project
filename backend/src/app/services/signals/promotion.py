"""Hard gates for model promotion and forecast publication."""
from __future__ import annotations

from typing import Any

from app.services.signals.schemas import ForecastOutlook, PromotionDecision
from app.services.signals.policy import apply_forecast_policy

MIN_EVENTS = 1500
MIN_SYMBOLS = 120
MIN_HOLDOUT_FORECASTS = 200
MIN_POSITIVE_FOLDS = 3
MIN_PRECISION = 0.60
MAX_ECE = 0.05
MIN_DSR = 0.95
MAX_PBO = 0.20


def evaluate_promotion(manifest: dict[str, Any]) -> PromotionDecision:
    """Validate the actual keyed manifest shape before an artifact can publish."""
    reasons: list[str] = []
    if str(manifest.get("status", "")).upper() not in {"VALIDATED", "EVALUATED"}:
        reasons.append("manifest status is not validated")
    if int(manifest.get("eligible_events", 0)) < MIN_EVENTS:
        reasons.append(f"eligible events below {MIN_EVENTS}")
    if int(manifest.get("symbols", 0)) < MIN_SYMBOLS:
        reasons.append(f"symbols below {MIN_SYMBOLS}")
    if int(manifest.get("holdout_forecasts", 0)) < MIN_HOLDOUT_FORECASTS:
        reasons.append(f"holdout forecasts below {MIN_HOLDOUT_FORECASTS}")
    if int(manifest.get("positive_folds", 0)) < MIN_POSITIVE_FOLDS:
        reasons.append("fewer than three positive walk-forward folds")
    if float(manifest.get("precision", 0)) < MIN_PRECISION:
        reasons.append("precision below 0.60")
    if float(manifest.get("ece", 1)) > MAX_ECE:
        reasons.append("ECE above 0.05")
    if float(manifest.get("dsr", 0)) < MIN_DSR:
        reasons.append("deflated Sharpe ratio below 0.95")
    if float(manifest.get("pbo", 1)) > MAX_PBO:
        reasons.append("probability of backtest overfitting above 0.20")
    return PromotionDecision(allowed=not reasons, status="VALIDATED" if not reasons else "RED", reasons=reasons)


def forecast_from_row(row: dict[str, Any], *, now=None) -> ForecastOutlook:
    """Map only persisted prediction fields; realized outcomes are never accepted."""
    from datetime import datetime, timezone
    current = now or datetime.now(timezone.utc)
    issued = _dt(row.get("issued_at"))
    expires = _dt(row.get("expires_at"))
    horizon = int(row.get("horizon_sessions") or 0)
    event_source = row.get("event_source")
    if horizon != 20:
        status = "unavailable"
        reason = "WRONG_HORIZON"
    elif not issued or not expires:
        status = "unavailable"
        reason = "INCOMPLETE_FORECAST"
    elif expires <= current:
        status = "stale"
        reason = "STALE_RUN"
    else:
        status = str(row.get("status", "UNAVAILABLE")).lower()
        reason = None
    if status in {"published", "shadow"} and not event_source:
        status = "abstained"
        reason = "NO_QUALIFYING_EVENT"
    decision = apply_forecast_policy(
        p_outperform=_float(row.get("p_outperform")),
        expected_excess_net=_float(row.get("expected_excess_net")),
        interval_lower=_float(row.get("interval_lower")),
        interval_upper=_float(row.get("interval_upper")),
    )
    if status == "published" and decision.direction is None:
        status = "abstained"
        reason = decision.abstain_reason
    direction = decision.direction if status in {"published", "shadow"} else None
    return ForecastOutlook(
        status=status if status in {"published", "shadow", "abstained", "stale", "unavailable"} else "unavailable",
        direction=direction,
        horizon_sessions=horizon or 20,
        event_source=event_source,
        p_outperform=_float(row.get("p_outperform")),
        expected_excess_net=_float(row.get("expected_excess_net")),
        interval={"lower": float(row["interval_lower"]), "upper": float(row["interval_upper"])} if row.get("interval_lower") is not None and row.get("interval_upper") is not None else None,
        issued_at=issued,
        expires_at=expires,
        model_version=row.get("model_version"),
        abstain_reason=row.get("abstain_reason") or reason or decision.abstain_reason,
    )

def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dt(value: Any):
    from datetime import datetime, timezone
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
    except (TypeError, ValueError):
        return None


