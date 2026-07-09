"""Tiny in-process TTL cache for hot market reads.

Supabase/Postgres stays the persistent store; this layer just keeps the most
recent result of each hot read in process memory so repeated requests within
the TTL never pay a network round-trip. Semantics:

- Fresh hit: return immediately.
- Expired hit: return the stale value immediately and refresh in the
  background (stale-while-revalidate) — user requests never block on a
  refresh once a key has been populated.
- Cold miss: load once (single-flight lock so concurrent requests don't
  stampede the loader), cache, return.

Empty/None loader results are returned but not cached, so a transient
upstream failure never pins an empty payload for a whole TTL.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import structlog

log = structlog.get_logger()

# Safety cap so per-symbol keys (history, fundamentals) can't grow unbounded.
MAX_ENTRIES = 2048


class TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._refreshing: set[str] = set()

    async def get_or_load(
        self,
        key: str,
        ttl: float,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        hit = self._data.get(key)
        if hit is not None:
            age = time.monotonic() - hit[0]
            if age < ttl:
                return hit[1]
            # Stale: serve instantly, refresh off the request path.
            self._refresh_in_background(key, loader)
            return hit[1]

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self._data.get(key)
            if hit is not None and time.monotonic() - hit[0] < ttl:
                return hit[1]
            value = await loader()
            self._store(key, value)
            return value

    def _store(self, key: str, value: Any) -> None:
        # Don't cache empty payloads — a failed scrape or empty table should
        # be retried on the next request, not served for a whole TTL.
        if value is None or value == [] or value == {}:
            return
        if len(self._data) >= MAX_ENTRIES:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)
        self._data[key] = (time.monotonic(), value)

    def _refresh_in_background(self, key: str, loader: Callable[[], Awaitable[Any]]) -> None:
        if key in self._refreshing:
            return
        self._refreshing.add(key)

        async def _run() -> None:
            try:
                value = await loader()
                self._store(key, value)
            except Exception:
                log.warning("memcache_refresh_failed", key=key, exc_info=True)
            finally:
                self._refreshing.discard(key)

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            # No running loop (sync test context) — drop the refresh silently;
            # the stale value was already served.
            self._refreshing.discard(key)


# Shared process-wide instance for market data.
mem_cache = TTLCache()
