"""The live index snapshot cutoff must tolerate a missed scheduler beat.

``job_refresh_index_snapshot`` runs on a 5-minute cron. When the staleness
cutoff in ``get_live_index_snapshot`` was also 300s, a row written at T expired
at exactly T+300 — the moment the next run *starts*, before it has scraped the
DPS homepage and written. Every cycle therefore had a dead window in which the
web process discarded a perfectly good snapshot and every index card fell back
to the previous day's EOD close, pinned there for up to TTL_INDEX (60s) by the
in-process memo.

These tests pin the tolerance in both directions: one missed beat still serves
live values, a genuinely dead scheduler still stops serving them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import cache as cache_mod
from app.services.cache import CacheLayer


class _ExplodingDPS:
    async def fetch_index_snapshot(self):
        raise AssertionError("web process scraped DPS (index_snapshot)")


def _layer(monkeypatch, age_seconds: float):
    """A web-role CacheLayer whose only snapshot row is `age_seconds` old."""
    written = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()

    async def _fake_async_execute(builder):
        class _Tbl:
            def select(self, *_a, **_k):
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(
            data=[
                {
                    "code": "KSE100",
                    "date": "2026-07-29",
                    "close": 176467.37,
                    "prev_close": 177623.88,
                    "change": -1156.51,
                    "change_pct": -0.65,
                    "updated_at": written,
                }
            ]
        )

    monkeypatch.setattr(cache_mod, "async_execute", _fake_async_execute)
    layer = CacheLayer(_ExplodingDPS())
    layer.live_scrape = False  # PROCESS_ROLE=web
    return layer


@pytest.mark.asyncio
async def test_one_missed_beat_still_serves_live_values(monkeypatch):
    """A 6-minute-old snapshot is one skipped cron beat, not a dead scheduler."""
    layer = _layer(monkeypatch, age_seconds=360)

    rows = await layer.get_live_index_snapshot()

    assert [r["code"] for r in rows] == ["KSE100"]
    assert rows[0]["close"] == 176467.37


@pytest.mark.asyncio
async def test_snapshot_at_the_old_knife_edge_still_serves(monkeypatch):
    """Exactly 300s old — the age the previous cutoff rejected outright."""
    layer = _layer(monkeypatch, age_seconds=300)

    assert await layer.get_live_index_snapshot() != []


@pytest.mark.asyncio
async def test_dead_scheduler_stops_serving_live_values(monkeypatch):
    """20 minutes with no write means the worker is down — fall back to EOD."""
    layer = _layer(monkeypatch, age_seconds=1200)

    assert await layer.get_live_index_snapshot() == []
