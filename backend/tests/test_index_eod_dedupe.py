"""job_refresh_index_eod must not send duplicate (code, date) rows in one upsert.

Same bug class as ``test_dividends_dedupe`` (fixed 2026-07-16), left unfixed on
the index path. Observed in production (Railway, 2026-07-29):

    postgrest.exceptions.APIError: {'message': 'ON CONFLICT DO UPDATE command
    cannot affect row a second time', 'code': '21000', 'hint': 'Ensure that no
    rows proposed for insertion within the same command have duplicate
    constrained values.'}

DPS's ``/timeseries/eod/{code}`` returns an exact duplicate bar for 2024-01-22
(and 2021-10-29 for BKTI/OGTI) in 15 of the 18 indices. Postgres rejects the
ENTIRE 1240-row batch when two proposed rows share the ON CONFLICT target, so
one duplicated day loses the whole index's history — not just the dupe. Only
KSE100PR, HBLTTI and MII30 are duplicate-free, and they are precisely the three
codes that kept ingesting (1239 + 917 + 588 = 2744 rows, the exact
``rows_updated`` the job last reported as a success).

The second test pins the reporting half: the job swallowed each per-code failure
with a ``log.warning`` and still recorded ``success=True``, so monitoring stayed
green while ALLSHR sat three weeks stale.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.jobs import scheduler as sched
from app.models import IndexBar


def _bar(code: str, day: date, close: float = 100.0):
    return IndexBar(
        code=code,
        date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


def _drive(monkeypatch, bars_by_code: dict[str, list], *, fail_codes=()):
    """Run job_refresh_index_eod against fakes.

    Returns ``(upserted_batches, health_calls)``.
    """
    upserted: list[list[dict]] = []
    health: list[dict] = []

    async def _fake_fetch(code: str):
        if code in fail_codes:
            raise RuntimeError(f"boom for {code}")
        return bars_by_code.get(code, [])

    async def _fake_async_execute(builder):
        class _Tbl:
            def upsert(self, rows, **_kw):
                upserted.append(rows)
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(data=[])

    async def _fake_health(source, success, rows_updated=0, error=None, **_k):
        health.append(
            {"source": source, "success": success, "rows_updated": rows_updated,
             "error": error}
        )

    monkeypatch.setattr(sched, "ALL_PSX_INDICES", tuple(bars_by_code))
    monkeypatch.setattr(sched.dps, "fetch_index_eod", _fake_fetch)
    monkeypatch.setattr(sched, "async_execute", _fake_async_execute)
    monkeypatch.setattr(sched, "_record_health", _fake_health)
    return upserted, health


@pytest.mark.asyncio
async def test_duplicate_code_date_bars_are_collapsed(monkeypatch):
    """Two bars sharing (code, date) must upsert as ONE row.

    This is the exact shape that produced 21000 in production.
    """
    dup_day = date(2024, 1, 22)
    upserted, _ = _drive(
        monkeypatch,
        {
            "ALLSHR": [
                _bar("ALLSHR", date(2026, 7, 28), 107472.26),
                _bar("ALLSHR", dup_day, 43217.9),
                _bar("ALLSHR", dup_day, 43217.9),
            ]
        },
    )

    await sched.job_refresh_index_eod()

    assert upserted, "job upserted nothing"
    rows = upserted[0]
    keys = [(r["code"], r["date"]) for r in rows]
    assert len(keys) == len(set(keys)), f"duplicate conflict targets in one batch: {keys}"
    assert sorted(keys) == [("ALLSHR", "2024-01-22"), ("ALLSHR", "2026-07-28")]


@pytest.mark.asyncio
async def test_distinct_bars_all_survive(monkeypatch):
    """Dedupe must not drop genuinely distinct trading days."""
    upserted, _ = _drive(
        monkeypatch,
        {
            "KSE100": [
                _bar("KSE100", date(2026, 7, 24)),
                _bar("KSE100", date(2026, 7, 27)),
                _bar("KSE100", date(2026, 7, 28)),
            ]
        },
    )

    await sched.job_refresh_index_eod()

    assert sorted(r["date"] for r in upserted[0]) == [
        "2026-07-24",
        "2026-07-27",
        "2026-07-28",
    ]


@pytest.mark.asyncio
async def test_per_code_failure_is_reported_as_unhealthy(monkeypatch):
    """A code that fails must not be reported as a green run.

    The old job counted only successful bars into ``rows_updated`` and always
    passed ``success=True``, so 15 broken indices looked identical to a clean
    night.
    """
    _, health = _drive(
        monkeypatch,
        {
            "KSE100": [_bar("KSE100", date(2026, 7, 28))],
            "ALLSHR": [_bar("ALLSHR", date(2026, 7, 28))],
        },
        fail_codes=("ALLSHR",),
    )

    await sched.job_refresh_index_eod()

    assert health, "job recorded no health row"
    assert health[-1]["success"] is False, "partial failure reported as success"
    assert "ALLSHR" in (health[-1]["error"] or "")


@pytest.mark.asyncio
async def test_transient_failure_is_retried_within_the_run(monkeypatch):
    """A code that fails once must be retried, not left stale for 24 hours.

    The job ran once daily with no retry, so a single transient DPS error meant
    a full day of staleness — and a repeat the next night meant indefinite.
    """
    calls: list[str] = []

    async def _flaky_fetch(code: str):
        calls.append(code)
        if code == "ALLSHR" and calls.count("ALLSHR") == 1:
            raise RuntimeError("transient DPS error")
        return [_bar(code, date(2026, 7, 28))]

    upserted, health = _drive(
        monkeypatch, {"KSE100": [], "ALLSHR": []}
    )
    monkeypatch.setattr(sched.dps, "fetch_index_eod", _flaky_fetch)

    await sched.job_refresh_index_eod(attempts=3, backoff_seconds=0)

    assert calls.count("ALLSHR") == 2, "failed code was not retried"
    assert calls.count("KSE100") == 1, "succeeded code must not be re-fetched"
    assert health[-1]["success"] is True, "retry recovered it; run should be green"


@pytest.mark.asyncio
async def test_permanent_failure_still_reports_unhealthy(monkeypatch):
    """Retries must not paper over a code that is genuinely broken."""
    _, health = _drive(
        monkeypatch,
        {"KSE100": [_bar("KSE100", date(2026, 7, 28))], "ALLSHR": []},
        fail_codes=("ALLSHR",),
    )

    await sched.job_refresh_index_eod(attempts=2, backoff_seconds=0)

    assert health[-1]["success"] is False
    assert "ALLSHR" in health[-1]["error"]


@pytest.mark.asyncio
async def test_all_codes_succeeding_is_reported_healthy(monkeypatch):
    """The happy path must still report green."""
    _, health = _drive(
        monkeypatch,
        {
            "KSE100": [_bar("KSE100", date(2026, 7, 28))],
            "ALLSHR": [_bar("ALLSHR", date(2026, 7, 28))],
        },
    )

    await sched.job_refresh_index_eod()

    assert health[-1]["success"] is True
    assert health[-1]["rows_updated"] == 2
