"""Signal routes: thin HTTP layer over services.signals."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.middleware.rate_limit import limiter
from app.services.market import signals as signals_service
from app.services.signals_v2 import engine as signals_v2

router = APIRouter(tags=["signals"])

# These routes are anonymous (auth.py lists /api/signal and /api/signals as
# public prefixes) and each can run ML inference, so they need an explicit
# limit: `default_limits` on the shared Limiter is inert because main.py
# deliberately does not install SlowAPIMiddleware.


class BatchSignalsRequest(BaseModel):
    # Was an unbounded `(body or {}).get("limit", 50)`, so a single anonymous
    # request could ask for arbitrarily many predictions.
    limit: int = Field(default=50, ge=1, le=100)
    horizon: str = Field(default="20D")


@router.get("/signal/{symbol}")
@limiter.limit("30/minute")
async def get_signal(request: Request, symbol: str):
    return await signals_service.get_signal(symbol)


@router.post("/signals/batch")
@limiter.limit("10/minute")
async def batch_signals(request: Request, body: BatchSignalsRequest | None = None):
    return await signals_service.batch_signals((body or BatchSignalsRequest()).limit)


@router.get("/signals/v2/track-record")
async def signal_track_record():
    """Live, measured track record of published signals (matured outcomes only)."""
    from app.repositories import signals_v3_repo
    from app.services.signals_v2.outcomes import aggregate_track_record

    joined = await signals_v3_repo.matured_outcomes_joined()
    pending = await signals_v3_repo.signals_missing_outcomes(limit=1000)
    return {
        **aggregate_track_record(joined),
        "pending_maturity": len(pending),
        "note": "Outcomes are measured against real prices after signals were published; "
                "insert-only history, never edited.",
    }


@router.get("/signals/v2/leaderboard")
@limiter.limit("20/minute")
async def signals_v2_leaderboard(
    request: Request,
    horizon: str = "20D",
    limit: int = 50,
):
    return await signals_v2.leaderboard(horizon=horizon, limit=max(1, min(limit, 100)))


@router.get("/signals/v2/{symbol}")
@limiter.limit("30/minute")
async def get_signal_v2(request: Request, symbol: str, horizon: str = "20D"):
    return await signals_v2.get_signal(symbol, horizon)


@router.get("/signals/v2/{symbol}/breakdown")
@limiter.limit("30/minute")
async def get_signal_v2_breakdown(request: Request, symbol: str, horizon: str = "20D"):
    return await signals_v2.get_signal(symbol, horizon)


@router.post("/signals/v2/batch")
@limiter.limit("10/minute")
async def batch_signals_v2(request: Request, body: BatchSignalsRequest | None = None):
    payload = body or BatchSignalsRequest()
    return await signals_v2.batch_signals(limit=payload.limit, horizon=payload.horizon)
