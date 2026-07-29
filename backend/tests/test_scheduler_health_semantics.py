"""What a job reports as "healthy" must match what it actually did.

Audit 2026-07-29 found the health table lying in both directions:

* `refresh_dividends` demanded 0 failures out of a 1077-symbol crawl, so the
  ~66 symbols with no DPS payout page turned every run red. `last_success` had
  not advanced in 8 days while the job wrote 421 rows nightly.
* `sbp_macro` collapsed four independently-failing feeds into one boolean, so a
  dead FX parser masked the fact that KIBOR, PKRV and the policy rate were fine.
* `job_check_alerts` — an entire product pillar — recorded nothing at all, so a
  permanently-throwing evaluator was indistinguishable from a quiet market.

These lock in the corrected semantics.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.jobs import scheduler as sched


@pytest.fixture
def health(recorded_health):
    """The autouse recorder from conftest, indexed by source name."""

    def _by_source(source):
        return [c for c in recorded_health if c["source"] == source]

    _by_source.calls = recorded_health
    return _by_source


# ---------- dividends: tolerate a small failure ratio ----------


def _patch_dividends(monkeypatch, symbols, failing):
    """Run job_refresh_dividends over `symbols`, failing the ones in `failing`.

    Symbols that succeed return one payout each, so the run writes real rows —
    otherwise the zero-rows guard, not the failure ratio, would decide the
    outcome and the ratio logic would go untested.
    """

    async def _get_all_symbols():
        return symbols

    class _DPS:
        async def fetch_payouts(self, sym):
            if sym in failing:
                raise RuntimeError("DPS 404")
            return [
                SimpleNamespace(
                    announcement_id=f"{sym}-1",
                    symbol=sym,
                    ex_date=date(2026, 7, 29),
                    announcement_date=date(2026, 7, 20),
                    payout_type="CASH",
                    per_share=2.5,
                    bonus_pct=None,
                )
            ]

    async def _noop_execute(_builder):
        return None

    monkeypatch.setattr(sched, "_get_all_symbols", _get_all_symbols)
    monkeypatch.setattr(sched, "dps", _DPS())
    monkeypatch.setattr(sched, "async_execute", _noop_execute)

    # The retry loop sleeps 5s between passes; nothing here needs real time.
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(sched.asyncio, "sleep", _no_sleep)


@pytest.mark.asyncio
async def test_dividends_tolerates_the_known_dead_symbols(monkeypatch, health):
    """66/1077 (~6%) is the observed steady state and must NOT read as failure."""
    symbols = [f"SYM{i}" for i in range(1077)]
    _patch_dividends(monkeypatch, symbols, set(symbols[:66]))

    await sched.job_refresh_dividends()

    (call,) = health("refresh_dividends")
    assert call["success"] is True, (
        "66/1077 failures with 1011 rows written is a healthy run — the old "
        "errors == 0 rule marked this red for 8 days straight"
    )
    assert call["error"] is None
    assert call["rows_updated"] == 1011


@pytest.mark.asyncio
async def test_dividends_reports_degraded_past_the_tolerance(monkeypatch, health):
    """Half the market failing is a real regression and must go red."""
    symbols = [f"SYM{i}" for i in range(100)]
    _patch_dividends(monkeypatch, symbols, set(symbols[:50]))

    await sched.job_refresh_dividends()

    (call,) = health("refresh_dividends")
    assert call["success"] is False
    assert "50/100 symbols failed" in call["error"]


def test_dividends_tolerance_covers_the_observed_failure_rate():
    """Guard the constant itself: 66/1077 must sit inside the tolerance."""
    assert 66 / 1077 < sched.DIVIDENDS_MAX_FAILURE_RATIO


# ---------- SBP: one health row per feed ----------


@pytest.mark.asyncio
async def test_sbp_records_each_feed_separately(monkeypatch, health):
    """A dead FX feed must not drag KIBOR/PKRV/policy-rate down with it."""

    class _SBP:
        async def fetch_kibor(self):
            return [{"series": "KIBOR_3M", "date": "2026-07-29", "value": 11.0}]

        async def fetch_pkrv(self):
            return [{"series": "PKRV_1Y", "date": "2026-07-29", "value": 11.2}]

        async def fetch_fx_rates(self):
            return []  # the real-world breakage

        async def fetch_policy_rate(self):
            return {"series": "POLICY_RATE", "date": "2026-07-29", "value": 11.5}

    async def _noop_execute(_builder):
        return None

    async def _no_fx():
        return []  # both SBP and the fallback dry — the worst case

    monkeypatch.setattr(sched, "sbp", _SBP())
    monkeypatch.setattr(sched, "async_execute", _noop_execute)
    monkeypatch.setattr(sched, "_fetch_fx_rows", _no_fx)

    await sched.job_refresh_sbp()

    assert health("sbp_kibor")[0]["success"] is True
    assert health("sbp_pkrv")[0]["success"] is True
    assert health("sbp_policy_rate")[0]["success"] is True

    fx = health("sbp_fx")[0]
    assert fx["success"] is False, "the one genuinely dead feed must be visible"
    assert "format" in fx["error"]


# ---------- FX: fall back when SBP's page is dead ----------


@pytest.mark.asyncio
async def test_fx_falls_back_to_the_monetary_provider(monkeypatch):
    """SBP retired the FX page, so macro_rates held no FX series at all."""

    class _DeadSBP:
        async def fetch_fx_rates(self):
            return []  # the 202KB site shell parses to nothing

    async def _snapshot():
        return {
            "currencies": [
                {"code": "USD", "one_unit_in_pkr": 277.875},
                {"code": "EUR", "one_unit_in_pkr": 316.3681449},
                {"code": "GBP", "one_unit_in_pkr": 369.2656679},
                {"code": "JPY", "one_unit_in_pkr": 1.695},  # not exposed by /macro/fx
            ]
        }

    monkeypatch.setattr(sched, "sbp", _DeadSBP())
    monkeypatch.setattr("app.services.macro.monetary.get_monetary_snapshot", _snapshot)

    rows = await sched._fetch_fx_rows()

    series = {r["series"]: r["value"] for r in rows}
    assert series["FX_USD_BUY"] == 277.875
    assert series["FX_USD_SELL"] == 277.875, "no bid/ask available — no invented spread"
    assert series["FX_EUR_BUY"] == 316.3681
    assert series["FX_GBP_BUY"] == 369.2657
    assert not any(s.startswith("FX_JPY") for s in series), "only USD/EUR/GBP are exposed"


@pytest.mark.asyncio
async def test_fx_prefers_sbp_when_it_works(monkeypatch):
    """If SBP restores the page, the authoritative source wins again."""
    sbp_rows = [{"series": "FX_USD_BUY", "date": "2026-07-29", "value": 277.5}]

    class _LiveSBP:
        async def fetch_fx_rates(self):
            return sbp_rows

    async def _explode():
        raise AssertionError("fallback used while SBP was healthy")

    monkeypatch.setattr(sched, "sbp", _LiveSBP())
    monkeypatch.setattr("app.services.macro.monetary.get_monetary_snapshot", _explode)

    assert await sched._fetch_fx_rows() == sbp_rows


# ---------- alerts: the pillar that reported nothing ----------


@pytest.mark.asyncio
async def test_alerts_evaluator_records_a_quiet_tick_as_healthy(monkeypatch, health):
    async def _evaluate_all():
        return {"price": 0, "bill": 0, "budget": 0, "goal": 0}

    monkeypatch.setattr("app.services.alerts.evaluate_all", _evaluate_all)

    await sched.job_check_alerts()

    (call,) = health("alerts_evaluator")
    assert call["success"] is True, "nothing crossing a threshold is not a failure"
    assert call["allow_zero_rows"] is True


@pytest.mark.asyncio
async def test_alerts_evaluator_surfaces_a_throwing_evaluator(monkeypatch, health):
    """The regression that was previously invisible: it only hit a log line."""

    async def _evaluate_all():
        raise RuntimeError("evaluator exploded")

    monkeypatch.setattr("app.services.alerts.evaluate_all", _evaluate_all)

    await sched.job_check_alerts()  # must still not raise into APScheduler

    (call,) = health("alerts_evaluator")
    assert call["success"] is False
    assert "evaluator exploded" in call["error"]


# ---------- MUFAP: "blocked" and "format changed" are different problems ----------


@pytest.mark.asyncio
async def test_mufap_reports_bot_protection_distinctly(monkeypatch, health):
    """The health row said "page format changed" for 8 days. It was a 403."""
    from app.scrapers.mufap import BotChallengeError

    class _BlockedMUFAP:
        async def fetch_funds(self):
            raise BotChallengeError("mufap.com.pk served a bot-protection challenge (HTTP 403)")

    monkeypatch.setattr(sched, "mufap", _BlockedMUFAP())

    await sched.job_refresh_mufap()  # must not escape into APScheduler

    (call,) = health("mufap_nav")
    assert call["success"] is False
    assert "bot-protection" in call["error"], (
        "an operator reading this must learn we are BLOCKED, not that a parser broke"
    )


# ---------- fundamentals: never fabricate a number ----------


def test_bounded_label_scan_rejects_absent_values():
    """The unbounded regex invented a P/E for 51% of the market.

    `[^0-9-]*` between the label and the number let the scan run arbitrarily far
    past a blank field and return the next unrelated digit on the page. Bounding
    the gap is what turns "absent" back into None instead of a fabricated 1.00.
    """
    import re

    # The field is BLANK, not "-": the character class already stops at a dash,
    # so an empty cell is the case that actually leaked. Here the next digit on
    # the page belongs to "Free Float", 40-odd characters downstream.
    text = "P/E Ratio (TTM) Sector Oil & Gas Exploration Free Float 1 Listed 4300928400"

    unbounded = re.search(r"P/E\s*Ratio\s*\(TTM\)[^0-9\-]*(-?\d+(?:\.\d+)?)", text, re.I)
    assert unbounded is not None and unbounded.group(1) == "1", (
        "reproduces the original bug: it scans past the blank and grabs the 1 "
        "that belongs to Book Value"
    )

    bounded = re.search(r"P/E\s*Ratio\s*\(TTM\)[^0-9\-]{0,12}(-?\d+(?:\.\d+)?)", text, re.I)
    assert bounded is None, "a blank P/E must yield nothing, not the next stray digit"
