"""Scheduler tests for the daily shared Market Brief job (§11).

The engine + reports_repo are monkeypatched and the DB `begin()` context
manager is stubbed, so this exercises the 9th scheduler job WITHOUT hitting a
live provider or the live `ai_reports` table. Mirrors the mocking approach in
tests/test_reports_api.py.
"""
from __future__ import annotations

import contextlib
from datetime import date, datetime

from apscheduler.triggers.cron import CronTrigger

from app.jobs import scheduler as sched
from app.schemas.reports import Citation, MarketBriefReport, VerificationResult
from app.services.ai.engine import GeneratedReport, ReportUnavailable
from app.services.ai.providers import ProviderError


@contextlib.asynccontextmanager
async def _fake_cm():
    yield object()


def _gen_result(provider="gemini", model="flash") -> GeneratedReport:
    report = MarketBriefReport(
        headline="Market brief",
        observations=["The KSE100 closed at 100000."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[
            Citation(value=100000.0, source_key="indices.kse100.close", as_of="2026-07-14")
        ],
    )
    return GeneratedReport(
        report=report,
        verification=VerificationResult(verified=True, mismatches=[]),
        provider=provider,
        model=model,
        bundle={"indices": {"kse100": {"close": 100000.0}}},
    )


def _patch_engine(monkeypatch, result_or_exc):
    async def _fake_generate(spec, **kw):
        _fake_generate.spec = spec
        _fake_generate.kwargs = kw
        if isinstance(result_or_exc, Exception):
            raise result_or_exc
        return result_or_exc

    _fake_generate.spec = None
    _fake_generate.kwargs = None
    monkeypatch.setattr(sched.engine, "generate_report", _fake_generate)
    monkeypatch.setattr(sched, "begin", _fake_cm)
    return _fake_generate


# --------------------------------------------------------------------------- #
# the job generates the shared brief and persists via get_or_create_shared    #
# --------------------------------------------------------------------------- #
async def test_job_generates_and_persists_shared_brief(monkeypatch):
    fake_generate = _patch_engine(monkeypatch, _gen_result())

    saved = {}

    async def _fake_get_or_create_shared(conn, **kw):
        saved.update(kw)
        return {"id": "abc", "created_at": "2026-07-14"}

    monkeypatch.setattr(
        sched.reports_repo, "get_or_create_shared", _fake_get_or_create_shared
    )

    await sched.job_generate_market_brief()

    # generated the market_brief spec, no user (shared)
    assert fake_generate.spec is sched.REPORT_SPECS["market_brief"]
    assert fake_generate.spec.report_type == "market_brief"
    assert fake_generate.kwargs.get("user_id") is None

    # persisted via the shared get-or-create with the expected fields
    assert saved["report_type"] == "market_brief"
    assert saved["subject"] is None
    assert saved["content"] == _gen_result().report.model_dump()
    assert saved["verified"] is True
    assert saved["provider"] == "gemini"
    assert saved["model"] == "flash"
    # trading_date MUST be a date, not an isoformat string. This assertion used
    # to require `str` — it pinned the bug in place. asyncpg binds this to a
    # DATE column and raises "'str' object has no attribute 'toordinal'" on a
    # string, so the job threw on every single run and
    # psx_data_source_health.market_brief carried last_success = NULL, while the
    # brief users actually saw was written as a side effect of whoever opened
    # the dashboard first that day.
    assert isinstance(saved["trading_date"], date)
    assert not isinstance(saved["trading_date"], datetime)
    assert isinstance(saved["context_hash"], str) and len(saved["context_hash"]) == 64
    # The morning run must not clobber an existing row — that is the dashboard
    # stampede guard.
    assert saved.get("replace") is False


async def test_postclose_run_replaces_the_days_row(monkeypatch):
    """The 16:05 PKT run exists to overwrite a partial-day brief.

    Without replace=True it would generate against the closing tape and then
    have ON CONFLICT DO NOTHING discard it, leaving the morning's brief — which
    on 2026-08-06 claimed the index closed at 180740.72 when it closed at
    181776.59.
    """
    _patch_engine(monkeypatch, _gen_result())
    saved = {}

    async def _fake_get_or_create_shared(conn, **kw):
        saved.update(kw)
        return {"id": "abc", "created_at": "2026-08-06"}

    monkeypatch.setattr(sched.reports_repo, "get_or_create_shared", _fake_get_or_create_shared)

    await sched.job_generate_market_brief(replace=True)
    assert saved["replace"] is True


# --------------------------------------------------------------------------- #
# a failed generation is swallowed — never persists, never crashes            #
# --------------------------------------------------------------------------- #
async def test_job_swallows_report_unavailable(monkeypatch):
    _patch_engine(monkeypatch, ReportUnavailable("nope"))

    called = {"persist": False}

    async def _fake_get_or_create_shared(conn, **kw):
        called["persist"] = True
        return None

    monkeypatch.setattr(
        sched.reports_repo, "get_or_create_shared", _fake_get_or_create_shared
    )

    # must not raise
    await sched.job_generate_market_brief()
    assert called["persist"] is False


async def test_job_swallows_provider_error(monkeypatch):
    _patch_engine(monkeypatch, ProviderError("boom"))

    async def _fake_get_or_create_shared(conn, **kw):
        raise AssertionError("should not persist on provider error")

    monkeypatch.setattr(
        sched.reports_repo, "get_or_create_shared", _fake_get_or_create_shared
    )

    await sched.job_generate_market_brief()  # no exception escapes


async def test_job_swallows_unexpected_error(monkeypatch):
    _patch_engine(monkeypatch, RuntimeError("unexpected"))

    async def _fake_get_or_create_shared(conn, **kw):
        raise AssertionError("should not persist on unexpected error")

    monkeypatch.setattr(
        sched.reports_repo, "get_or_create_shared", _fake_get_or_create_shared
    )

    await sched.job_generate_market_brief()  # no exception escapes


# --------------------------------------------------------------------------- #
# init_scheduler registers the 9th job on a Karachi cron trigger              #
# --------------------------------------------------------------------------- #
def test_init_scheduler_registers_market_brief_job(monkeypatch):
    monkeypatch.setattr(sched.scheduler, "start", lambda: None)
    try:
        sched.init_scheduler()
        job = sched.scheduler.get_job("generate_market_brief")
        assert job is not None
        assert job.func is sched.job_generate_market_brief
        assert isinstance(job.trigger, CronTrigger)
        # scheduled in Asia/Karachi (UTC+5)
        assert "Karachi" in str(job.trigger.timezone)
        # all original jobs are preserved (8 existing + this new one)
        assert sched.scheduler.get_job("check_alerts") is not None
        assert len(sched.scheduler.get_jobs()) >= 9

        # The post-close run is what makes the brief describe the finished
        # session; it must be registered, on Karachi time, and must pass
        # replace=True or it regenerates and then discards the result.
        post = sched.scheduler.get_job("generate_market_brief_postclose")
        assert post is not None
        assert post.func is sched.job_generate_market_brief
        assert "Karachi" in str(post.trigger.timezone)
        assert post.kwargs == {"replace": True}
        # After the 15:30 PKT close, not before it.
        assert str(post.trigger.fields[post.trigger.FIELD_NAMES.index("hour")]) == "16"
    finally:
        sched.scheduler.remove_all_jobs()
