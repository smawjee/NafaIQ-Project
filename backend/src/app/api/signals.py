"""Signals API — the single engine.

The contract exposes a deterministic technical setup and a separately gated
event outlook. It never falls back to a fabricated HOLD signal.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.middleware.rate_limit import limiter
from app.services.signals import service

router = APIRouter(tags=["signals"])

# These routes are anonymous (auth.py lists /api/signal and /api/signals as
# public prefixes) and each can run inference, so they need an explicit limit:
# `default_limits` on the shared Limiter is inert because main.py deliberately
# does not install SlowAPIMiddleware.


class BatchSignalsRequest(BaseModel):
    # Was an unbounded `(body or {}).get("limit", 50)`, so a single anonymous
    # request could ask for arbitrarily many predictions.
    limit: int = Field(default=50, ge=1, le=100)


# --- Canonical routes -------------------------------------------------------
# Declaration order matters: FastAPI matches in order, so the literal paths must
# come before `/signals/{symbol}` or "batch" is captured as a symbol.


@router.get("/signals/track-record")
async def signal_track_record():
    """Out-of-sample reliability of the calibrated probabilities.

    Not a strategy P&L and not a forecast record. This answers the one question
    that makes a stated probability meaningful: when the engine said 58%, how
    often did it actually happen — on a period the calibration never saw?

    The numbers come from the calibration artifact, which is built on 2016-2024
    and scored against an untouched 2025-2026 holdout. An artifact is only
    written when that holdout error clears the pre-registered bound, so a
    response here is itself evidence the calibration passed.
    """
    # Installed mobile builds read `by_signal`/`matured_total` unguarded
    # (SignalTrackRecordCard does `SIGNAL_ORDER.filter(s => data.by_signal[s])`,
    # which throws on undefined) and cannot be force-updated. These three keys
    # are therefore part of the contract until those builds age out — same
    # reasoning as the deprecated URL aliases below.
    legacy = {"matured_total": 0, "by_signal": {}, "pending_maturity": 0}

    table = service.get_base_rate_table()
    if table is None:
        return {
            **legacy,
            "status": "unavailable",
            "reason_code": "NO_CALIBRATION_ARTIFACT",
            "note": "Base-rate calibration has not been generated.",
        }

    validation = table.holdout_validation or {}
    reliability = validation.get("reliability") or []

    # Live record: predictions actually served, then measured. Best-effort —
    # the historical holdout stands on its own, and an empty live record simply
    # means not enough predictions have reached their horizon yet.
    live: dict[str, Any] = {"reliability": [], "n": 0, "ece": None}
    try:
        from app.repositories import signals_repo
        from app.services.signals.outcomes import reliability_from_rollup

        live = reliability_from_rollup(await signals_repo.calibration_rows())
    except Exception:
        pass

    return {
        **legacy,
        "status": "available" if reliability else "unavailable",
        "kind": "probability_calibration",
        "horizon_sessions": table.horizon,
        "base_rate": table.global_rate,
        "total_samples": table.total_samples,
        # Predictions served and since measured. Accumulates from launch, so it
        # is empty at first and is the only figure that can catch the
        # relationship decaying after calibration.
        "live": {
            "observations": live.get("n", 0),
            "calibration_error": live.get("ece"),
            "buckets": live.get("reliability", []),
        },
        "holdout": {
            "period_start": table.explore_end,
            "observations": validation.get("n", 0),
            # Expected calibration error: average gap between stated and
            # realised frequency, weighted by how often each bucket occurred.
            "calibration_error": validation.get("ece"),
            "passes_bound": validation.get("passes"),
            "buckets": reliability,
        },
        "note": (
            "Reliability of the stated probabilities on data the calibration "
            "never saw. Not a trading track record."
        ),
    }


@router.post("/signals/batch")
@limiter.limit("10/minute")
async def batch_signals(request: Request, body: BatchSignalsRequest | None = None):
    return await service.batch_signals((body or BatchSignalsRequest()).limit)


@router.get("/signals/{symbol}")
@limiter.limit("30/minute")
async def get_signal(request: Request, symbol: str):
    return await service.get_signal(symbol)


# --- Deprecated aliases -----------------------------------------------------
# Installed mobile builds still call these paths and cannot be force-updated the
# way the web app can. They forward to the canonical handlers above and add no
# behaviour of their own. Remove once the old builds are out of circulation.


@router.get("/signal/{symbol}", include_in_schema=False)
@limiter.limit("30/minute")
async def get_signal_legacy(request: Request, symbol: str):
    return await service.get_signal(symbol)


@router.get("/signals/v3/{symbol}", include_in_schema=False)
@limiter.limit("30/minute")
async def get_signal_v3_alias(request: Request, symbol: str):
    return await service.get_signal(symbol)


@router.post("/signals/v3/batch", include_in_schema=False)
@limiter.limit("10/minute")
async def batch_signals_v3_alias(request: Request, body: BatchSignalsRequest | None = None):
    return await service.batch_signals((body or BatchSignalsRequest()).limit)


@router.get("/signals/v2/track-record", include_in_schema=False)
async def signal_track_record_legacy():
    return await signal_track_record()
