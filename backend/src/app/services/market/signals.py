"""Signal service: ML prediction with a 4h Supabase-backed cache.

Business logic only — Supabase access is delegated to
app.repositories.signals_repo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories import signals_repo as repo
from app.services.signals_v2 import engine as signals_v2
from app.services.signals_v2.schemas import SignalV2Response, to_v1

_SIGNAL_TTL_SECONDS = 14400  # 4 hours


async def get_signal(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    try:
        v2 = await signals_v2.get_signal(sym)
        return to_v1(SignalV2Response(**v2)).model_dump(mode="json")
    except Exception:
        pass

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

    result = {
        "symbol": sym,
        "signal": "HOLD",
        "confidence": 0,
        "probabilities": {},
        "features_used": [],
        "model_version": "unavailable",
    }
    return result


async def batch_signals(limit: int = 50) -> dict[str, Any]:
    symbols = await repo.top_symbols_by_volume(limit)
    results = []
    for sym in symbols:
        try:
            # Via get_signal, not engine.predict: this went straight to the
            # model and bypassed the 4h cache above, so every batch call paid
            # full inference for symbols already predicted minutes earlier.
            results.append(await get_signal(sym))
        except Exception:
            pass
    return {"signals": results, "count": len(results)}
