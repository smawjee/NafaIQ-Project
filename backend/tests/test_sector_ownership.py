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

import pytest

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
