"""Treemap sizing: never present a proxy as a real market cap.

`psx_profile.listed_shares` is NULL for most symbols, so the treemap falls back
to a `price * sqrt(volume)` proxy to size tiles. That proxy must stay in
`size_metric`; `market_cap` must be None so the UI renders "—" rather than an
invented figure. These tests pin that contract.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.market import treemap as tm


@pytest.fixture(autouse=True)
def _clear_cache():
    """get_treemap memoizes for 15s — reset around every test."""
    tm._last_treemap_cache = None
    tm._last_treemap_time = 0
    yield
    tm._last_treemap_cache = None
    tm._last_treemap_time = 0


def _fake_async_execute(snapshot_rows, profile_rows):
    """Return the snapshot rows on the 1st call, profile rows on the 2nd."""
    calls = {"n": 0}

    async def _fake(_builder):
        calls["n"] += 1
        data = snapshot_rows if calls["n"] == 1 else profile_rows
        return SimpleNamespace(data=data)

    return _fake


@pytest.mark.asyncio
async def test_real_market_cap_when_listed_shares_present(monkeypatch):
    monkeypatch.setattr(
        tm,
        "async_execute",
        _fake_async_execute(
            [{"symbol": "HBL", "price": 100.0, "change_pct": 1.0, "volume": 1000}],
            [{"symbol": "HBL", "sector": "BANKING", "name": "Habib Bank",
              "listed_shares": 1_000_000, "logoid": None}],
        ),
    )
    result = await tm.get_treemap()
    stock = result["sectors"][0]["stocks"][0]

    assert stock["sizing_basis"] == "market_cap"
    assert stock["market_cap"] == 100.0 * 1_000_000
    assert stock["size_metric"] == 100.0 * 1_000_000
    # Sector cap is reportable because every stock had a real cap.
    assert result["sectors"][0]["total_market_cap"] == 100.0 * 1_000_000


@pytest.mark.asyncio
async def test_market_cap_is_none_when_listed_shares_missing(monkeypatch):
    """The regression this guards: a proxy leaking into `market_cap`."""
    monkeypatch.setattr(
        tm,
        "async_execute",
        _fake_async_execute(
            [{"symbol": "OGDC", "price": 100.0, "change_pct": 2.0, "volume": 10_000}],
            [{"symbol": "OGDC", "sector": "OIL & GAS", "name": "Oil & Gas Dev",
              "listed_shares": None, "logoid": None}],
        ),
    )
    result = await tm.get_treemap()
    stock = result["sectors"][0]["stocks"][0]

    assert stock["market_cap"] is None, "proxy must never be reported as market_cap"
    assert stock["sizing_basis"] == "volume_proxy"
    # price * sqrt(volume) * 100 == 100 * 100 * 100
    assert stock["size_metric"] == pytest.approx(100.0 * (10_000 ** 0.5) * 100.0)
    # Tile still has non-zero area, so the heatmap is not empty.
    assert stock["size_metric"] > 0
    # Sector cap is withheld rather than under-reported.
    assert result["sectors"][0]["total_market_cap"] is None
    assert result["sectors"][0]["total_size_metric"] == stock["size_metric"]


@pytest.mark.asyncio
async def test_sector_cap_withheld_when_only_some_stocks_have_real_caps(monkeypatch):
    monkeypatch.setattr(
        tm,
        "async_execute",
        _fake_async_execute(
            [
                {"symbol": "AAA", "price": 10.0, "change_pct": 1.0, "volume": 100},
                {"symbol": "BBB", "price": 20.0, "change_pct": 1.0, "volume": 100},
            ],
            [
                {"symbol": "AAA", "sector": "MIXED", "name": "A",
                 "listed_shares": 1000, "logoid": None},
                {"symbol": "BBB", "sector": "MIXED", "name": "B",
                 "listed_shares": None, "logoid": None},
            ],
        ),
    )
    result = await tm.get_treemap()
    sector = result["sectors"][0]

    # A partial sum would silently understate the sector — withhold instead.
    assert sector["total_market_cap"] is None
    assert sector["stock_count"] == 2


@pytest.mark.asyncio
async def test_stock_skipped_only_when_both_signals_absent(monkeypatch):
    monkeypatch.setattr(
        tm,
        "async_execute",
        _fake_async_execute(
            [{"symbol": "DEAD", "price": 5.0, "change_pct": 0.0, "volume": 0}],
            [{"symbol": "DEAD", "sector": "X", "name": "Dead Co",
              "listed_shares": None, "logoid": None}],
        ),
    )
    result = await tm.get_treemap()
    assert result["stock_count"] == 0
    assert result["sectors"] == []
