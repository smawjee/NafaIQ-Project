"""Index EOD cache must not serve old KSE/KMI rows forever.

The PSX page's index cards and KSE-100 chart read ``psx_index_eod``. If that
table has any rows, the read-through cache used to return them indefinitely,
even when the newest row was days behind DPS. These tests pin both the freshness
refresh and the OHLC fields needed by the candlestick chart.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.models import IndexBar
from app.scrapers.dps import DPSScraper
from app.services import cache as cache_mod
from app.services.market import quotes as quotes_mod


class _FakeTable:
    def __init__(self, select_rows: list[dict]):
        self.select_rows = select_rows
        self.limit_n: int | None = None
        self.upserted: list[dict] | None = None

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def upsert(self, rows, **_kw):
        self.upserted = rows
        return self


def _install_index_db(monkeypatch, rows: list[dict]):
    calls = {"selects": 0, "upserts": []}

    async def _fake_async_execute(builder):
        table = _FakeTable(rows)
        built = builder(SimpleNamespace(table=lambda _name: table))
        if built.upserted is not None:
            calls["upserts"].append(built.upserted)
            return SimpleNamespace(data=[])
        calls["selects"] += 1
        data = rows[: built.limit_n] if built.limit_n is not None else rows
        return SimpleNamespace(data=data)

    monkeypatch.setattr(cache_mod, "async_execute", _fake_async_execute)
    return calls


class _IndexDPS:
    def __init__(self):
        self.calls: list[str] = []

    async def fetch_index_eod(self, code: str):
        self.calls.append(code)
        return [
            IndexBar(
                code=code,
                date=date(2026, 7, 17),
                open=178123.56,
                high=178694.48,
                low=175790.62,
                close=175802.78,
                volume=267055616,
            ),
            IndexBar(
                code=code,
                date=date(2026, 7, 16),
                open=173500.00,
                high=176000.00,
                low=172900.00,
                close=175285.78,
                volume=583804947,
            ),
        ]


class _ExplodingDPS:
    async def fetch_index_eod(self, code: str):  # pragma: no cover
        raise AssertionError(f"unexpected scrape for {code}")


@pytest.mark.asyncio
async def test_stale_index_rows_refresh_from_dps_and_write_ohlc(monkeypatch):
    monkeypatch.setattr(cache_mod, "_expected_latest_index_date", lambda: date(2026, 7, 17))
    calls = _install_index_db(
        monkeypatch,
        [
            {
                "code": "KSE100",
                "date": "2026-07-09",
                "open": 180000.00,
                "high": 181500.00,
                "low": 179000.00,
                "close": 181259.67,
                "volume": 470840072,
            }
        ],
    )
    dps = _IndexDPS()

    bars = await cache_mod.CacheLayer(dps).get_index_eod("KSE100")

    assert dps.calls == ["KSE100"]
    assert bars[0].date == date(2026, 7, 17)
    assert bars[0].open == 178123.56
    assert calls["upserts"], "fresh DPS rows should be persisted"
    written = calls["upserts"][0][0]
    assert written["open"] == 178123.56
    assert written["high"] == 178694.48
    assert written["low"] == 175790.62


@pytest.mark.asyncio
async def test_fresh_index_rows_do_not_scrape_and_preserve_ohlc(monkeypatch):
    monkeypatch.setattr(cache_mod, "_expected_latest_index_date", lambda: date(2026, 7, 17))
    calls = _install_index_db(
        monkeypatch,
        [
            {
                "code": "KSE100",
                "date": "2026-07-17",
                "open": 178123.56,
                "high": 178694.48,
                "low": 175790.62,
                "close": 175802.78,
                "volume": 267055616,
            }
        ],
    )

    bars = await cache_mod.CacheLayer(_ExplodingDPS()).get_index_latest("KSE100", bars=1)

    assert calls["upserts"] == []
    assert bars[0].open == 178123.56
    assert bars[0].high == 178694.48
    assert bars[0].low == 175790.62


@pytest.mark.asyncio
async def test_dps_live_index_snapshot_parses_top_index_strip(monkeypatch):
    dps = DPSScraper()

    async def _fake_get(path: str) -> str:
        assert path == "/"
        return """
        <html><body>
          <div>Jul 20, 2026 1:42 PM</div>
          <div class="topIndices__item">
            <div>
              <div class="topIndices__item__name">KSE100</div>
              <div class="topIndices__item__val">175,655.77</div>
            </div>
            <div class="change__text--neg">
              <div class="topIndices__item__change">-147.01</div>
              <div class="topIndices__item__changep">(-0.08%)</div>
            </div>
          </div>
          <div class="topIndices__item">
            <div>
              <div class="topIndices__item__name">KMI30</div>
              <div class="topIndices__item__val">247,393.83</div>
            </div>
            <div class="change__text--pos">
              <div class="topIndices__item__change">70.46</div>
              <div class="topIndices__item__changep">(0.03%)</div>
            </div>
          </div>
        </body></html>
        """

    monkeypatch.setattr(dps, "_get", _fake_get)

    rows = await dps.fetch_index_snapshot()

    assert rows == [
        {
            "code": "KSE100",
            "date": "2026-07-20",
            "close": 175655.77,
            "prev_close": 175802.78,
            "change": -147.01,
            "change_pct": -0.08,
        },
        {
            "code": "KMI30",
            "date": "2026-07-20",
            "close": 247393.83,
            "prev_close": 247323.37,
            "change": 70.46,
            "change_pct": 0.03,
        },
    ]


class _QuoteCache:
    async def get_live_index_snapshot(self):
        return [
            {
                "code": "KSE100",
                "date": "2026-07-20",
                "close": 175655.77,
                "prev_close": 175802.78,
                "change": -147.01,
                "change_pct": -0.08,
            }
        ]

    async def get_index_latest(self, code: str, bars: int = 2):
        return [
            IndexBar(code=code, date=date(2026, 7, 17), close=175802.78),
            IndexBar(code=code, date=date(2026, 7, 16), close=175285.78),
        ]

    async def get_index_eod(self, code: str):
        return [IndexBar(code=code, date=date(2026, 7, 17), close=175802.78)]


@pytest.mark.asyncio
async def test_index_cards_prefer_live_dps_values(monkeypatch):
    quotes_mod.mem_cache._data.clear()
    monkeypatch.setattr(quotes_mod, "INDEX_CARD_CODES", ["KSE100"])
    monkeypatch.setattr(quotes_mod, "get_cache", lambda: _QuoteCache())

    cards = await quotes_mod.index_cards()

    assert cards == [
        {
            "code": "KSE100",
            "date": "2026-07-20",
            "close": 175655.77,
            "prev_close": 175802.78,
            "change": -147.01,
            "change_pct": -0.08,
        }
    ]


@pytest.mark.asyncio
async def test_index_eod_appends_live_point_after_latest_eod(monkeypatch):
    quotes_mod.mem_cache._data.clear()
    monkeypatch.setattr(quotes_mod, "get_cache", lambda: _QuoteCache())

    bars = await quotes_mod.index_eod("KSE100")

    assert [b["date"] for b in bars] == ["2026-07-17", "2026-07-20"]
    assert bars[-1]["close"] == 175655.77
