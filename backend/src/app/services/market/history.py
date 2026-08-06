"""OHLCV history reads + history-coverage report."""
from __future__ import annotations

from typing import Any

from app.repositories import market as repo
from app.repositories.base import connect
from app.services.market._base import TTL_HISTORY, get_cache
from app.services.memcache import mem_cache


# Cache windows. `days` is caller-controlled (1..3650), so keying the cache on
# it directly gave a key space of ~1076 symbols x 3650 values: the cache
# thrashed, and walking `?days=N` was a cheap way to amplify process memory.
# Requests are served from the smallest window that covers them and sliced, so
# a symbol occupies at most len(_WINDOWS) entries. These match the ranges the
# charts actually request (1M / 3M / 1Y / 2Y / 5Y / 10Y).
_WINDOWS = (30, 90, 250, 500, 1250, 2500, 3650)


def _window_for(days: int) -> int:
    """Smallest cache window that fully covers `days`."""
    for window in _WINDOWS:
        if days <= window:
            return window
    return _WINDOWS[-1]


async def history(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    sym = symbol.upper()
    window = _window_for(days)

    async def load() -> list[dict[str, Any]]:
        bars = await get_cache().get_history(sym, window)
        rows = [b.model_dump(mode="json") for b in bars]
        # CacheLayer has two paths with opposite ordering: the DB read is
        # `date` DESC, the scrape fallback returns `bars[-days:]` (oldest
        # first). Normalise so the slice below is always the most recent bars.
        # Dates are ISO strings, so a plain reverse sort is chronological.
        rows.sort(key=lambda r: r["date"], reverse=True)
        return rows

    rows = await mem_cache.get_or_load(f"history:{sym}:{window}", TTL_HISTORY, load)
    # Newest-first, so the first `days` are the most recent — the same payload
    # an exact-`days` fetch returned. Slicing also hands callers their own list
    # rather than the cached one.
    return rows[:days]


async def history_coverage() -> list[dict[str, Any]]:
    """Days of historical OHLCV data per symbol. Verifies the 20-day guarantee."""
    async with connect() as conn:
        return await repo.history_coverage(conn)
