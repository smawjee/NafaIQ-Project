"""Report endpoint tests over a minimal FastAPI app.

Auth is DI-overridden, the engine + reports_repo + quota are monkeypatched, and
DB connection context managers are stubbed — so the `ai_reports` table does NOT
need to be live. We assert HTTP behaviour, cache short-circuits, quota gating
(429), and the fail-closed 503.
"""
from __future__ import annotations

import contextlib

import httpx
import pytest
from fastapi import FastAPI

from app.schemas.reports import Citation, MarketBriefReport, PortfolioReport
from app.services.ai.engine import GeneratedReport, ReportUnavailable
from app.schemas.reports import VerificationResult

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {"ai_reports_per_period": 3, "ai_reports_period": "month"},
}


def _make_app() -> FastAPI:
    from app.api import reports as reports_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(reports_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=_make_app())
    return httpx.AsyncClient(transport=transport, base_url="http://t")


@contextlib.asynccontextmanager
async def _fake_cm():
    yield object()


def _gen_result(report=None, provider="gemini", model="flash") -> GeneratedReport:
    report = report or MarketBriefReport(
        headline="Market brief",
        observations=["The KSE100 closed at 100000."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[Citation(value=100000.0, source_key="indices.kse100.close", as_of="2026-07-14")],
    )
    return GeneratedReport(
        report=report,
        verification=VerificationResult(verified=True, mismatches=[]),
        provider=provider,
        model=model,
        bundle={"indices": {"kse100": {"close": 100000.0}}},
    )


def _patch_engine(monkeypatch, result_or_exc):
    from app.services.ai import report_service as reports_api

    async def _fake_generate(spec, **kw):
        if isinstance(result_or_exc, Exception):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(reports_api.engine, "generate_report", _fake_generate)
    # stub DB connection managers so no live DB / table is needed
    monkeypatch.setattr(reports_api, "connect", _fake_cm)
    monkeypatch.setattr(reports_api, "begin", _fake_cm)


# --------------------------------------------------------------------------- #
# market-brief — shared cache, generate on miss                               #
# --------------------------------------------------------------------------- #
async def test_market_brief_generates_on_cache_miss(monkeypatch):
    from app.services.ai import report_service as reports_api

    _patch_engine(monkeypatch, _gen_result())

    async def _no_latest(conn, **kw):
        return None

    created = {}

    async def _create_shared(conn, **kw):
        created.update(kw)
        return {"content": kw["content"], "provider": kw["provider"],
                "model": kw["model"], "verified": kw["verified"],
                "created_at": "2026-07-14T00:00:00"}

    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _no_latest)
    monkeypatch.setattr(reports_api.reports_repo, "get_or_create_shared", _create_shared)

    async with _client() as c:
        res = await c.get("/api/ai/report/market-brief")

    assert res.status_code == 200
    body = res.json()
    assert body["content"]["headline"] == "Market brief"
    assert body["provider"] == "gemini"
    assert body["verified"] is True
    assert created["trading_date"] == __import__("datetime").date.today()
    # An auto-load must never overwrite the day's row — that is the stampede guard.
    assert created.get("replace") is False


async def test_market_brief_refresh_replaces_the_stored_row(monkeypatch):
    """`?refresh=true` must overwrite, not dedupe.

    The reported bug: pressing refresh regenerated the brief (the call showed up
    in Langfuse with the correct closing figures) and then ON CONFLICT DO
    NOTHING returned the row already stored, so the card kept showing a stale
    mid-session brief no matter how many times the user refreshed.
    """
    from app.services.ai import report_service as reports_api

    _patch_engine(monkeypatch, _gen_result())
    today = __import__("datetime").date.today()

    async def _has_todays_row(conn, **kw):
        return {
            "content": {"headline": "Stale mid-session brief"},
            "provider": "gemini", "model": "flash", "verified": True,
            "trading_date": today, "created_at": "2026-08-06T07:42:00",
        }

    saved = {}

    async def _create_shared(conn, **kw):
        saved.update(kw)
        return {"content": kw["content"], "provider": kw["provider"],
                "model": kw["model"], "verified": kw["verified"],
                "created_at": "2026-08-06T11:05:00"}

    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _has_todays_row)
    monkeypatch.setattr(reports_api.reports_repo, "get_or_create_shared", _create_shared)

    async with _client() as c:
        res = await c.get("/api/ai/report/market-brief?refresh=true")

    assert res.status_code == 200
    assert saved["replace"] is True
    # The response carries the NEW content, not the row that was already there.
    assert res.json()["content"]["headline"] == "Market brief"


