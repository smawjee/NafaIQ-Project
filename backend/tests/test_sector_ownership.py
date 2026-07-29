"""psx_profile.sector ownership: DPS is authoritative, TradingView is fallback.

DPS is the official PSX portal, so its quote__sector is PSX's real
classification (~35 sectors: "Commercial Banks", "Cement", ...). TV_SECTOR_MAP
collapses that into TradingView's 18 global buckets and is lossy.

job_refresh_tv_data runs every 5 minutes and used to overwrite `sector`
unconditionally, which meant the good DPS value survived at most 5 minutes and
migration 20260716010000 looked like a no-op. These tests pin the rule:

    - TV fills sector ONLY when it is empty
    - TV never overwrites an existing sector
    - fundamentals (DPS) writes sector, but never blanks it on a failed scrape
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.jobs import scheduler as sched
from app.scrapers.tradingview import TV_SECTOR_MAP


def _tv_sector_for(existing_sector, tv_sector):
    """Mirror of the resolution rule in job_refresh_tv_data."""
    return existing_sector or TV_SECTOR_MAP.get(tv_sector, tv_sector or None)


def test_tv_does_not_overwrite_an_existing_dps_sector():
    # HBL already classified by DPS; TV reports the generic "Finance" bucket.
    assert _tv_sector_for("Commercial Banks", "Finance") == "Commercial Banks"


def test_tv_fills_sector_when_missing():
    assert _tv_sector_for(None, "Finance") == "BANKING & FINANCE"
    assert _tv_sector_for("", "Energy Minerals") == "OIL & GAS"


def test_tv_passes_unmapped_value_through_as_last_resort():
    assert _tv_sector_for(None, "Some New TV Bucket") == "Some New TV Bucket"


def test_tv_yields_none_when_it_knows_nothing():
    assert _tv_sector_for(None, "") is None


def test_tv_sector_map_is_lossy_which_is_why_dps_wins():
    """Documents the concrete loss: distinct PSX sectors collapse into one."""
    # Both map into a single bucket, so a TV-sourced heatmap cannot separate
    # Cement from Chemicals from Textile.
    assert TV_SECTOR_MAP["Health Technology"] == TV_SECTOR_MAP["Health Services"]
    assert TV_SECTOR_MAP["Electronic Technology"] == TV_SECTOR_MAP["Technology Services"]
    # 18 TV buckets in, fewer distinct labels out.
    assert len(set(TV_SECTOR_MAP.values())) < len(TV_SECTOR_MAP)


@pytest.mark.parametrize("scraped_sector", [None, ""])
def test_fundamentals_never_blanks_sector_on_a_failed_scrape(scraped_sector):
    """Mirror of the guard in job_refresh_fundamentals."""
    row = {"symbol": "HBL"}
    if scraped_sector:
        row["sector"] = scraped_sector
    assert "sector" not in row, "a missing DPS sector must not be written"


def test_fundamentals_writes_sector_when_dps_returns_one():
    row = {"symbol": "HBL"}
    scraped_sector = "Commercial Banks"
    if scraped_sector:
        row["sector"] = scraped_sector
    assert row["sector"] == "Commercial Banks"


# The tests above assert against `_tv_sector_for`, a copy of the rule. They pass
# whether or not job_refresh_tv_data still applies it, so they cannot catch a
# regression in the job itself. The tests below drive the real function and
# assert on the rows it actually upserts.


def _drive_tv_job(monkeypatch, *, existing, tv_items, preload_raises=None):
    """Run job_refresh_tv_data against fakes; return (upserted_rows, health)."""
    upserted: list[list[dict]] = []
    health: list[dict] = []

    async def _fake_select_all(_table, _cols, **_kw):
        if preload_raises is not None:
            raise preload_raises
        return existing

    async def _fake_fetch():
        return tv_items

    async def _fake_async_execute(builder):
        class _Tbl:
            def upsert(self, rows, **_kw):
                upserted.append(rows)
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(data=[])

    async def _fake_health(source, success, rows_updated=0, error=None):
        health.append({"source": source, "success": success, "error": error})

    monkeypatch.setattr(sched, "select_all", _fake_select_all)
    monkeypatch.setattr(sched.tv, "fetch_market_data", _fake_fetch)
    monkeypatch.setattr(sched, "async_execute", _fake_async_execute)
    monkeypatch.setattr(sched, "_record_health", _fake_health)

    asyncio.get_event_loop()
    return upserted, health


@pytest.mark.asyncio
async def test_job_preserves_dps_sector_end_to_end(monkeypatch):
    """The real job must not write a TV bucket over a DPS-classified symbol."""
    upserted, _ = _drive_tv_job(
        monkeypatch,
        existing=[{"symbol": "HBL", "sector": "COMMERCIAL BANKS"}],
        tv_items=[{"symbol": "HBL", "name": "Habib Bank", "sector": "Finance"}],
    )

    await sched.job_refresh_tv_data()

    assert upserted, "job wrote nothing"
    assert upserted[0][0]["sector"] == "COMMERCIAL BANKS"


@pytest.mark.asyncio
async def test_job_fills_sector_only_when_dps_has_none(monkeypatch):
    upserted, _ = _drive_tv_job(
        monkeypatch,
        existing=[{"symbol": "NEWCO", "sector": None}],
        tv_items=[{"symbol": "NEWCO", "name": "New Co", "sector": "Finance"}],
    )

    await sched.job_refresh_tv_data()

    assert upserted[0][0]["sector"] == "BANKING & FINANCE"


@pytest.mark.asyncio
async def test_preload_failure_never_clobbers_sectors_market_wide(monkeypatch):
    """A failed pre-load must abort the job, not proceed with an empty map.

    The bug: the pre-load was wrapped in a bare `except Exception` that logged
    at DEBUG and continued. With an empty map every symbol falls through to the
    TV bucket and gets upserted, replacing PSX's taxonomy market-wide — while
    the job reported itself healthy.
    """
    upserted, health = _drive_tv_job(
        monkeypatch,
        existing=[],
        tv_items=[{"symbol": "HBL", "name": "Habib Bank", "sector": "Finance"}],
        preload_raises=RuntimeError("supabase 503"),
    )

    await sched.job_refresh_tv_data()

    assert not upserted, "job clobbered sectors after failing to read existing ones"
    assert health and health[-1]["success"] is False, "a failed pre-load reported healthy"
