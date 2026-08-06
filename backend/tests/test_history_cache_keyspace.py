"""``history()`` must not mint a cache entry per distinct ``days`` value.

``/quote/{symbol}/history`` accepts ``days`` anywhere in 1..3650, and the cache
key was ``history:{sym}:{days}`` — a key space of ~1076 symbols x 3650 values.
That both thrashed the cache and let a caller amplify memory just by walking
``?days=N``. Requests are now served from a bucketed window and sliced, so the
per-symbol key space is the handful of windows below.

The returned payload must be byte-identical to what an exact-``days`` fetch
returned before: the ``days`` most recent bars, newest first.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest

import importlib

from app.schemas.market import OHLCVBar
from app.services.memcache import mem_cache

# `app.services.market.__init__` re-exports the `history` FUNCTION under the
# same name as this submodule, so a plain import binds the function. Reach for
# the module itself — monkeypatching needs the module namespace.
history_mod = importlib.import_module("app.services.market.history")


@pytest.fixture(autouse=True)
def _clear_cache():
    mem_cache._data.clear()
    mem_cache._locks.clear()
    mem_cache._nbytes = 0
    yield
    mem_cache._data.clear()
    mem_cache._locks.clear()
    mem_cache._nbytes = 0


def _fake_cache(calls: list[int]):
    """Stands in for CacheLayer: returns `days` bars, newest first."""
    base = date(2024, 1, 1)

    class _Fake:
        async def get_history(self, sym: str, days: int):
            calls.append(days)
            return [
                OHLCVBar(
                    symbol=sym,
                    date=base - timedelta(days=i),
                    open=100.0 + i, high=101.0 + i, low=99.0 + i,
                    close=100.5 + i, volume=1000 + i,
                )
                for i in range(days)
            ]

    return lambda: _Fake()


def test_nearby_day_counts_share_one_fetch(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(history_mod, "get_cache", _fake_cache(calls))

    async def go():
        return await history_mod.history("HBL", 100), await history_mod.history("HBL", 200)

    r100, r200 = asyncio.run(go())

    assert len(calls) == 1, f"expected one upstream fetch for both, got {calls}"
    assert len(r100) == 100
    assert len(r200) == 200
    assert r100 == r200[:100], "both must be the same newest-first series"


def test_returns_exactly_the_days_most_recent_bars_newest_first(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(history_mod, "get_cache", _fake_cache(calls))

    rows = asyncio.run(history_mod.history("ENGRO", 37))

    assert len(rows) == 37
    assert rows[0]["date"] == "2024-01-01", "newest bar first"
    assert rows[1]["date"] == "2023-12-31"
    assert rows[0]["symbol"] == "ENGRO"


def test_key_space_per_symbol_stays_small(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(history_mod, "get_cache", _fake_cache(calls))

    async def go():
        for days in range(1, 400):
            await history_mod.history("PSO", days)

    asyncio.run(go())

    keys = [k for k in mem_cache._data if k.startswith("history:PSO:")]
    assert len(keys) <= 8, f"399 distinct ?days= values minted {len(keys)} cache keys: {keys}"


def test_slice_takes_the_most_recent_bars_even_if_upstream_is_oldest_first(monkeypatch):
    """CacheLayer.get_history has two paths with opposite ordering.

    The DB read orders `date` DESC (newest first); the scrape fallback returns
    `bars[-days:]`, which is oldest-first. Slicing a window blindly would hand
    back the OLDEST `days` on that path. history() normalises so the window
    slice is always the most recent bars.
    """
    base = date(2024, 1, 1)

    class _OldestFirst:
        async def get_history(self, sym: str, days: int):
            bars = [
                OHLCVBar(symbol=sym, date=base - timedelta(days=i), close=100.0 + i)
                for i in range(days)
            ]
            return list(reversed(bars))  # oldest first, like the scrape fallback

    monkeypatch.setattr(history_mod, "get_cache", lambda: _OldestFirst())

    rows = asyncio.run(history_mod.history("MARI", 5))

    assert len(rows) == 5
    assert rows[0]["date"] == "2024-01-01", "must be the newest bar, not the oldest"
    assert rows[-1]["date"] == "2023-12-28"


def test_a_short_request_is_not_served_a_truncated_series(monkeypatch):
    """A symbol with less history than the bucket must still return all it has."""
    base = date(2024, 1, 1)

    class _Short:
        async def get_history(self, sym: str, days: int):
            return [
                OHLCVBar(symbol=sym, date=base - timedelta(days=i), close=1.0 + i)
                for i in range(12)  # only 12 bars exist
            ]

    monkeypatch.setattr(history_mod, "get_cache", lambda: _Short())

    rows = asyncio.run(history_mod.history("NEWCO", 250))
    assert len(rows) == 12, "must return everything available, not pad or truncate"
