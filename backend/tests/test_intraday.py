"""Intraday 5-minute bar capture and reads.

The chart's "1D" timeframe used to render five DAILY candles because no
intraday series was stored anywhere — both live tables are upsert-on-key. These
tests pin the pure parts of `psx_intraday`'s writer and reader: bucket
alignment, how a sample folds into an in-progress bucket, and the cumulative →
per-bar volume diff (the one place an off-by-one silently produces plausible
but wrong candles).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.market import intraday as mod

UTC = timezone.utc


def _at(hh: int, mm: int, ss: int = 0) -> datetime:
    return datetime(2026, 8, 6, hh, mm, ss, tzinfo=UTC)


# ---------- bucketing ----------


@pytest.mark.parametrize(
    "minute,expected",
    [(0, 0), (1, 0), (4, 0), (5, 5), (9, 5), (10, 10), (57, 55), (59, 55)],
)
def test_bucket_start_floors_to_five_minutes(minute, expected):
    assert mod.bucket_start(_at(9, minute, 42)).minute == expected


def test_bucket_start_zeroes_seconds_and_micros():
    got = mod.bucket_start(_at(9, 7, 31).replace(microsecond=999))
    assert (got.second, got.microsecond) == (0, 0)


def test_bucket_start_normalises_to_utc():
    pkt_noon = datetime(2026, 8, 6, 12, 3, tzinfo=mod.PKT)
    assert mod.bucket_start(pkt_noon) == datetime(2026, 8, 6, 7, 0, tzinfo=UTC)


def test_bucket_start_treats_naive_as_utc():
    assert mod.bucket_start(datetime(2026, 8, 6, 9, 7)) == _at(9, 5)


def test_session_date_is_the_pkt_trading_day():
    # 04:30 UTC is 09:30 PKT — the PSX open. Same calendar day either way,
    # which is the point: a session never straddles UTC midnight.
    assert mod.session_date_for(_at(4, 30)).isoformat() == "2026-08-06"
    # 20:00 UTC is 01:00 PKT the NEXT day — outside a session, but the
    # conversion must still follow PKT rather than UTC.
    assert mod.session_date_for(_at(20, 0)).isoformat() == "2026-08-07"


# ---------- merge_sample ----------


def test_first_sample_of_a_bucket_opens_it_at_the_current_price():
    row = mod.merge_sample(None, symbol="TSBL", price=2.44, ts=_at(9, 7))
    assert (row["open"], row["high"], row["low"], row["close"]) == (2.44, 2.44, 2.44, 2.44)
    assert row["ts"].startswith("2026-08-06T09:05:00")
    assert row["session_date"] == "2026-08-06"


def test_first_sample_ignores_session_extremes():
    """A fresh bucket must not inherit the whole day's range.

    `day_high`/`day_low` are session-wide. Seeding a new bucket with them would
    draw a candle spanning the entire day at whatever minute it opened.
    """
    row = mod.merge_sample(
        None, symbol="TSBL", price=2.44, ts=_at(9, 7), day_high=2.53, day_low=2.37
    )
    assert (row["high"], row["low"]) == (2.44, 2.44)


def test_later_sample_widens_the_bucket_and_moves_close():
    existing = {"open": 2.44, "high": 2.46, "low": 2.43, "cum_volume": 1000}
    row = mod.merge_sample(existing, symbol="TSBL", price=2.50, ts=_at(9, 9))
    assert row["open"] == 2.44  # open is sticky
    assert row["high"] == 2.50
    assert row["low"] == 2.43
    assert row["close"] == 2.50


def test_later_sample_may_widen_toward_session_extremes():
    existing = {"open": 2.44, "high": 2.46, "low": 2.43, "cum_volume": 1000}
    row = mod.merge_sample(
        existing, symbol="TSBL", price=2.45, ts=_at(9, 9), day_high=2.53, day_low=2.37
    )
    assert (row["high"], row["low"]) == (2.53, 2.37)


def test_cumulative_volume_never_decreases():
    """A stale snapshot read must not make a later bucket look emptier.

    The reader diffs consecutive buckets; a decrease here would surface as a
    negative volume bar.
    """
    existing = {"open": 2.44, "high": 2.46, "low": 2.43, "cum_volume": 5000}
    row = mod.merge_sample(existing, symbol="TSBL", price=2.45, ts=_at(9, 9), volume=4200)
    assert row["cum_volume"] == 5000


def test_unparseable_stored_open_falls_back_to_price():
    """The column is NOT NULL — one bad field must not drop the whole bucket."""
    row = mod.merge_sample(
        {"open": None, "high": None, "low": None}, symbol="TSBL", price=2.45, ts=_at(9, 9)
    )
    assert row["open"] == 2.45


def test_samples_in_the_same_bucket_share_one_key():
    a = mod.merge_sample(None, symbol="TSBL", price=2.44, ts=_at(9, 5, 10))
    b = mod.merge_sample(None, symbol="TSBL", price=2.48, ts=_at(9, 9, 55))
    assert a["ts"] == b["ts"]


# ---------- to_bars: cumulative -> per-bar volume ----------


def _stored(ts: str, session: str, close: float, cum: int) -> dict:
    return {
        "ts": ts,
        "session_date": session,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "cum_volume": cum,
    }


def test_to_bars_diffs_cumulative_volume_within_a_session():
    rows = [
        _stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 1000),
        _stored("2026-08-06T09:10:00+00:00", "2026-08-06", 2.46, 2500),
        _stored("2026-08-06T09:15:00+00:00", "2026-08-06", 2.45, 2500),
    ]
    assert [b["volume"] for b in mod.to_bars(rows)] == [1000, 1500, 0]


def test_to_bars_restarts_the_diff_each_session():
    """Cumulative volume resets at every open — carrying it across sessions
    would emit one huge negative (clamped to 0) bar each morning."""
    rows = [
        _stored("2026-08-05T09:05:00+00:00", "2026-08-05", 2.40, 9000),
        _stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 1200),
        _stored("2026-08-06T09:10:00+00:00", "2026-08-06", 2.46, 1900),
    ]
    assert [b["volume"] for b in mod.to_bars(rows)] == [9000, 1200, 700]


def test_to_bars_clamps_a_negative_diff_to_zero():
    rows = [
        _stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 5000),
        _stored("2026-08-06T09:10:00+00:00", "2026-08-06", 2.46, 4000),
    ]
    assert [b["volume"] for b in mod.to_bars(rows)] == [5000, 0]


def test_to_bars_sorts_oldest_first_regardless_of_input_order():
    """The reader fetches newest-first (`order(ts, desc=True)`); charts draw
    oldest-first."""
    rows = [
        _stored("2026-08-06T09:15:00+00:00", "2026-08-06", 2.45, 3000),
        _stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 1000),
        _stored("2026-08-06T09:10:00+00:00", "2026-08-06", 2.46, 2000),
    ]
    bars = mod.to_bars(rows)
    assert [b["ts"] for b in bars] == sorted(b["ts"] for b in bars)
    assert [b["volume"] for b in bars] == [1000, 1000, 1000]


def test_to_bars_emits_parseable_utc_timestamps():
    """The frontend parses these with `new Date()`, which needs an offset."""
    rows = [_stored("2026-08-06T09:05:00", "2026-08-06", 2.44, 1000)]
    ts = mod.to_bars(rows)[0]["ts"]
    assert datetime.fromisoformat(ts).tzinfo is not None


def test_to_bars_accepts_datetime_timestamps():
    rows = [_stored(_at(9, 5), "2026-08-06", 2.44, 1000)]
    assert mod.to_bars(rows)[0]["ts"].startswith("2026-08-06T09:05:00")


def test_to_bars_drops_rows_without_a_timestamp():
    rows = [_stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 1000)]
    rows.append({**rows[0], "ts": None})
    assert len(mod.to_bars(rows)) == 1


# ---------- latest_sessions ----------


def test_latest_sessions_keeps_only_the_newest_days():
    bars = [
        {"session_date": "2026-08-04"},
        {"session_date": "2026-08-05"},
        {"session_date": "2026-08-06"},
        {"session_date": "2026-08-06"},
    ]
    assert [b["session_date"] for b in mod.latest_sessions(bars, 1)] == ["2026-08-06"] * 2
    assert len(mod.latest_sessions(bars, 2)) == 3


# ---------- read path ----------


async def test_intraday_returns_empty_when_the_table_is_missing(monkeypatch):
    """A deploy where the migration has not landed must degrade to "no intraday
    data" so the chart falls back to daily bars, not 500."""
    monkeypatch.setattr(mod.mem_cache, "get_or_load", lambda _k, _t, load: load())

    async def _boom(_fn):
        raise RuntimeError('relation "psx_intraday" does not exist')

    monkeypatch.setattr(mod, "async_execute", _boom)
    assert await mod.intraday("TSBL") == []


