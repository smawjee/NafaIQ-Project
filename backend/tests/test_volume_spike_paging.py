"""The volume-spike detector's OHLCV batch read must page past PostgREST's cap.

VolumeSpikeDetector pulls a 31-day trailing window for the whole market in one
batch — ~500 symbols x ~21 trading days is ~10k rows, but PostgREST caps any
single response at ~1000 regardless of the filters. An unpaginated read would
silently see only the alphabetically first ~5% of symbols and still report
success: every symbol past the cut has no trailing average, so it can never
trigger a spike. The detector would look healthy while blind to most of PSX.

Note the psx_market_snapshot read goes through `select_all` (pinned by
test_profile_paging.py); the OHLCV batch is the module's own `.range()` loop,
which is what these tests pin.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.signals import volume_spikes as vs_mod

_DAYS = 30
# 60 symbols x 30 bars = 1,800 rows, comfortably past the 1,000-row cap.
_SYMBOLS = [f"SYM{i:03d}" for i in range(60)]
# Ordered last by symbol, so its bars sit at offset ~1,770 — page 2.
_SPIKER = _SYMBOLS[-1]
_BASE_VOL = 100.0


def _ohlcv_dataset(symbols: list[str]) -> list[dict]:
    """Every symbol's bars, ordered by (symbol, date) as the query asks."""
    return [
        {"symbol": s, "volume": _BASE_VOL, "date": f"2026-06-{d + 1:02d}"}
        for s in symbols
        for d in range(_DAYS)
    ]


class _FakeOhlcvTable:
    """PostgREST builder stub that enforces the ~1000-row page cap."""

    def __init__(self, rows: list[dict], page_cap: int = 1000):
        self._all = rows
        self._cap = page_cap
        self._start = 0
        self._stop = len(rows) - 1

    def select(self, *_a, **_k):
        return self

    def gte(self, *_a, **_k):
        return self

    def lt(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def range(self, start, end):
        self._start, self._stop = start, end
        return self

    def _rows(self):
        requested = (self._stop - self._start) + 1
        # The behaviour being guarded: the server never returns more than the
        # cap in one response, however wide the requested range.
        served = min(requested, self._cap)
        return self._all[self._start : self._start + served]


class _FakeWriteTable:
    """psx_unusual_activity: absorb the cleanup delete and the result upsert."""

    def __init__(self, sink: list[dict]):
        self._sink = sink

    def delete(self):
        return self

    def lt(self, *_a, **_k):
        return self

    def upsert(self, rows, **_k):
        self._sink.extend(rows)
        return self

    def _rows(self):
        return []


def _install(monkeypatch, symbols: list[str], rows: list[dict]):
    calls = {"ohlcv": 0}
    written: list[dict] = []

    async def _fake_select_all(_table, _columns, **_k):
        # Snapshot: only _SPIKER trades at 10x its trailing average; the rest sit
        # at 1x and must fall below VOLUME_RATIO_THRESHOLD.
        return [
            {
                "symbol": s,
                "price": 10.0,
                "change_pct": 5.0,
                "volume": _BASE_VOL * (10 if s == _SPIKER else 1),
                "refreshed_at": "2026-07-16T00:00:00Z",
            }
            for s in symbols
        ]

    async def _fake_async_execute(builder):
        def _table(name):
            if name == "psx_ohlcv":
                calls["ohlcv"] += 1
                return _FakeOhlcvTable(rows)
            return _FakeWriteTable(written)

        built = builder(SimpleNamespace(table=_table))
        return SimpleNamespace(data=built._rows())

    monkeypatch.setattr(vs_mod, "select_all", _fake_select_all)
    monkeypatch.setattr(vs_mod, "async_execute", _fake_async_execute)
    return calls, written


@pytest.mark.asyncio
async def test_detector_sees_symbols_past_the_1000_row_cap(monkeypatch):
    """The spiking symbol's bars live on page 2 — an unpaginated read is blind
    to them, so the spike would never fire."""
    calls, written = _install(monkeypatch, _SYMBOLS, _ohlcv_dataset(_SYMBOLS))

    triggered = await vs_mod.VolumeSpikeDetector().detect()

    found = [t["symbol"] for t in triggered]
    assert _SPIKER in found, (
        f"{_SPIKER}'s bars start at offset ~{(len(_SYMBOLS) - 1) * _DAYS}; "
        f"the OHLCV read was clipped at the first page (found: {found})"
    )
    assert calls["ohlcv"] >= 2, "1,800 rows must take more than one page"
    # A 10x volume day at a 100-share average.
    assert [w["symbol"] for w in written] == [_SPIKER]
    assert triggered[0]["volume_ratio"] == 10.0


@pytest.mark.asyncio
async def test_symbols_within_the_first_page_still_resolve(monkeypatch):
    """Control: paging must not lose the rows it already had. Every non-spiking
    symbol sits at 1x and must stay below the ratio threshold."""
    _install(monkeypatch, _SYMBOLS, _ohlcv_dataset(_SYMBOLS))

    triggered = await vs_mod.VolumeSpikeDetector().detect()

    assert [t["symbol"] for t in triggered] == [_SPIKER], (
        "only the 10x symbol should trigger; a duplicated page would inflate "
        "other symbols' averages or emit spurious rows"
    )


@pytest.mark.asyncio
async def test_single_page_dataset_is_one_request(monkeypatch):
    """The small-market case must not regress into a needless round-trip."""
    symbols = _SYMBOLS[:5]  # 5 x 30 = 150 rows, one short page
    calls, _ = _install(monkeypatch, symbols, _ohlcv_dataset(symbols))

    await vs_mod.VolumeSpikeDetector().detect()

    assert calls["ohlcv"] == 1


@pytest.mark.asyncio
async def test_paging_stops_on_an_exact_page_multiple(monkeypatch):
    """Exactly 1,000 rows must terminate on the empty page, not loop to the
    60k runaway guard."""
    rows = _ohlcv_dataset(_SYMBOLS)[:1000]
    calls, _ = _install(monkeypatch, _SYMBOLS, rows)

    await vs_mod.VolumeSpikeDetector().detect()

    assert calls["ohlcv"] == 2, "full page, then an empty page to learn it ended"
