"""An index card must never be a full day stale while today's close is on hand.

`get_live_index_snapshot` drops snapshot rows older than 900s so an intraday
card can't pass a stale tick off as live. Correct during the session; wrong
after it. `job_refresh_index_snapshot` stops writing at 16:55 PKT, so from
~17:10 PKT the live tier is empty and `index_cards` falls back to
`psx_index_eod` — which does not hold today's close until the 18:00 PKT ingest
lands. On 2026-08-05 that ingest was skipped outright (APScheduler's 1s default
misfire grace) and 17 of 18 cards served the *previous* day's close for hours,
while the correct values sat unread in `psx_index_live_snapshot`.

These tests pin the tie-break in both directions: a snapshot newer than the
newest EOD bar wins, and a snapshot older than it never does.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.models import IndexBar
from app.services.market import quotes


def _bar(code: str, day: date, close: float) -> IndexBar:
    return IndexBar(code=code, date=day, open=close, high=close, low=close, close=close)


def _wire(monkeypatch, *, eod: list[IndexBar], snapshot: list[dict]):
    """Serve one index code, with the live (<900s) tier empty as it is after close."""
    monkeypatch.setattr(quotes, "INDEX_CARD_CODES", ["KSE30"])
    monkeypatch.setattr(quotes.mem_cache, "get_or_load", lambda _k, _t, load: load())

    async def _no_live():
        return {}

    monkeypatch.setattr(quotes, "_live_index_by_code", _no_live)

    async def _get_index_latest(code, bars=2):
        return eod[:bars]

    async def _get_index_snapshot_any_age():
        return snapshot

    monkeypatch.setattr(
        quotes,
        "get_cache",
        lambda: SimpleNamespace(
            get_index_latest=_get_index_latest,
            get_index_snapshot_any_age=_get_index_snapshot_any_age,
        ),
    )


_TODAY_SNAPSHOT = {
    "code": "KSE30",
    "date": "2026-08-05",
    "close": 53821.81,
    "prev_close": 52836.31,
    "change": 985.5,
    "change_pct": 1.87,
    "updated_at": "2026-08-05T11:15:02+00:00",
}


@pytest.mark.asyncio
async def test_stale_snapshot_beats_an_older_eod_bar(monkeypatch):
    """The exact 2026-08-05 outage: EOD stops at the 4th, snapshot has the 5th."""
    _wire(
        monkeypatch,
        eod=[
            _bar("KSE30", date(2026, 8, 4), 52836.31),
            _bar("KSE30", date(2026, 8, 3), 53213.70),
        ],
        snapshot=[_TODAY_SNAPSHOT],
    )

    (card,) = await quotes.index_cards()

    assert card["date"] == "2026-08-05"
    assert card["close"] == 53821.81
    assert card["change_pct"] == 1.87


@pytest.mark.asyncio
async def test_without_a_snapshot_the_stale_eod_bar_is_all_there_is(monkeypatch):
    """Pins the delta: identical EOD input, empty snapshot tier -> the old,
    day-stale card. If this and the test above ever agree, the tie-break is
    dead and the regression is back."""
    _wire(
        monkeypatch,
        eod=[
            _bar("KSE30", date(2026, 8, 4), 52836.31),
            _bar("KSE30", date(2026, 8, 3), 53213.70),
        ],
        snapshot=[],
    )

    (card,) = await quotes.index_cards()

    assert card["date"] == "2026-08-04"
    assert card["close"] == 52836.31


@pytest.mark.asyncio
async def test_fresher_eod_is_not_overridden_by_an_older_snapshot(monkeypatch):
    """Once the ingest lands, the official close outranks yesterday's snapshot."""
    _wire(
        monkeypatch,
        eod=[
            _bar("KSE30", date(2026, 8, 6), 54000.00),
            _bar("KSE30", date(2026, 8, 5), 53821.81),
        ],
        snapshot=[_TODAY_SNAPSHOT],
    )

    (card,) = await quotes.index_cards()

    assert card["date"] == "2026-08-06"
    assert card["close"] == 54000.00


@pytest.mark.asyncio
async def test_same_day_snapshot_does_not_displace_the_eod_bar(monkeypatch):
    """Equal dates are not 'newer' — the settled close stays authoritative."""
    _wire(
        monkeypatch,
        eod=[
            _bar("KSE30", date(2026, 8, 5), 53821.81),
            _bar("KSE30", date(2026, 8, 4), 52836.31),
        ],
        snapshot=[_TODAY_SNAPSHOT],
    )

    (card,) = await quotes.index_cards()

    assert card["date"] == "2026-08-05"
    assert card["prev_close"] == 52836.31  # computed from EOD, not the snapshot


@pytest.mark.asyncio
async def test_snapshot_serves_a_card_when_there_is_no_eod_history(monkeypatch):
    _wire(monkeypatch, eod=[], snapshot=[_TODAY_SNAPSHOT])

    (card,) = await quotes.index_cards()

    assert card["date"] == "2026-08-05"


@pytest.mark.asyncio
async def test_no_eod_and_no_snapshot_yields_no_card(monkeypatch):
    _wire(monkeypatch, eod=[], snapshot=[])

    assert await quotes.index_cards() == []
