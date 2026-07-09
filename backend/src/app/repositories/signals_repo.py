"""Signal data access over Supabase REST (psx_signals cache + snapshot reads).

This domain persists to Supabase (not the SQLAlchemy pooler), so the repo wraps
the Supabase client here and keeps the service free of data-access calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.db.supabase import get_supabase


async def get_cached_signal(symbol: str) -> Optional[dict[str, Any]]:
    db = get_supabase()
    row = db.table("psx_signals").select("*").eq("symbol", symbol).execute()
    if row.data:
        return row.data[0]
    return None


async def upsert_signal(symbol: str, result: dict[str, Any]) -> None:
    db = get_supabase()
    db.table("psx_signals").upsert(
        {
            "symbol": symbol,
            "signal": result["signal"],
            "confidence": result["confidence"],
            "probabilities": result.get("probabilities"),
            "features_used": result.get("features_used", []),
            "model_version": result.get("model_version"),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="symbol",
    ).execute()


async def top_symbols_by_volume(limit: int) -> list[str]:
    db = get_supabase()
    snapshot = (
        db.table("psx_market_snapshot")
        .select("symbol")
        .order("volume", desc=True)
        .limit(limit)
        .execute()
    )
    return [r["symbol"] for r in (snapshot.data or [])]
