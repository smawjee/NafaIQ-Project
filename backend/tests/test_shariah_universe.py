"""psx_profile.is_shariah comes from the live KMI All-Share index, safely.

The flag used to be derived from a hardcoded 124-symbol set in config, which
flagged conventional interest-based banks (HBL, UBL, NBP, SCBPL, BAFL, BAHL)
as Shariah-compliant and even listed PSX, the exchange itself, as a stock.
Measured against the live index: 66 overlap, 58 false positives, 244 false
negatives. job_refresh_shariah replaces it with KMIALLSHR, PSX's own
Shariah-screened index.

The dangerous part is not the scrape, it is the write. `is_shariah` is
NOT NULL DEFAULT false and this job writes `false` for every non-member, so a
failed or partial scrape that returned few or zero members would mark THE
ENTIRE MARKET non-Shariah — silently, and strictly worse than the wrong data
it replaced. A per-field `if value:` guard cannot catch that, because `false`
IS the value being written. Hence the size gate, pinned below.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.jobs import scheduler as sched
from app.scrapers.dps import DPSScraper

FIXTURE = Path(__file__).parent / "fixtures" / "dps_kmiallshr.html"


# --------------------------------------------------------------------------- #
# parsing                                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fetch_index_constituents_extracts_symbols(monkeypatch):
    """Symbols come out of a.tbl__symbol, in page order."""
    dps = DPSScraper()
    requested: list[str] = []

    async def _fake_get(path: str) -> str:
        requested.append(path)
        return FIXTURE.read_text(encoding="utf-8")

    monkeypatch.setattr(dps, "_get", _fake_get)

    symbols = await dps.fetch_index_constituents("kmiallshr")

    assert symbols == ["AIRLINK", "ENGRO", "LUCK", "MEBL", "OGDC"]
    assert requested == ["/indices/KMIALLSHR"], "code must be upper-cased into the path"


@pytest.mark.asyncio
async def test_fetch_index_constituents_reads_past_the_client_side_page_length(monkeypatch):
    """data-page-length="25" is DataTables client-side paging.

    Every constituent is in the served HTML, so the parser must never treat
    that attribute as a limit. The fixture's row count is what comes back.
    """
    dps = DPSScraper()
    html = FIXTURE.read_text(encoding="utf-8")
    assert 'data-page-length="25"' in html, "fixture no longer pins the paging attribute"

    monkeypatch.setattr(dps, "_get", lambda _p: _async(html))

    assert len(await dps.fetch_index_constituents("KMIALLSHR")) == html.count("tbl__symbol")


@pytest.mark.asyncio
async def test_fetch_index_constituents_is_empty_when_the_page_has_no_table(monkeypatch):
    """A blocked/error page yields [] — the caller's size gate then aborts."""
    dps = DPSScraper()
    monkeypatch.setattr(dps, "_get", lambda _p: _async("<html><body>403</body></html>"))

    assert await dps.fetch_index_constituents("KMIALLSHR") == []


async def _async(value):
    return value


# --------------------------------------------------------------------------- #
# the job                                                                     #
# --------------------------------------------------------------------------- #


def _drive_shariah_job(monkeypatch, *, members, symbols):
    """Run job_refresh_shariah against fakes; return (upserted_rows, health)."""
    upserted: list[list[dict]] = []
    health: list[dict] = []

    async def _fake_constituents(code: str):
        return members

    async def _fake_symbols():
        return symbols

    async def _fake_async_execute(builder):
        class _Tbl:
            def upsert(self, rows, **_kw):
                upserted.append(rows)
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(data=[])

    async def _fake_health(source, success, rows_updated=0, error=None):
        health.append(
            {"source": source, "success": success, "rows_updated": rows_updated, "error": error}
        )

    monkeypatch.setattr(sched.dps, "fetch_index_constituents", _fake_constituents)
    monkeypatch.setattr(sched, "_get_all_symbols", _fake_symbols)
    monkeypatch.setattr(sched, "async_execute", _fake_async_execute)
    monkeypatch.setattr(sched, "_record_health", _fake_health)

    return upserted, health


def _index(n: int) -> list[str]:
    return [f"KMI{i:04d}" for i in range(n)]


@pytest.mark.asyncio
@pytest.mark.parametrize("member_count", [0, 1, 66, 199])
async def test_a_short_constituent_set_writes_nothing(monkeypatch, member_count):
    """THE test that matters: the gate must abort BEFORE any write.

    Zero members is the scrape-failed case; 199 is a partial parse. Either one,
    written through, sets is_shariah=false market-wide.
    """
    upserted, health = _drive_shariah_job(
        monkeypatch,
        members=_index(member_count),
        symbols=["MEBL", "HBL", "LUCK"],
    )

    await sched.job_refresh_shariah()

    assert not upserted, "a partial constituent set was written to psx_profile"
    assert health and health[-1]["success"] is False, "a failed scrape reported healthy"
    assert str(member_count) in (health[-1]["error"] or ""), "the error must name the size"


