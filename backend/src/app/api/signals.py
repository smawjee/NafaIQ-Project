"""Signal routes: thin HTTP layer over services.signals."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.middleware.rate_limit import limiter
from app.services.market import signals as signals_service

router = APIRouter(tags=["signals"])

# These routes are anonymous (auth.py lists /api/signal and /api/signals as
# public prefixes) and each can run ML inference, so they need an explicit
# limit: `default_limits` on the shared Limiter is inert because main.py
# deliberately does not install SlowAPIMiddleware.


class BatchSignalsRequest(BaseModel):
    # Was an unbounded `(body or {}).get("limit", 50)`, so a single anonymous
    # request could ask for arbitrarily many predictions.
    limit: int = Field(default=50, ge=1, le=100)


@router.get("/signal/{symbol}")
@limiter.limit("30/minute")
async def get_signal(request: Request, symbol: str):
    return await signals_service.get_signal(symbol)


@router.post("/signals/batch")
@limiter.limit("10/minute")
async def batch_signals(request: Request, body: BatchSignalsRequest | None = None):
    return await signals_service.batch_signals((body or BatchSignalsRequest()).limit)
