from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.db.supabase import get_supabase
from app.services.signal_engine import get_signal_engine
from app.services.cache import CacheLayer
from app.scrapers.dps import DPSScraper

router = APIRouter(tags=["signals"])

engine = get_signal_engine()


@router.get("/signal/{symbol}")
async def get_signal(symbol: str):
    sym = symbol.upper()
    db = get_supabase()

    # Check cache first (4h TTL)
    try:
        row = db.table("psx_signals").select("*").eq("symbol", sym).execute()
        if row.data:
            r = row.data[0]
            predicted_at = datetime.fromisoformat(r["predicted_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - predicted_at).total_seconds()
            if age < 14400:  # 4 hours
                return {
                    "symbol": r["symbol"],
                    "signal": r["signal"],
                    "confidence": r["confidence"],
                    "probabilities": r.get("probabilities"),
                    "features_used": r.get("features_used", []),
                    "model_version": r.get("model_version"),
                }
    except Exception:
        pass

    # Generate fresh signal
    result = engine.predict(sym)

    # Cache it
    try:
        db.table("psx_signals").upsert({
            "symbol": sym,
            "signal": result["signal"],
            "confidence": result["confidence"],
            "probabilities": result.get("probabilities"),
            "features_used": result.get("features_used", []),
            "model_version": result.get("model_version"),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="symbol").execute()
    except Exception:
        pass

    return result


@router.post("/signals/batch")
async def batch_signals(body: dict | None = None):
    limit = (body or {}).get("limit", 50)
    db = get_supabase()

    # Get top symbols by volume
    snapshot = db.table("psx_market_snapshot").select("symbol").order("volume", desc=True).limit(limit).execute()
    symbols = [r["symbol"] for r in (snapshot.data or [])]

    results = []
    for sym in symbols:
        try:
            result = engine.predict(sym)
            results.append(result)
        except Exception:
            pass

    return {"signals": results, "count": len(results)}