@pytest.mark.asyncio
async def test_a_full_constituent_set_passes_the_gate(monkeypatch):
    """The gate must not be so tight it rejects the real index (~310)."""
    upserted, health = _drive_shariah_job(
        monkeypatch, members=_index(310), symbols=["KMI0000"]
    )

    await sched.job_refresh_shariah()

    assert upserted, "the gate rejected a full-size index"
    assert health[-1]["success"] is True


@pytest.mark.asyncio
async def test_membership_is_written_for_members_and_non_members(monkeypatch):
    """Happy path: true for members, false for everyone else in psx_profile."""
    members = _index(300) + ["MEBL", "LUCK"]
    upserted, health = _drive_shariah_job(
        monkeypatch,
        # HBL/UBL/NBP are conventional interest-based banks the old hardcoded
        # set marked compliant; PSX is the exchange, not a stock.
        symbols=["MEBL", "LUCK", "HBL", "UBL", "NBP", "PSX"],
        members=members,
    )

    await sched.job_refresh_shariah()

    assert len(upserted) == 1, "the whole universe must go in one upsert"
    by_sym = {r["symbol"]: r["is_shariah"] for r in upserted[0]}
    assert by_sym == {
        "MEBL": True,
        "LUCK": True,
        "HBL": False,
        "UBL": False,
        "NBP": False,
        "PSX": False,
    }
    assert health[-1]["success"] is True
    assert health[-1]["source"] == "shariah_universe"


@pytest.mark.asyncio
async def test_an_empty_profile_universe_writes_nothing(monkeypatch):
    """No symbols means the read failed — not that the market is empty."""
    upserted, health = _drive_shariah_job(monkeypatch, members=_index(310), symbols=[])

    await sched.job_refresh_shariah()

    assert not upserted
    assert health[-1]["success"] is False


@pytest.mark.asyncio
async def test_a_scrape_exception_is_recorded_and_never_escapes(monkeypatch):
    """APScheduler must not see the raise, and nothing may be written."""
    upserted, health = _drive_shariah_job(monkeypatch, members=[], symbols=["MEBL"])

    async def _boom(_code):
        raise RuntimeError("dps 503")

    monkeypatch.setattr(sched.dps, "fetch_index_constituents", _boom)

    await sched.job_refresh_shariah()

    assert not upserted
    assert health[-1]["success"] is False
    assert "dps 503" in (health[-1]["error"] or "")


# --------------------------------------------------------------------------- #
# the 5-minute job must no longer touch the column                            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tv_job_does_not_write_is_shariah(monkeypatch):
    """is_shariah has a single owner. The TV job ran every 5 minutes and
    derived the flag from a hardcoded config set; membership does not change
    intraday and that set no longer exists."""
    upserted: list[list[dict]] = []

    async def _fake_select_all(_table, _cols, **_kw):
        return [{"symbol": "HBL", "sector": "COMMERCIAL BANKS"}]

    async def _fake_fetch():
        return [{"symbol": "HBL", "name": "Habib Bank", "sector": "Finance"}]

    async def _fake_async_execute(builder):
        class _Tbl:
            def upsert(self, rows, **_kw):
                upserted.append(rows)
                return self

        builder(SimpleNamespace(table=lambda _n: _Tbl()))
        return SimpleNamespace(data=[])

    async def _fake_health(*_a, **_kw):
        return None

    monkeypatch.setattr(sched, "select_all", _fake_select_all)
    monkeypatch.setattr(sched.tv, "fetch_market_data", _fake_fetch)
    monkeypatch.setattr(sched, "async_execute", _fake_async_execute)
    monkeypatch.setattr(sched, "_record_health", _fake_health)

    await sched.job_refresh_tv_data()

    assert upserted, "job wrote nothing"
    assert "is_shariah" not in upserted[0][0]


def test_the_hardcoded_shariah_set_is_gone():
    """Deleting the constant is the point: it was the false-positive source."""
    from app.config import settings

    assert not hasattr(settings, "SHARIAH_STOCKS")


def test_the_shariah_job_is_registered_daily():
    """Registration is load-bearing — an unregistered job never runs."""
    import inspect

    src = inspect.getsource(sched.init_scheduler)
    assert 'id="refresh_shariah"' in src
    assert "job_refresh_shariah" in src