async def test_intraday_returns_one_session_oldest_first(monkeypatch):
    monkeypatch.setattr(mod.mem_cache, "get_or_load", lambda _k, _t, load: load())
    stored = [
        _stored("2026-08-05T09:05:00+00:00", "2026-08-05", 2.40, 9000),
        _stored("2026-08-06T09:10:00+00:00", "2026-08-06", 2.46, 1900),
        _stored("2026-08-06T09:05:00+00:00", "2026-08-06", 2.44, 1200),
    ]

    async def _rows(_fn):
        class _Res:
            data = stored

        return _Res()

    monkeypatch.setattr(mod, "async_execute", _rows)
    bars = await mod.intraday("tsbl", sessions=1)
    assert [b["session_date"] for b in bars] == ["2026-08-06", "2026-08-06"]
    assert [b["volume"] for b in bars] == [1200, 700]


async def test_capture_skips_symbols_without_a_usable_price(monkeypatch):
    from types import SimpleNamespace

    async def _snapshot():
        return [
            SimpleNamespace(symbol="TSBL", price=2.44, day_high=2.53, day_low=2.37, volume=1000),
            SimpleNamespace(symbol="DEAD", price=None, day_high=None, day_low=None, volume=0),
            SimpleNamespace(symbol="ZERO", price=0, day_high=None, day_low=None, volume=0),
        ]

    monkeypatch.setattr(
        mod, "get_cache", lambda: SimpleNamespace(get_market_snapshot=_snapshot)
    )

    async def _no_existing(_bucket):
        return {}

    monkeypatch.setattr(mod, "_rows_at_bucket", _no_existing)

    written: list[list[dict]] = []

    async def _capture(fn):
        class _Table:
            def upsert(self, rows, on_conflict=None):
                written.append(rows)
                return self

        class _Client:
            def table(self, _name):
                return _Table()

        return fn(_Client())

    monkeypatch.setattr(mod, "async_execute", _capture)
    count = await mod.capture_snapshot(now=_at(9, 7))
    assert count == 1
    assert [r["symbol"] for r in written[0]] == ["TSBL"]


async def test_capture_writes_nothing_when_the_snapshot_is_empty(monkeypatch):
    from types import SimpleNamespace

    async def _snapshot():
        return []

    monkeypatch.setattr(
        mod, "get_cache", lambda: SimpleNamespace(get_market_snapshot=_snapshot)
    )

    async def _never(_fn):
        raise AssertionError("must not touch the database with nothing to write")

    monkeypatch.setattr(mod, "async_execute", _never)
    assert await mod.capture_snapshot(now=_at(9, 7)) == 0


async def test_prune_cuts_at_the_retention_boundary(monkeypatch):
    seen: dict[str, str] = {}

    async def _delete(fn):
        class _Q:
            def lt(self, column, value):
                seen[column] = value
                return self

        class _Table:
            def delete(self):
                return _Q()

        class _Client:
            def table(self, _name):
                return _Table()

        return fn(_Client())

    monkeypatch.setattr(mod, "async_execute", _delete)
    await mod.prune(retention_days=10)
    cutoff = datetime.fromisoformat(seen["session_date"]).date()
    assert cutoff == (datetime.now(mod.PKT).date() - timedelta(days=10))
