"""Shared market-service infra: the DPS cache accessor, in-process TTLs, and
the snapshot helper used by quote reads."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.scrapers.dps import DPSScraper
from app.services.cache import CacheLayer
from app.services.memcache import mem_cache

DEFAULT_INDICATORS = ["rsi14", "sma20", "sma50", "sma200", "macd", "bollinger", "atr14"]

# In-process TTLs for hot reads (seconds). Supabase stays the persistent
# store; these just stop every request from paying a cloud round-trip.
TTL_SNAPSHOT = 5.0
TTL_SYMBOLS = 900.0
TTL_INDEX = 60.0
TTL_SECTORS = 15.0
TTL_HISTORY = 3600.0  # EOD candles — refreshed by the nightly backfill job
TTL_PROFILE = 1800.0
TTL_FUNDAMENTALS = 1800.0
TTL_SECTOR_AVG = 30.0
TTL_SCREENER_METRICS = 120.0

INDEX_CARD_CODES = ["KSE100", "KSE30", "KMI30", "ALLSHR"]


@lru_cache(maxsize=1)
def get_cache() -> CacheLayer:
    return CacheLayer(DPSScraper())


async def snapshot_rows() -> list[dict[str, Any]]:
    async def load() -> list[dict[str, Any]]:
        items = await get_cache().get_market_snapshot()
        return [i.model_dump(mode="json") for i in items]

    return await mem_cache.get_or_load("market_snapshot", TTL_SNAPSHOT, load)
