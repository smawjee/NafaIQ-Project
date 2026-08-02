"""Signals API — the single engine.

The contract exposes a deterministic technical setup and a separately gated
event outlook. It never falls back to a fabricated HOLD signal.
"""
from __future__ import annotations

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
    """Technical setups are not scored as forecasts, so there is no track record."""
    return {
        "status": "unavailable",
        "reason_code": "TECHNICAL_SETUP_NOT_FORECAST",
        "matured_total": 0,
        "by_signal": {},
        "pending_maturity": 0,
        "note": "Only promoted event forecasts receive predictive outcomes.",
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
