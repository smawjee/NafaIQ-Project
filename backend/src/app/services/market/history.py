"""OHLCV history reads + history-coverage report."""
from __future__ import annotations

from typing import Any

from app.repositories import market_repo as repo
from app.repositories.base import connect
from app.services.market._base import TTL_HISTORY, get_cache
from app.services.memcache import mem_cache


async def history(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    sym = symbol.upper()

    async def load() -> list[dict[str, Any]]:
        bars = await get_cache().get_history(sym, days)
        return [b.model_dump(mode="json") for b in bars]

    return await mem_cache.get_or_load(f"history:{sym}:{days}", TTL_HISTORY, load)


async def history_coverage() -> list[dict[str, Any]]:
    """Days of historical OHLCV data per symbol. Verifies the 20-day guarantee."""
    async with connect() as conn:
        return await repo.history_coverage(conn)
