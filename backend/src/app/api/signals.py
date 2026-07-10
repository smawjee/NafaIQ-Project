"""Signal routes: thin HTTP layer over services.signals."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.market import signals as signals_service

router = APIRouter(tags=["signals"])


@router.get("/signal/{symbol}")
async def get_signal(symbol: str):
    return await signals_service.get_signal(symbol)


@router.post("/signals/batch")
async def batch_signals(body: dict | None = None):
    limit = (body or {}).get("limit", 50)
    return await signals_service.batch_signals(limit)
