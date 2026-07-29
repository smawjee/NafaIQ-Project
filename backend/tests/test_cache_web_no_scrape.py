"""On the web/API process (live_scrape=False), the CacheLayer must NEVER scrape
DPS in the request path — it serves the DB or returns empty, fast. A blocking
DPS scrape here (4 retries x backoff when DPS is unreachable) was making market
endpoints take 8-13s. The worker keeps the DB populated.
"""
from types import SimpleNamespace

import pytest

from app.services import cache as cache_mod
from app.services.cache import CacheLayer


class _ExplodingDPS:
    """Every scrape raises — so any call from the web path fails the test."""

    async def fetch_market_watch(self):
        raise AssertionError("web process scraped DPS (market_watch)")

    async def fetch_symbols(self):
        raise AssertionError("web process scraped DPS (symbols)")

    async def fetch_historical(self, symbol):
        raise AssertionError("web process scraped DPS (historical)")

    async def fetch_index_snapshot(self):
        raise AssertionError("web process scraped DPS (index_snapshot)")


@pytest.fixture
def web_layer(monkeypatch):
    async def _empty(*a, **k):
        return []

    async def _no_rows(_builder):
        return SimpleNamespace(data=[])

    # Empty DB reads force the "nothing cached" path — where the old code scraped.
    monkeypatch.setattr(cache_mod, "select_all", _empty)
    # `get_live_index_snapshot` reads through `async_execute`, not `select_all`.
    # Without this stub the test hit the REAL Supabase project and passed only
    # because production's psx_index_live_snapshot happened to be stale enough to
    # be filtered out — so it went green while the scheduler was dead and red the
    # moment the data was repaired. Assert on a hermetic empty DB instead.
    monkeypatch.setattr(cache_mod, "async_execute", _no_rows)
    layer = CacheLayer(_ExplodingDPS())
    layer.live_scrape = False  # simulate PROCESS_ROLE=web
    return layer


@pytest.mark.asyncio
async def test_market_snapshot_returns_empty_not_scrape(web_layer):
    assert await web_layer.get_market_snapshot() == []


@pytest.mark.asyncio
async def test_symbols_returns_empty_not_scrape(web_layer):
    assert await web_layer.get_symbols() == []


@pytest.mark.asyncio
async def test_live_index_snapshot_returns_empty_not_scrape(web_layer):
    assert await web_layer.get_live_index_snapshot() == []


@pytest.mark.asyncio
async def test_stale_db_data_is_still_served_not_blanked(monkeypatch):
    """The real fear: does splitting the work mean 'no data'? No — when the DB
    has rows (even STALE ones from an earlier session), the web process serves
    them and NEVER scrapes. Only a genuinely empty DB yields an empty response.
    """
    stale_row = {
        "symbol": "HBL",
        "price": 120.5,
        "change": 2.0,
        "change_pct": 1.7,
        "volume": 1000,
        "day_high": 121.0,
        "day_low": 118.0,
        "refreshed_at": "2020-01-01T00:00:00+00:00",  # very stale
    }

    async def _rows(*a, **k):
        return [stale_row]

    monkeypatch.setattr(cache_mod, "select_all", _rows)
    layer = CacheLayer(_ExplodingDPS())
    layer.live_scrape = False

    items = await layer.get_market_snapshot()
    assert len(items) == 1 and items[0].symbol == "HBL" and items[0].price == 120.5


@pytest.mark.asyncio
async def test_background_refresh_is_noop_on_web(web_layer):
    called = {"n": 0}

    async def _refresh():
        called["n"] += 1

    web_layer._refresh_in_background("market_snapshot", _refresh)
    assert called["n"] == 0  # never even scheduled on the web process
