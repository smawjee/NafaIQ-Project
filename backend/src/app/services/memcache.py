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

Sizing — why there is a BYTE budget and not just an entry cap
-------------------------------------------------------------
``MAX_ENTRIES`` bounds how many entries live here, but entries are not the
same size: a ``history:{sym}:{days}`` payload holds ``days`` bar-dicts and
``days`` is caller-controlled (1..3650). A cache full of 2048 such entries
measured 249 MB at the default days=250 and 2.7 GB at days=3650 — against a
1024 MB Railway container. The box OOM-killed itself daily.

So the real guarantee is ``MAX_BYTES``: no matter what shape callers ask for,
the cache never holds more than that. The entry cap is kept as a cheap
secondary bound on key churn.
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any, Awaitable, Callable

import structlog

log = structlog.get_logger()

# Safety cap so per-symbol keys (history, fundamentals) can't grow unbounded.
MAX_ENTRIES = 2048

# Hard ceiling on everything this cache holds. The container is 1024 MB and the
# app idles around 240 MB, so 192 MB leaves generous headroom for request
# handling. This is the bound that actually prevents the OOM.
MAX_BYTES = 192 * 1024 * 1024

# A key whose entry is gone still leaves its single-flight Lock behind. Locks
# are small but the key space is ~1076 symbols x 3650 day-values, so they were
# the second unbounded leak. Prune once we hold noticeably more than we need.
_LOCK_SLACK = 4

# Sampling threshold for _approx_size: past this many elements a homogeneous
# list (which is what every payload here is) is measured by sampling.
_SAMPLE_AFTER = 32
_SAMPLE_SIZE = 8


def _approx_size(obj: Any, _depth: int = 0) -> int:
    """Approximate retained bytes of a JSON-ish payload.

    Deliberately cheap: payloads here are homogeneous lists of flat dicts, so
    past ``_SAMPLE_AFTER`` elements this samples a few and extrapolates rather
    than walking millions of objects on every store. Shared/interned strings
    get counted per-reference, which over-estimates — erring toward evicting
    early is the safe direction for a memory bound.
    """
    size = sys.getsizeof(obj)
    if _depth > 3:
        return size
    if isinstance(obj, dict):
        for key, value in obj.items():
            size += _approx_size(key, _depth + 1) + _approx_size(value, _depth + 1)
    elif isinstance(obj, (list, tuple, set)):
        count = len(obj)
        if count == 0:
            return size
        items = list(obj)
        if count > _SAMPLE_AFTER:
            sampled = sum(_approx_size(o, _depth + 1) for o in items[:_SAMPLE_SIZE])
            size += int(sampled / _SAMPLE_SIZE * count)
        else:
            size += sum(_approx_size(o, _depth + 1) for o in items)
    return size


class TTLCache:
    def __init__(
        self,
        max_entries: int = MAX_ENTRIES,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        # key -> (stored_at, value, approx_bytes)
        self._data: dict[str, tuple[float, Any, int]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._refreshing: set[str] = set()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._nbytes = 0

    @property
    def nbytes(self) -> int:
        """Approximate bytes currently held. Never exceeds ``max_bytes``."""
        return self._nbytes

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

        size = _approx_size(value)
        if size > self._max_bytes:
            # One payload larger than the entire budget. Caching it would evict
            # everything else and still not fit. Serve it, don't keep it.
            log.warning("memcache_payload_over_budget", key=key, bytes=size)
            self._drop(key)
            return

        self._drop(key)  # replacing: retire the old size first
        self._data[key] = (time.monotonic(), value, size)
        self._nbytes += size
        self._evict()

    def _drop(self, key: str) -> None:
        existing = self._data.pop(key, None)
        if existing is not None:
            self._nbytes -= existing[2]

    def _evict(self) -> None:
        """Evict oldest-first until back inside both the byte and entry caps."""
        while self._data and (
            self._nbytes > self._max_bytes or len(self._data) > self._max_entries
        ):
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._drop(oldest)
        self._prune_locks()

    def _prune_locks(self) -> None:
        """Release single-flight locks for keys no longer cached.

        A held lock is never pruned, so an in-flight cold load keeps its
        single-flight guarantee. Locks are only created inside ``get_or_load``
        with no await between ``setdefault`` and acquiring, so there is no
        window where a caller can lose the lock it just took.
        """
        if len(self._locks) <= self._max_entries * _LOCK_SLACK:
            return
        for key, lock in list(self._locks.items()):
            if key not in self._data and not lock.locked():
                del self._locks[key]

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