async def test_market_brief_serves_shared_cache(monkeypatch):
    from app.services.ai import report_service as reports_api

    # A date, not a string: the trading_date column is DATE and the driver
    # returns datetime.date. Stringly-typed fixtures here masked a real bug.
    today = __import__("datetime").date.today()
    cached = {
        "content": {"headline": "Cached brief"},
        "provider": "gemini", "model": "flash", "verified": True,
        "trading_date": today, "created_at": "2026-07-14T00:00:00",
    }

    called = {"gen": False}

    async def _fake_generate(spec, **kw):
        called["gen"] = True
        return _gen_result()

    async def _latest(conn, **kw):
        return cached

    monkeypatch.setattr(reports_api.engine, "generate_report", _fake_generate)
    monkeypatch.setattr(reports_api, "connect", _fake_cm)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _latest)

    async with _client() as c:
        res = await c.get("/api/ai/report/market-brief")

    assert res.status_code == 200
    assert res.json()["content"]["headline"] == "Cached brief"
    assert called["gen"] is False  # served from cache, engine not called


# --------------------------------------------------------------------------- #
# stock — shared cache by (symbol, trading_date)                              #
# --------------------------------------------------------------------------- #
async def test_stock_report_generates(monkeypatch):
    from app.services.ai import report_service as reports_api

    _patch_engine(monkeypatch, _gen_result())

    async def _no_latest(conn, **kw):
        return None

    seen = {}

    async def _create_shared(conn, **kw):
        seen.update(kw)
        return {"content": kw["content"], "provider": kw["provider"],
                "model": kw["model"], "verified": kw["verified"],
                "created_at": "2026-07-14T00:00:00"}

    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _no_latest)
    monkeypatch.setattr(reports_api.reports_repo, "get_or_create_shared", _create_shared)

    async with _client() as c:
        res = await c.post("/api/ai/report/stock/OGDC")

    assert res.status_code == 200
    assert seen["subject"] == "OGDC"


# --------------------------------------------------------------------------- #
# portfolio — per-user, quota-gated                                          #
# --------------------------------------------------------------------------- #
async def test_portfolio_report_persists_and_increments(monkeypatch):
    from app.services.ai import report_service as reports_api

    pf = PortfolioReport(
        headline="Portfolio review", period_days=180,
        observations=["Your window spans 180 days."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[Citation(value=180, source_key="period_days", as_of="2026-07-14")],
    )
    _patch_engine(monkeypatch, _gen_result(report=pf, provider="groq", model="llama"))

    async def _ok_quota(user):
        return True, 1, 3

    calls = {"insert": False, "increment": False, "prune": False}

    async def _insert(conn, **kw):
        calls["insert"] = True
        return {"id": 5, "created_at": "2026-07-14T00:00:00"}

    async def _increment(conn, uid):
        calls["increment"] = True

    async def _prune(conn, uid, rt, keep=5):
        calls["prune"] = True

    monkeypatch.setattr(reports_api.quota, "check_report_quota", _ok_quota)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "increment_report_usage", _increment)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _prune)

    async with _client() as c:
        res = await c.post("/api/ai/report/portfolio?days=180")

    assert res.status_code == 200
    body = res.json()
    assert body["content"]["period_days"] == 180
    assert body["provider"] == "groq"
    assert calls == {"insert": True, "increment": True, "prune": True}


async def test_portfolio_report_quota_exceeded_429(monkeypatch):
    from app.services.ai import report_service as reports_api

    called = {"gen": False}

    async def _fake_generate(spec, **kw):
        called["gen"] = True
        return _gen_result()

    async def _blocked(user):
        return False, 3, 3

    monkeypatch.setattr(reports_api.engine, "generate_report", _fake_generate)
    monkeypatch.setattr(reports_api.quota, "check_report_quota", _blocked)

    async with _client() as c:
        res = await c.post("/api/ai/report/portfolio")

    assert res.status_code == 429
    assert called["gen"] is False  # quota checked before any generation


