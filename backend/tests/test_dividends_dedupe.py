"""job_refresh_dividends must not send duplicate announcement_ids in one upsert.

Observed in production (Railway, 2026-07-16):

    postgrest.exceptions.APIError: {'message': 'ON CONFLICT DO UPDATE command
    cannot affect row a second time', 'code': '21000', 'hint': 'Ensure that no
    rows proposed for insertion within the same command have duplicate
    constrained values.'}

DPS returns the same announcement twice for some symbols. Postgres rejects the
ENTIRE batch when two proposed rows share the ON CONFLICT target, so one
duplicated payout loses every dividend for that symbol — not just the dupe.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.jobs import scheduler as sched


def _payout(announcement_id: str, symbol: str = "HBL", per_share: float = 1.5):
    return SimpleNamespace(
        announcement_id=announcement_id,
        symbol=symbol,
        ex_date=date(2026, 5, 1),
        announcement_date=date(2026, 4, 1),
        payout_type="cash",
        per_share=per_share,
        bonus_pct=None,
    )


def _drive(monkeypatch, events):
    """Run job_refresh_dividends against fakes; return the rows it upserted."""
    upserted: list[list[dict]] = []

    async def _fake_select_all(_table, _cols, **_kw):
        return [{"symbol": "HBL"}]

    async def _fake_payouts(_sym):
        return events

    async def _fake_async_execute(builder):
        class _Tbl:
            def upsert(self, rows, **_kw):
                upserted.append(rows)
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(data=[])

    async def _fake_health(*_a, **_k):
        return None

    monkeypatch.setattr(sched, "select_all", _fake_select_all)
    monkeypatch.setattr(sched.dps, "fetch_payouts", _fake_payouts)
    monkeypatch.setattr(sched, "async_execute", _fake_async_execute)
    monkeypatch.setattr(sched, "_record_health", _fake_health)
    return upserted


@pytest.mark.asyncio
async def test_duplicate_announcement_ids_are_collapsed(monkeypatch):
    """Two payouts sharing an announcement_id must upsert as ONE row.

    This is the exact shape that produced 21000 in production.
    """
    upserted = _drive(
        monkeypatch,
        [_payout("A-1"), _payout("A-1"), _payout("A-2")],
    )

    await sched.job_refresh_dividends()

    assert upserted, "job upserted nothing"
    rows = upserted[0]
    ids = [r["announcement_id"] for r in rows]
    assert len(ids) == len(set(ids)), f"duplicate conflict targets in one batch: {ids}"
    assert sorted(ids) == ["A-1", "A-2"]


@pytest.mark.asyncio
async def test_distinct_announcements_all_survive(monkeypatch):
    """Dedupe must not drop genuinely distinct payouts."""
    upserted = _drive(
        monkeypatch,
        [_payout("A-1"), _payout("A-2"), _payout("A-3")],
    )

    await sched.job_refresh_dividends()

    assert sorted(r["announcement_id"] for r in upserted[0]) == ["A-1", "A-2", "A-3"]
