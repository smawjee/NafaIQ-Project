"""Signal data access over Supabase REST (psx_signals cache + snapshot reads).

This domain persists to Supabase (not the SQLAlchemy pooler), so the repo wraps
the Supabase client here and keeps the service free of data-access calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.db.supabase import async_execute


async def get_cached_signal(symbol: str) -> Optional[dict[str, Any]]:
    row = await async_execute(lambda c: c.table("psx_signals").select("*").eq("symbol", symbol))
    if row.data:
        return row.data[0]
    return None


async def upsert_signal(symbol: str, result: dict[str, Any]) -> None:
    await async_execute(lambda c: c.table("psx_signals").upsert(
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
    ))


async def top_symbols_by_volume(limit: int) -> list[str]:
    snapshot = await async_execute(
        lambda c: (
            c.table("psx_market_snapshot")
            .select("symbol")
            .order("volume", desc=True)
            .limit(limit)
        )
    )
    return [r["symbol"] for r in (snapshot.data or [])]


async def get_cached_signal_v2(symbol: str, horizon: str) -> Optional[dict[str, Any]]:
    row = await async_execute(
        lambda c: c.table("psx_signals_v2")
        .select("*")
        .eq("symbol", symbol.upper())
        .eq("horizon", horizon.upper())
        .limit(1)
    )
    if row.data:
        return row.data[0]
    return None


async def upsert_signal_v2(result: dict[str, Any]) -> None:
    await async_execute(
        lambda c: c.table("psx_signals_v2").upsert(
            {
                "symbol": result["symbol"],
                "horizon": result["horizon"],
                "signal": result["signal"],
                "confidence": result["confidence"],
                "rank_score": result["rank_score"],
                "technical_signal": result["technical_signal"],
                "technical_score": result["technical_score"],
                "ml_signal": result.get("ml_signal"),
                "ml_confidence": result.get("ml_confidence"),
                "risk_level": result["risk_level"],
                "regime": result["regime"],
                "freshness": result["freshness"],
                "reasons": result.get("reasons", []),
                "warnings": result.get("warnings", []),
                "indicator_votes": result.get("indicator_votes", []),
                "probabilities": result.get("probabilities"),
                "features_snapshot": result.get("features_snapshot", {}),
                "model_version": result["model_version"],
                "engine_version": result["engine_version"],
                "predicted_at": result["predicted_at"],
            },
            on_conflict="symbol,horizon",
        )
    )


async def leaderboard_v2(horizon: str, limit: int) -> list[dict[str, Any]]:
    rows = await async_execute(
        lambda c: c.table("psx_signals_v2")
        .select("*")
        .eq("horizon", horizon.upper())
        .order("rank_score", desc=True)
        .limit(limit)
    )
    return rows.data or []