# --------------------------------------------------------------------------- #
# finance — per-user, quota-gated                                            #
# --------------------------------------------------------------------------- #
async def test_finance_report_quota_exceeded_429(monkeypatch):
    from app.services.ai import report_service as reports_api

    async def _blocked(user):
        return False, 3, 3

    monkeypatch.setattr(reports_api.quota, "check_report_quota", _blocked)

    async with _client() as c:
        res = await c.post("/api/ai/report/finance")

    assert res.status_code == 429


async def test_finance_report_generates(monkeypatch):
    from app.services.ai import report_service as reports_api
    from app.schemas.reports import FinanceReport

    fr = FinanceReport(
        headline="Finance review",
        observations=["Educational note."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[],
    )
    _patch_engine(monkeypatch, _gen_result(report=fr, provider="groq", model="llama"))

    async def _ok_quota(user):
        return True, 0, 3

    async def _insert(conn, **kw):
        return {"id": 8, "created_at": "2026-07-14T00:00:00"}

    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(reports_api.quota, "check_report_quota", _ok_quota)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "increment_report_usage", _noop)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _noop)

    async with _client() as c:
        res = await c.post("/api/ai/report/finance")

    assert res.status_code == 200
    assert res.json()["content"]["headline"] == "Finance review"


# --------------------------------------------------------------------------- #
# dashboard-recommendation — per-user daily cache                            #
# --------------------------------------------------------------------------- #
async def test_dashboard_rec_daily_cache_second_call(monkeypatch):
    from app.services.ai import report_service as reports_api
    from app.schemas.reports import DashboardRecReport

    # A date, not a string: the trading_date column is DATE and the driver
    # returns datetime.date. Stringly-typed fixtures here masked a real bug.
    today = __import__("datetime").date.today()
    dr = DashboardRecReport(
        headline="Daily nudge",
        observations=["Educational nudge."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[],
    )
    gen_calls = {"n": 0}

    async def _fake_generate(spec, **kw):
        gen_calls["n"] += 1
        return _gen_result(report=dr, provider="groq", model="llama")

    # First call: no cache -> generate + insert. Second call: cache present.
    store = {"row": None}

    async def _latest(conn, **kw):
        return store["row"]

    async def _insert(conn, **kw):
        store["row"] = {
            "content": kw["content"], "provider": kw["provider"], "model": kw["model"],
            "verified": kw["verified"], "trading_date": today,
            "created_at": "2026-07-14T00:00:00",
        }
        return {"id": 3, "created_at": "2026-07-14T00:00:00"}

    # Track that the dashboard nudge does NOT consume the deep-report quota (F2)
    # but IS pruned for retention (F3).
    usage = {"increment": 0, "prune": 0}

    async def _increment(conn, uid):
        usage["increment"] += 1

    async def _prune(conn, uid, rt, keep=5):
        usage["prune"] += 1

    monkeypatch.setattr(reports_api.engine, "generate_report", _fake_generate)
    monkeypatch.setattr(reports_api, "connect", _fake_cm)
    monkeypatch.setattr(reports_api, "begin", _fake_cm)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _latest)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "increment_report_usage", _increment)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _prune)

    async with _client() as c:
        first = await c.get("/api/ai/report/dashboard-recommendation")
        second = await c.get("/api/ai/report/dashboard-recommendation")

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["content"]["headline"] == "Daily nudge"
    assert second.json()["content"]["headline"] == "Daily nudge"
    assert gen_calls["n"] == 1  # second served from the daily cache
    assert usage["increment"] == 0  # dashboard must NOT consume deep-report quota (F2)
    assert usage["prune"] == 1  # retention prune applied on the one generation (F3)


