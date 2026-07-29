"""get_history must page past PostgREST's ~1000-row response cap.

psx_ohlcv holds ~10 years of bars (verified 2026-07-15: 973,599 rows, 836
symbols, back to 2016-07-11). PostgREST caps any single response at ~1000 rows
regardless of .limit(), so a bare `.limit(days)` silently returned only the
first page for any request deeper than ~4 years — with no error. These tests
pin the paging so that truncation cannot come back unnoticed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import cache as cache_mod


class _FakeTable:
    """Minimal PostgREST builder stub that enforces the ~1000-row page cap."""

    def __init__(self, total_rows: int, page_cap: int = 1000):
        self._total = total_rows
        self._cap = page_cap
        self._start = 0
        self._stop = None

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._start, self._stop = 0, n - 1
        return self

    def range(self, start, end):
        self._start, self._stop = start, end
        return self

    def _rows(self):
        requested = (self._stop - self._start) + 1
        # This is the real-world behaviour being guarded: the server never
        # returns more than the cap in one response, however much you ask for.
        served = min(requested, self._cap)
        avail = max(0, self._total - self._start)
        n = min(served, avail)
        return [
            {
                "symbol": "TEST",
                "date": f"2020-01-{(i % 28) + 1:02d}",
                "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100,
            }
            for i in range(n)
        ]


class _ExplodingDPS:
    """The DB read must satisfy these tests — the scrape fallback is a failure."""

    async def fetch_historical(self, symbol):  # pragma: no cover
        raise AssertionError("fell through to the scraper; the DB read should have served this")


def _layer():
    return cache_mod.CacheLayer(_ExplodingDPS())


def _install_fake(monkeypatch, total_rows: int):
    calls = {"n": 0}
    table = _FakeTable(total_rows)

    async def _fake_async_execute(builder):
        calls["n"] += 1
        client = SimpleNamespace(table=lambda _name: table)
        built = builder(client)
        return SimpleNamespace(data=built._rows(), count=total_rows)

    monkeypatch.setattr(cache_mod, "async_execute", _fake_async_execute)
    return calls


@pytest.mark.asyncio
async def test_deep_history_pages_past_the_1000_row_cap(monkeypatch):
    """A 10-year request must return all ~2500 bars, not just the first 1000."""
    calls = _install_fake(monkeypatch, total_rows=2500)

    bars = await _layer().get_history("TEST", days=3650)

    assert len(bars) == 2500, f"expected full series, got {len(bars)} (truncated at cap?)"
    assert calls["n"] >= 3, "should have issued multiple pages"


@pytest.mark.asyncio
async def test_shallow_history_is_a_single_request(monkeypatch):
    """The common case (<= one page) must not regress into extra round-trips."""
    calls = _install_fake(monkeypatch, total_rows=5000)

    bars = await _layer().get_history("TEST", days=250)

    assert len(bars) == 250
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_paging_stops_when_symbol_history_is_exhausted(monkeypatch):
    """A short-listed symbol must not page forever chasing rows that don't exist."""
    calls = _install_fake(monkeypatch, total_rows=1200)

    bars = await _layer().get_history("TEST", days=3650)

    assert len(bars) == 1200
    # 1000 (full page) + 200 (short page -> stop). Must not keep walking to 3650.
    assert calls["n"] == 2
