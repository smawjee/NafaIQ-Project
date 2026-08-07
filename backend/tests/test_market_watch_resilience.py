"""Market-watch resilience: TradingView fallback + AHL price-only writes.

Regression tests for the 2026-08-07 outage: DPS /market-watch dropped the
connection from Railway's egress IP while the TradingView scanner kept
working, freezing psx_market_snapshot on yesterday's close; and
job_poll_ahletrade parsed the BuySell quote tape as trades, writing an ask
quote as the price and the other quote as the volume (CNERGY showed volume
11 vs a real 42.2M shares).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.jobs import scheduler as sched
from app.schemas.market import MarketSnapshotItem


# --------------------------------------------------------------------------- #
# _market_watch_tv_fallback                                                    #
# --------------------------------------------------------------------------- #


def _tv_rows():
    return [
        {
            "symbol": "CNERGY",
            "name": "CNERGY",
            "close": 11.5,
            "change_pct": 2.2222222222222223,
            "change_abs": 0.25,
            "volume": 42223536,
            "sector": "Distribution Services",
            "market_cap": 60757529063,
            "logoid": None,
        },
        {
            "symbol": "BOP",
            "name": "BOP",
            "close": 36.05,
            "change_pct": 0.14,
            "change_abs": 0.05,
            "volume": 17997571,
            "sector": "Finance",
            "market_cap": None,
            "logoid": None,
        },
        # A symbol with no trade yet must be dropped, never written as 0.0.
        {"symbol": "DEAD1", "close": 0.0, "change_pct": None, "change_abs": None, "volume": 0},
        {"symbol": "NULLP", "close": None, "change_pct": None, "change_abs": None, "volume": None},
    ]


def test_tv_fallback_shapes_snapshot_items(monkeypatch):
    monkeypatch.setattr(sched.tv, "fetch_market_data", AsyncMock(return_value=_tv_rows()))

    items = asyncio.run(sched._market_watch_tv_fallback())

    assert [i.symbol for i in items] == ["CNERGY", "BOP"]
    c = items[0]
    assert isinstance(c, MarketSnapshotItem)
    assert c.price == 11.5
    assert c.change == 0.25
    assert round(c.change_pct, 2) == 2.22
    assert c.volume == 42223536
    # TV has no session extremes; the writer omits these columns so the upsert
    # preserves the last DPS-derived values.
    assert c.day_high is None
    assert c.day_low is None


def test_tv_fallback_skips_non_positive_prices(monkeypatch):
    monkeypatch.setattr(sched.tv, "fetch_market_data", AsyncMock(return_value=_tv_rows()))

    items = asyncio.run(sched._market_watch_tv_fallback())

    assert all(i.price > 0 for i in items)


# --------------------------------------------------------------------------- #
# job_poll_ahletrade: price-only writes                                        #
# --------------------------------------------------------------------------- #


class _FakeClient:
    """Stands in for the supabase-py client chain the job builds lambdas for.

    `c.table(...).select(...).order(...).limit(...)` must return an object with
    `.data` (the top-20 read), and `c.rpc(...)` must record its payload (the
    patch write). One client object serves both shapes.
    """

    def __init__(self):
        self.rpc_calls: list[list[dict]] = []
        self.data = [
            {"symbol": "CNERGY", "volume": 10_000_000},
            {"symbol": "BOP", "volume": 9_000_000},
        ]

    def table(self, name):
        return self

    def select(self, *cols):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def rpc(self, name, payload):
        self.rpc_calls.append(payload["rows"])
        return self


def _patch_ahle_job(monkeypatch, trades_by_symbol):
    monkeypatch.setattr(sched, "_is_market_open", AsyncMock(return_value=True))

    async def _fake_fetch_trades(sym, market="REG"):
        return trades_by_symbol.get(sym, [])

    monkeypatch.setattr(sched.ahletrade, "fetch_trades", _fake_fetch_trades)

    client = _FakeClient()

    async def _fake_execute(call):
        return call(client)

    monkeypatch.setattr(sched, "async_execute", _fake_execute)
    monkeypatch.setattr(sched, "_record_health", AsyncMock())
    return client


def test_ahle_job_writes_price_only_and_skips_bad_prices(monkeypatch):
    trades = {
        "CNERGY": [
            {"time": "11:59:57", "price": 11.5, "volume": 500},
        ],
        # A stale "no trade" tick (price 0.0) must not be written.
        "BOP": [{"time": "12:00:00", "price": 0.0, "volume": 0}],
    }
    client = _patch_ahle_job(monkeypatch, trades)

    asyncio.run(sched.job_poll_ahletrade())

    assert len(client.rpc_calls) == 1
    rows = client.rpc_calls[0]
    assert len(rows) == 1
    assert rows[0]["symbol"] == "CNERGY"
    assert rows[0]["price"] == 11.5
    # Volume is AHL-owned per-trade data and must never clobber the cumulative
    # DPS figure.
    assert "volume" not in rows[0]
    assert "refreshed_at" in rows[0]


def test_ahle_job_patches_nothing_when_no_trades(monkeypatch):
    client = _patch_ahle_job(monkeypatch, {"CNERGY": [], "BOP": []})

    asyncio.run(sched.job_poll_ahletrade())

    assert client.rpc_calls == []