async def test_dashboard_rec_cache_generation_and_storage_are_language_scoped(monkeypatch):
    from app.services.ai import report_service as reports_api
    from app.schemas.reports import DashboardRecReport

    dr = DashboardRecReport(
        lang="ur",
        headline="روزانہ خلاصہ",
        observations=["یہ تعلیمی خلاصہ ہے۔"],
        disclaimer="صرف تعلیمی معلومات۔ مالی مشورہ نہیں۔",
        citations=[],
    )
    seen = {"latest": [], "engine": [], "insert": []}

    async def _fake_generate(spec, **kw):
        seen["engine"].append(kw)
        return _gen_result(report=dr, provider="groq", model="llama")

    async def _latest(conn, **kw):
        seen["latest"].append(kw)
        return None

    async def _insert(conn, **kw):
        seen["insert"].append(kw)
        return {"id": 4, "created_at": "2026-07-14T00:00:00"}

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(reports_api.engine, "generate_report", _fake_generate)
    monkeypatch.setattr(reports_api, "connect", _fake_cm)
    monkeypatch.setattr(reports_api, "begin", _fake_cm)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _latest)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _noop)

    async with _client() as c:
        res = await c.get("/api/ai/report/dashboard-recommendation?lang=ur")

    assert res.status_code == 200
    assert res.json()["content"]["lang"] == "ur"
    assert {call["lang"] for call in seen["latest"]} == {"ur"}
    assert seen["engine"][0]["lang"] == "ur"
    assert seen["insert"][0]["lang"] == "ur"


# --------------------------------------------------------------------------- #
# fail-closed -> 503                                                          #
# --------------------------------------------------------------------------- #
async def test_report_unavailable_yields_503(monkeypatch):
    from app.services.ai import report_service as reports_api

    _patch_engine(monkeypatch, ReportUnavailable("could not verify"))

    async def _no_latest(conn, **kw):
        return None

    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _no_latest)

    async with _client() as c:
        res = await c.get("/api/ai/report/market-brief")

    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# Regression: the cache never hit in production for the feature's whole life   #
# --------------------------------------------------------------------------- #
def test_report_sql_binds_content_instead_of_a_postgres_cast():
    """`:content::jsonb` is NOT a bind parameter.

    SQLAlchemy's text() bind regex carries a `(?!:)` lookahead so it skips
    `::casts` — so `:content` stayed literal in the emitted SQL, asyncpg hit the
    bare ':' and raised PostgresSyntaxError. Every ai_reports insert failed and
    the table sat at 0 rows since the feature was written. CAST(:content AS
    jsonb) binds correctly.
    """
    import inspect

    from app.repositories import reports_repo

    src = inspect.getsource(reports_repo)
    assert ":content::jsonb" not in src, "reverted to a cast SQLAlchemy cannot bind"
    assert "CAST(:content AS jsonb)" in src


def test_serve_uses_a_real_date_so_the_cache_can_match():
    """trading_date is a DATE column: the driver refuses to bind a str
    ("'str' object has no attribute 'toordinal'"), and a cached row's
    trading_date comes back as datetime.date — so comparing it to an
    isoformat string was always False and the cache could never hit.
    """
    import inspect

    from app.services.ai import report_service

    src = inspect.getsource(report_service.serve)
    assert "date.today().isoformat()" not in src, (
        "serve() must hold a date, not a string — see this test's docstring"
    )
    assert "today = date.today()" in src


# --------------------------------------------------------------------------- #
# Failure cooldown — the quota guard                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.requires_db  # touches the real engine
async def test_a_failed_report_is_not_regenerated_on_every_page_load(monkeypatch):
    """The dashboard nudge auto-loads. Without a cooldown, a provider outage
    meant every refresh rebuilt ~13s of context and spent another burst of
    tokens on a provider already refusing — draining the daily quota the cache
    exists to protect."""
    from app.services.ai import report_service as reports_api
    from app.services.ai.engine import ReportUnavailable
    from app.services.ai.specs import REPORT_SPECS

    reports_api._recent_failures.clear()
    calls = {"n": 0}

    async def _boom(*a, **kw):
        calls["n"] += 1
        raise ReportUnavailable("provider is down")

    async def _no_cache(conn, **kw):
        return None

    monkeypatch.setattr(reports_api, "_generate", _boom)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _no_cache)

    user = {"user_id": "u1", "email": "e", "plan": "Free", "features": {}}
    spec = REPORT_SPECS["dashboard_rec"]

    for _ in range(3):
        with pytest.raises(ReportUnavailable):
            await reports_api.serve(spec, mode="user_daily", user=user, lang="en")

    assert calls["n"] == 1, (
        f"generation ran {calls['n']}x for 3 loads — the cooldown is not holding"
    )
    reports_api._recent_failures.clear()


