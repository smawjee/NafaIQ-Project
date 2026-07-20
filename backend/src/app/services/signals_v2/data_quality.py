from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.signals_v2.constants import (
    MIN_FULL_HISTORY,
    MIN_PARTIAL_HISTORY,
    STALE_SNAPSHOT_SECONDS,
    VERY_STALE_SNAPSHOT_SECONDS,
)
from app.services.signals_v2.schemas import DataQuality


def assess_data_quality(
    *,
    ohlcv_rows: list[dict[str, Any]],
    snapshot: dict[str, Any] | None,
    liquidity_score: float,
) -> DataQuality:
    warnings: list[str] = []
    history_days = len(ohlcv_rows)
    latest_date = None
    if ohlcv_rows:
        latest = max(ohlcv_rows, key=lambda r: str(r.get("date")))
        try:
            latest_date = datetime.fromisoformat(str(latest.get("date"))[:10]).date()
        except (TypeError, ValueError):
            warnings.append("Latest OHLCV date is invalid")

    if history_days < MIN_PARTIAL_HISTORY:
        return DataQuality(
            eligible=False,
            status="NO_SIGNAL",
            history_days=history_days,
            latest_ohlcv_date=latest_date,
            warnings=[*warnings, "Insufficient OHLCV history for a reliable signal"],
            liquidity_score=liquidity_score,
            freshness="UNKNOWN",
        )

    last = ohlcv_rows[-1] if ohlcv_rows else {}
    for key in ("open", "high", "low", "close"):
        try:
            if float(last.get(key) or 0) <= 0:
                return DataQuality(
                    eligible=False,
                    status="NO_SIGNAL",
                    history_days=history_days,
                    latest_ohlcv_date=latest_date,
                    warnings=[*warnings, f"Invalid latest {key} value"],
                    liquidity_score=liquidity_score,
                    freshness="UNKNOWN",
                )
        except (TypeError, ValueError):
            return DataQuality(
                eligible=False,
                status="NO_SIGNAL",
                history_days=history_days,
                latest_ohlcv_date=latest_date,
                warnings=[*warnings, f"Invalid latest {key} value"],
                liquidity_score=liquidity_score,
                freshness="UNKNOWN",
            )

    age = _snapshot_age(snapshot)
    freshness = "UNKNOWN"
    if age is not None:
        if age <= STALE_SNAPSHOT_SECONDS:
            freshness = "LIVE"
        elif age <= VERY_STALE_SNAPSHOT_SECONDS:
            freshness = "DELAYED"
            warnings.append("Live snapshot is delayed")
        else:
            freshness = "STALE"
            warnings.append("Live snapshot is stale")
    else:
        warnings.append("Live snapshot timestamp is unavailable")

    status = "OK" if history_days >= MIN_FULL_HISTORY else "PARTIAL"
    if status == "PARTIAL":
        warnings.append("Partial history: ML confidence is capped")

    return DataQuality(
        eligible=True,
        status=status,
        history_days=history_days,
        latest_ohlcv_date=latest_date,
        snapshot_age_seconds=age,
        warnings=warnings,
        liquidity_score=liquidity_score,
        freshness=freshness,
    )


def _snapshot_age(snapshot: dict[str, Any] | None) -> float | None:
    if not snapshot:
        return None
    value = snapshot.get("refreshed_at")
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except (TypeError, ValueError):
        return None
