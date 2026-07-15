"""generate_report has a total wall-clock deadline (C3).

`ai_tutor_request_timeout_s` (30s) bounds ONE HTTP request, not the pipeline.
Instructor is configured `max_retries=2` (2 attempts) and those attempts are
applied afresh per API key, and the engine calls `generate_structured` twice
(generate + regenerate-exactly-once). So the floor for a single key is
2 x 2 x 30s ~= 120s, and a K-key pool that 429s slowly multiplies it again
(K=3 -> ~360s). The strip/re-verify path is local CPU and adds nothing; SDK
retries are off (`max_retries=0`).

Nothing bounded that total, so a caller could hold a request open far past any
sane budget. `asyncio.timeout(settings.ai_report_deadline_s)` now does, and it
sits INSIDE the existing `try` so the `finally` still returns the httpx pool —
a deadline that leaked a connection pool on every fire would trade one
resource bug for a worse one.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.reports import Citation, MarketBriefReport
from app.services.ai import engine
from app.services.ai.specs import ReportSpec

BUNDLE = {
    "as_of": "2026-07-14",
    "indices": {"kse100": {"close": 100000.0, "change_pct": 1.5}},
}


async def _fake_ctx(conn_or_session=None, *, subject=None, days=None, user_id=None):
    return BUNDLE


def _spec() -> ReportSpec:
    return ReportSpec(
        report_type="market_brief",
        schema=MarketBriefReport,
        prompt_template=(
            "lang={lang}\nBUNDLE=<<<{bundle_json}>>>\nUNTRUSTED=<<<{untrusted_data}>>>"
        ),
        confidential=False,
        guardrail_profile="test",
        context_builder=_fake_ctx,
    )


def _clean_report() -> MarketBriefReport:
    return MarketBriefReport(
        headline="Daily market update",
        observations=["The KSE100 closed at 100000 today."],
        considerations=[],
        disclaimer="Educational information only. Not financial advice.",
        citations=[
            Citation(value=100000.0, source_key="indices.kse100.close", as_of="2026-07-14")
        ],
    )


def _install(monkeypatch, generate, *, deadline_s):
    """Wire the engine to fakes; return the list of closed clients."""
    closed: list[object] = []
    client = SimpleNamespace(client=object(), model="fake-model", provider="fake-provider")

    async def _fake_close(c):
        closed.append(c)

    monkeypatch.setattr(engine, "generate_structured", generate)
    monkeypatch.setattr(engine, "make_report_client", lambda *, confidential, transport=None: client)
    monkeypatch.setattr(engine, "aclose_report_client", _fake_close)
    monkeypatch.setattr(engine, "log_report_generation", lambda **_kw: None)
    monkeypatch.setattr(engine.settings, "ai_report_deadline_s", deadline_s)
    return closed


@pytest.mark.asyncio
async def test_a_slow_provider_raises_report_unavailable_instead_of_hanging(monkeypatch):
    async def _never_returns(*_a, **_kw):
        await asyncio.sleep(30)
        raise AssertionError("the deadline did not fire")

    closed = _install(monkeypatch, _never_returns, deadline_s=0.05)

    with pytest.raises(engine.ReportUnavailable):
        await engine.generate_report(_spec(), lang="en")

    assert closed, "the deadline fired but the httpx pool was never released"


@pytest.mark.asyncio
async def test_the_deadline_fires_at_the_configured_budget(monkeypatch):
    """Not merely 'eventually' — the caller is released on the budget."""
    async def _never_returns(*_a, **_kw):
        await asyncio.sleep(30)

    _install(monkeypatch, _never_returns, deadline_s=0.1)

    started = asyncio.get_running_loop().time()
    with pytest.raises(engine.ReportUnavailable):
        await engine.generate_report(_spec(), lang="en")
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 5.0, f"waited {elapsed:.1f}s on a 0.1s deadline"


@pytest.mark.asyncio
async def test_the_deadline_also_bounds_the_regeneration_call(monkeypatch):
    """The budget is TOTAL. A first call that returns just under it must not
    buy the retry a fresh one — that is the 2x in the 120s worst case."""
    calls = {"n": 0}

    async def _slow(*_a, **_kw):
        calls["n"] += 1
        await asyncio.sleep(0.08)
        # Orphan number ("42") -> verification fails -> engine regenerates once.
        return MarketBriefReport(
            headline="Daily market update",
            observations=["The index jumped 42 points to 100000 today."],
            considerations=[],
            disclaimer="Educational information only. Not financial advice.",
            citations=[
                Citation(value=100000.0, source_key="indices.kse100.close", as_of="2026-07-14")
            ],
        )

    _install(monkeypatch, _slow, deadline_s=0.12)

    with pytest.raises(engine.ReportUnavailable):
        await engine.generate_report(_spec(), lang="en")

    assert calls["n"] == 2, "the deadline should fire during the regeneration, not before it"


@pytest.mark.asyncio
async def test_a_generous_deadline_does_not_disturb_the_happy_path(monkeypatch):
    """The guard must be invisible to a report that finishes in time."""
    async def _fast(*_a, **_kw):
        return _clean_report()

    closed = _install(monkeypatch, _fast, deadline_s=30.0)

    gen = await engine.generate_report(_spec(), lang="en")

    assert gen.verification.verified
    assert gen.provider == "fake-provider"
    assert closed, "the happy path must still release the pool"


def test_the_default_deadline_is_below_the_unbounded_worst_case():
    """120s is the single-key worst case (2 attempts x 2 calls x 30s); the
    default must sit under it or the guard changes nothing."""
    from app.config import settings

    assert settings.ai_report_deadline_s == 90.0
    assert settings.ai_report_deadline_s < 2 * 2 * settings.ai_tutor_request_timeout_s
