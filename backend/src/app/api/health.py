from datetime import datetime, timezone
from functools import lru_cache

from fastapi import APIRouter
from sqlalchemy import text

from app.scrapers.dps import DPSScraper
from app.services.cache import CacheLayer
from app.db.sqlalchemy import ensure_reflected, get_session_factory

router = APIRouter(tags=["health"])


@lru_cache
def _get_cache() -> CacheLayer:
    return CacheLayer(DPSScraper())


_last_market_refresh: datetime | None = None


def set_market_refresh_time():
    global _last_market_refresh
    _last_market_refresh = datetime.now(timezone.utc)


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "last_market_refresh": _last_market_refresh.isoformat() if _last_market_refresh else None,
    }


@router.get("/health/db")
async def health_db():
    import time
    await ensure_reflected()
    factory = get_session_factory()
    start = time.perf_counter()
    async with factory() as session:
        await session.execute(text("SELECT 1"))
    latency = (time.perf_counter() - start) * 1000
    return {"status": "ok", "latency_ms": round(latency, 2)}
