"""Reads of psx_profile must page past PostgREST's ~1000-row response cap.

psx_profile is 1,076 rows (verified 2026-07-16), so an unpaginated `.select()`
is truncated *today* — silently, with no error. Two callers were affected:

  * job_refresh_tv_data pre-loads existing sectors so it does not overwrite
    DPS's authoritative classification. Every symbol missing from that map
    resolves to a generic TradingView bucket and is upserted over the real
    sector, so a clipped read clobbers ~76 symbols every 5 minutes.
  * build_treemap joins snapshots to profiles; a clipped read drops those
    symbols into the junk "Other" bucket.

The same read must also never be swallowed: an empty map is indistinguishable
from "no symbol has a sector yet" and clobbers the column market-wide.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db import supabase as db_mod


class _FakeTable:
    """PostgREST builder stub that enforces the ~1000-row page cap."""

    def __init__(self, total_rows: int, page_cap: int = 1000):
        self._total = total_rows
        self._cap = page_cap
        self._start = 0
        self._stop = None

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def range(self, start, end):
        self._start, self._stop = start, end
        return self

    def _rows(self):
        requested = (self._stop - self._start) + 1
        served = min(requested, self._cap)
        avail = max(0, self._total - self._start)
        n = min(served, avail)
        return [{"symbol": f"SYM{self._start + i:04d}", "sector": "CEMENT"} for i in range(n)]


def _install(monkeypatch, module, total_rows: int):
    calls = {"n": 0}

    async def _fake_async_execute(builder):
        calls["n"] += 1
        table = _FakeTable(total_rows)
        built = builder(SimpleNamespace(table=lambda _n: table))
        return SimpleNamespace(data=built._rows())

    monkeypatch.setattr(module, "async_execute", _fake_async_execute)
    return calls


@pytest.mark.asyncio
async def test_select_all_pages_past_the_cap(monkeypatch):
    """The live row count (1,076) must come back whole, not clipped to 1,000."""
    calls = _install(monkeypatch, db_mod, total_rows=1076)

    rows = await db_mod.select_all("psx_profile", "symbol,sector", order_by="symbol")

    assert len(rows) == 1076, f"truncated at the cap: got {len(rows)}"
    assert calls["n"] == 2, "should page exactly twice for 1,076 rows"


@pytest.mark.asyncio
async def test_select_all_returns_distinct_rows(monkeypatch):
    """Offset paging must not repeat or skip rows across page boundaries."""
    _install(monkeypatch, db_mod, total_rows=1076)

    rows = await db_mod.select_all("psx_profile", "symbol,sector", order_by="symbol")

    symbols = [r["symbol"] for r in rows]
    assert len(set(symbols)) == len(symbols), "a row was served on two pages"


@pytest.mark.asyncio
async def test_select_all_single_page_is_one_request(monkeypatch):
    """The common case must not regress into a needless second round-trip."""
    calls = _install(monkeypatch, db_mod, total_rows=42)

    rows = await db_mod.select_all("psx_profile", "symbol,sector", order_by="symbol")

    assert len(rows) == 42
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_select_all_stops_on_an_exact_page_multiple(monkeypatch):
    """Exactly 1,000 rows must terminate, not page forever on empty results."""
    calls = _install(monkeypatch, db_mod, total_rows=1000)

    rows = await db_mod.select_all("psx_profile", "symbol,sector", order_by="symbol")

    assert len(rows) == 1000
    assert calls["n"] == 2, "full page then an empty page to learn it ended"
