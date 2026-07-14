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
    assert created["trading_date"] == __import__("datetime").date.today().isoformat()


async def test_market_brief_serves_shared_cache(monkeypatch):
    from app.services.ai import report_service as reports_api

    today = __import__("datetime").date.today().isoformat()
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

    today = __import__("datetime").date.today().isoformat()
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
