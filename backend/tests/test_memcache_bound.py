"""The shared in-process market cache must stay bounded in BYTES, not entries.

``MAX_ENTRIES`` alone capped the entry count while each ``history:{sym}:{days}``
entry could hold up to 3650 bar-dicts (``days`` is caller-controlled). A
saturated cache measured 249 MB at the default days=250 and 2.7 GB at days=3650,
against a 1024 MB Railway container — the box OOM-killed itself daily.

``_locks`` was worse: it had no cap at all, so every distinct key ever requested
left a permanent ``asyncio.Lock`` behind.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import memcache as mc


def _bars(n: int, sym: str = "HBL") -> list[dict]:
    """Same shape history() caches: OHLCVBar.model_dump(mode="json")."""
    return [
        {
            "symbol": sym,
            "date": f"2020-01-{(i % 28) + 1:02d}",
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1_234_567 + i,
        }
        for i in range(n)
    ]


async def _ret(v):
    return v


def test_cache_respects_a_byte_budget():
    """Many large payloads must not push the cache past its byte budget."""
    cache = mc.TTLCache(max_bytes=4 * 1024 * 1024)  # 4 MB

    async def fill():
        for i in range(400):
            await cache.get_or_load(
                f"history:SYM{i}:3650", 1e9, lambda i=i: _ret(_bars(3650, f"SYM{i}"))
            )

    asyncio.run(fill())

    assert cache.nbytes <= 4 * 1024 * 1024, (
        f"cache held {cache.nbytes / 1024 / 1024:.1f} MB, budget was 4 MB"
    )
    assert cache._data, "budget must not evict everything — the cache still has to work"


def test_locks_do_not_grow_without_bound():
    """Every distinct key used to leave a permanent asyncio.Lock behind."""
    cache = mc.TTLCache(max_entries=64, max_bytes=8 * 1024 * 1024)

    async def fill():
        for i in range(5_000):
            await cache.get_or_load(f"history:S:{i}", 1e9, lambda i=i: _ret([{"a": i}]))

    asyncio.run(fill())

    assert len(cache._locks) <= 64 * 4, (
        f"_locks held {len(cache._locks)} entries for 5000 distinct keys"
    )


def test_a_single_oversized_payload_is_not_cached():
    """One payload bigger than the whole budget must not be stored."""
    cache = mc.TTLCache(max_bytes=64 * 1024)  # 64 KB

    async def go():
        return await cache.get_or_load("history:BIG:3650", 1e9, lambda: _ret(_bars(3650)))

    result = asyncio.run(go())

    assert len(result) == 3650, "caller must still get its data back"
    assert cache.nbytes <= 64 * 1024
    assert "history:BIG:3650" not in cache._data


# ---------- behaviour that must NOT change ----------


def test_fresh_hit_returns_cached_value_without_reloading():
    cache = mc.TTLCache()
    calls = []

    async def loader():
        calls.append(1)
        return [{"v": 1}]

    async def go():
        a = await cache.get_or_load("k", 1e9, loader)
        b = await cache.get_or_load("k", 1e9, loader)
        return a, b

    a, b = asyncio.run(go())
    assert a == b == [{"v": 1}]
    assert len(calls) == 1, "a fresh hit must not re-run the loader"


def test_empty_payloads_are_never_cached():
    cache = mc.TTLCache()

    async def go():
        await cache.get_or_load("empty_list", 1e9, lambda: _ret([]))
        await cache.get_or_load("empty_dict", 1e9, lambda: _ret({}))
        await cache.get_or_load("none", 1e9, lambda: _ret(None))

    asyncio.run(go())
    assert cache._data == {}


def test_expired_entry_serves_stale_then_refreshes_in_background():
    cache = mc.TTLCache()
    calls = []

    async def loader():
        calls.append(1)
        return [{"n": len(calls)}]

    async def go():
        first = await cache.get_or_load("k", 0.0, loader)  # cold miss -> loads
        stale = await cache.get_or_load("k", 0.0, loader)  # expired -> serve stale
        await asyncio.sleep(0.05)                          # let refresh land
        return first, stale, cache._data["k"][1]

    first, stale, after = asyncio.run(go())
    assert first == [{"n": 1}]
    assert stale == [{"n": 1}], "expired reads must serve the stale value instantly"
    assert after == [{"n": 2}], "a background refresh must replace it"
