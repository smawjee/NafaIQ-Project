"""Canonical Signals V4 API.

The contract exposes a deterministic technical setup and a separately gated
event outlook. It never falls back to a fabricated HOLD signal.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.middleware.rate_limit import limiter
from app.services.signals_v4 import service

router = APIRouter(tags=["signals-v4"])


class BatchSignalsV4Request(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)


@router.get("/signals/v3/{symbol}")
@limiter.limit("30/minute")
async def get_signal_v4(request: Request, symbol: str):
    return await service.get_signal(symbol)


@router.post("/signals/v3/batch")
@limiter.limit("10/minute")
async def batch_signals_v4(request: Request, body: BatchSignalsV4Request | None = None):
    return await service.batch_signals((body or BatchSignalsV4Request()).limit)

