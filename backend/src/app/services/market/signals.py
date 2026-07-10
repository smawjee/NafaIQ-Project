"""Signal service: ML prediction with a 4h Supabase-backed cache.

Business logic only — Supabase access is delegated to
app.repositories.signals_repo.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.repositories import signals_repo as repo
from app.services.signal_engine import get_signal_engine

_SIGNAL_TTL_SECONDS = 14400  # 4 hours


async def get_signal(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()

    # Serve from cache when the stored prediction is still fresh.
    try:
        cached = await repo.get_cached_signal(sym)
        if cached:
            predicted_at = datetime.fromisoformat(
                cached["predicted_at"].replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - predicted_at).total_seconds()
            if age < _SIGNAL_TTL_SECONDS:
                return {
                    "symbol": cached["symbol"],
                    "signal": cached["signal"],
                    "confidence": cached["confidence"],
                    "probabilities": cached.get("probabilities"),
                    "features_used": cached.get("features_used", []),
                    "model_version": cached.get("model_version"),
                }
    except Exception:
        pass

    engine = get_signal_engine()
    result = await asyncio.to_thread(engine.predict, sym)

    try:
        await repo.upsert_signal(sym, result)
    except Exception:
        pass

    return result


async def batch_signals(limit: int = 50) -> dict[str, Any]:
    engine = get_signal_engine()
    symbols = await repo.top_symbols_by_volume(limit)
    results = []
    for sym in symbols:
        try:
            results.append(await asyncio.to_thread(engine.predict, sym))
        except Exception:
            pass
    return {"signals": results, "count": len(results)}