@pytest.mark.requires_db  # touches the real engine
async def test_the_cooldown_expires_so_recovery_is_automatic(monkeypatch):
    """A provider outage must not disable the report until a redeploy."""
    from app.services.ai import report_service as reports_api
    from app.services.ai.engine import ReportUnavailable
    from app.services.ai.specs import REPORT_SPECS

    reports_api._recent_failures.clear()
    calls = {"n": 0}

    async def _boom(*a, **kw):
        calls["n"] += 1
        raise ReportUnavailable("provider is down")

    async def _no_cache(conn, **kw):
        return None

    monkeypatch.setattr(reports_api, "_generate", _boom)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _no_cache)
    monkeypatch.setattr(reports_api, "_FAILURE_COOLDOWN_S", 0.0)  # expire instantly

    user = {"user_id": "u2", "email": "e", "plan": "Free", "features": {}}
    spec = REPORT_SPECS["dashboard_rec"]
    for _ in range(2):
        with pytest.raises(ReportUnavailable):
            await reports_api.serve(spec, mode="user_daily", user=user, lang="en")

    assert calls["n"] == 2, "an expired cooldown must allow a fresh attempt"
    reports_api._recent_failures.clear()


async def test_concurrent_loads_collapse_to_one_generation(monkeypatch):
    """The cache dedupes READS; this pins that generation is deduped too.

    The cached row only exists after a ~13s generation, so every request landing
    in that window used to miss the cache and generate its own copy. Two tabs
    double the nudge; for the SHARED market brief every user opening the
    dashboard at 09:30 burned a full generation to produce a row
    get_or_create_shared then discarded.
    """
    import asyncio as _asyncio
    import datetime as _dt

    from app.services.ai import report_service as reports_api
    from app.schemas.reports import DashboardRecReport
    from app.services.ai.specs import REPORT_SPECS

    reports_api._recent_failures.clear()
    reports_api._inflight.clear()
    today = _dt.date.today()
    dr = DashboardRecReport(
        headline="Daily nudge",
        observations=["Educational nudge."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[],
    )
    store: dict[str, object] = {"row": None}
    gen_calls = {"n": 0}

    async def _slow_generate(spec, **kw):
        gen_calls["n"] += 1
        await _asyncio.sleep(0.05)  # the window every racer used to slip through
        return _gen_result(report=dr, provider="groq", model="llama")

    async def _latest(conn, **kw):
        return store["row"]

    async def _insert(conn, **kw):
        store["row"] = {
            "content": kw["content"], "provider": kw["provider"], "model": kw["model"],
            "verified": kw["verified"], "trading_date": today,
            "created_at": "2026-07-16T00:00:00",
        }
        return {"id": 1, "created_at": "2026-07-16T00:00:00"}

    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(reports_api, "_generate", _slow_generate)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _latest)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _noop)
    monkeypatch.setattr(reports_api, "begin", lambda *a, **k: _fake_cm())
    monkeypatch.setattr(reports_api, "connect", lambda *a, **k: _fake_cm())

    user = {"user_id": "u1", "email": "e", "plan": "Free", "features": {}}
    spec = REPORT_SPECS["dashboard_rec"]

    results = await _asyncio.gather(
        *(reports_api.serve(spec, mode="user_daily", user=user, lang="en") for _ in range(5))
    )

    assert gen_calls["n"] == 1, (
        f"5 concurrent loads ran {gen_calls['n']} generations — single-flight is not holding"
    )
    assert all(r.content["headline"] == "Daily nudge" for r in results), (
        "every racer must still get the report, not an error"
    )
    assert not reports_api._inflight, "the lock entry leaked — _inflight grows per user forever"


async def test_manual_refresh_bypasses_the_daily_cache_and_costs_quota(monkeypatch):
    """The refresh button must actually regenerate — and must not be free.

    The auto-load path is free because it reads the day's row. A button a user
    can click all afternoon cannot be, or it is the stampede the cache exists to
    prevent wearing a nicer hat. So it spends the deep-report quota.
    """
    import datetime as _dt

    from app.services.ai import report_service as reports_api
    from app.schemas.reports import DashboardRecReport
    from app.services.ai.specs import REPORT_SPECS

    reports_api._recent_failures.clear()
    reports_api._inflight.clear()
    today = _dt.date.today()
    dr = DashboardRecReport(
        headline="Daily nudge",
        observations=["Educational nudge."],
        disclaimer="Educational information only. Not financial advice.",
        citations=[],
    )
    gen_calls = {"n": 0}
    usage = {"increment": 0}

    async def _fake_generate(spec, **kw):
        gen_calls["n"] += 1
        return _gen_result(report=dr, provider="groq", model="llama")

    # A cached row for today already exists — the whole point is bypassing it.
    async def _latest(conn, **kw):
        return {
            "content": dr.model_dump(), "provider": "groq", "model": "llama",
            "verified": True, "trading_date": today,
            "created_at": "2026-07-16T00:00:00",
        }

    async def _insert(conn, **kw):
        return {"id": 1, "created_at": "2026-07-16T00:00:00"}

    async def _increment(conn, uid):
        usage["increment"] += 1

    async def _noop(*a, **kw):
        return None

    async def _quota_ok(user):
        return True, 0, 3

    monkeypatch.setattr(reports_api, "_generate", _fake_generate)
    monkeypatch.setattr(reports_api.quota, "check_report_quota", _quota_ok)
    monkeypatch.setattr(reports_api.reports_repo, "get_latest_report", _latest)
    monkeypatch.setattr(reports_api.reports_repo, "insert_report", _insert)
    monkeypatch.setattr(reports_api.reports_repo, "increment_report_usage", _increment)
    monkeypatch.setattr(reports_api.reports_repo, "prune_reports", _noop)
    monkeypatch.setattr(reports_api, "begin", lambda *a, **k: _fake_cm())
    monkeypatch.setattr(reports_api, "connect", lambda *a, **k: _fake_cm())

    user = {"user_id": "u1", "email": "e", "plan": "Free",
            "features": {"ai_reports_per_period": 3, "ai_reports_period": "month"}}
    spec = REPORT_SPECS["dashboard_rec"]

    # Without force: the cached row wins, nothing is generated or charged.
    await reports_api.serve(spec, mode="user_daily", user=user, lang="en")
    assert gen_calls["n"] == 0 and usage["increment"] == 0

    # With force: regenerates despite the cache, and charges one unit.
    await reports_api.serve(spec, mode="user_daily", user=user, lang="en", force=True)
    assert gen_calls["n"] == 1, "force must bypass the daily cached row"
    assert usage["increment"] == 1, "a manual refresh must spend quota"


async def test_manual_refresh_is_429_when_quota_is_gone(monkeypatch):
    """Refresh is available, not unlimited — otherwise it reopens the quota hole
    the daily cache exists to close."""
    from fastapi import HTTPException

    from app.services.ai import report_service as reports_api
    from app.services.ai.specs import REPORT_SPECS

    reports_api._recent_failures.clear()
    reports_api._inflight.clear()

    async def _boom(*a, **kw):
        raise AssertionError("must not generate once quota is exhausted")

    async def _no_quota(user):
        return False, 3, 3

    monkeypatch.setattr(reports_api, "_generate", _boom)
    monkeypatch.setattr(reports_api.quota, "check_report_quota", _no_quota)
    monkeypatch.setattr(reports_api, "connect", lambda *a, **k: _fake_cm())

    user = {"user_id": "u1", "email": "e", "plan": "Free",
            "features": {"ai_reports_per_period": 3, "ai_reports_period": "month"}}

    with pytest.raises(HTTPException) as exc:
        await reports_api.serve(
            REPORT_SPECS["dashboard_rec"], mode="user_daily", user=user,
            lang="en", force=True,
        )
    assert exc.value.status_code == 429
