"""Health (3 routes) and profile (1 route) endpoint tests.

Both routers were untested. /health/sources gets particular attention because
it is ANONYMOUS and its except-branch is a deliberate information-disclosure
guard: the raw exception text can carry the Supabase project URL, table names
and connection detail, so it must never reach the response body.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {"user_id": "00000000-0000-0000-0000-000000000001", "email": "t@example.com"}

SECRET_IN_ERROR = (
    "connection to https://abcdefghijk.supabase.co failed for table "
    "psx_data_source_health (password=hunter2)"
)


# ----------------------------------- health --------------------------------


def _health_app() -> FastAPI:
    from app.api import health as health_api
    from app.middleware.rate_limit import limiter

    app = FastAPI()
    # /health/sources carries @limiter.limit, which reads app.state.limiter.
    app.state.limiter = limiter
    app.include_router(health_api.router, prefix="/api")
    return app


def _health_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_health_app()), base_url="http://t")


async def test_health_reports_ok_with_a_version(monkeypatch):
    from app.api import health as health_api

    monkeypatch.setattr(health_api, "get_market_refresh_time", lambda: "2026-07-28T09:00:00Z")

    async with _health_client() as c:
        r = await c.get("/api/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["last_market_refresh"] == "2026-07-28T09:00:00Z"


async def test_health_is_anonymous(monkeypatch):
    # Playwright's webServer readiness probe and Railway's healthcheck both hit
    # this without credentials; requiring auth here would break both.
    from app.api import health as health_api

    monkeypatch.setattr(health_api, "get_market_refresh_time", lambda: None)

    async with _health_client() as c:
        r = await c.get("/api/health")

    assert r.status_code == 200
    assert r.json()["last_market_refresh"] is None


async def test_health_db_delegates_to_db_ping(monkeypatch):
    from app.api import health as health_api

    async def _ping():
        return {"db": "ok", "latency_ms": 4}

    monkeypatch.setattr(health_api, "db_ping", _ping)

    async with _health_client() as c:
        r = await c.get("/api/health/db")

    assert r.status_code == 200
    assert r.json() == {"db": "ok", "latency_ms": 4}


async def test_health_sources_returns_rows_and_healthy_true(monkeypatch):
    class _Result:
        data = [{"source": "dps", "last_success": "2026-07-28T09:00:00Z"}]

    async def _exec(_fn):
        return _Result()

    monkeypatch.setattr("app.db.supabase.async_execute", _exec)

    async with _health_client() as c:
        r = await c.get("/api/health/sources")

    assert r.status_code == 200
    body = r.json()
    assert body["healthy"] is True
    assert body["sources"][0]["source"] == "dps"


async def test_health_sources_treats_no_rows_as_healthy(monkeypatch):
    class _Result:
        data = None

    async def _exec(_fn):
        return _Result()

    monkeypatch.setattr("app.db.supabase.async_execute", _exec)

    async with _health_client() as c:
        r = await c.get("/api/health/sources")

    assert r.json() == {"sources": [], "healthy": True}


async def test_health_sources_never_leaks_the_exception_text(monkeypatch):
    """The anonymous endpoint must degrade without disclosing internals."""

    async def _boom(_fn):
        raise RuntimeError(SECRET_IN_ERROR)

    monkeypatch.setattr("app.db.supabase.async_execute", _boom)

    async with _health_client() as c:
        r = await c.get("/api/health/sources")

    assert r.status_code == 200
    body = r.json()
    assert body == {"sources": [], "healthy": False, "error": "health check unavailable"}

    raw = r.text
    for leak in ("supabase.co", "psx_data_source_health", "hunter2", "RuntimeError"):
        assert leak not in raw, f"{leak!r} leaked into an anonymous response"


async def test_health_sources_requests_explicit_columns_not_star(monkeypatch):
    """last_error_message holds raw str(e) and must never be selected here."""
    captured: dict[str, str] = {}

    class _Table:
        def select(self, cols):
            captured["cols"] = cols
            return self

        def order(self, _c):
            return self

    class _Client:
        def table(self, _name):
            return _Table()

    class _Result:
        data = []

    async def _exec(fn):
        fn(_Client())
        return _Result()

    monkeypatch.setattr("app.db.supabase.async_execute", _exec)

    async with _health_client() as c:
        await c.get("/api/health/sources")

    assert "*" not in captured["cols"]
    assert "last_error_message" not in captured["cols"]
    assert "last_error" in captured["cols"]


# ----------------------------------- profile -------------------------------


def _profile_app() -> FastAPI:
    from app.api import profile as profile_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(profile_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _profile_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_profile_app()), base_url="http://t")


@pytest.fixture
def select_plan(monkeypatch):
    from app.api import profile as profile_api

    calls: list = []

    async def _fn(user_id, plan):
        calls.append((user_id, plan))
        return {"plan": plan, "plan_selected_at": "2026-07-28T09:00:00Z"}

    monkeypatch.setattr(profile_api.profile_service, "select_plan", _fn)
    return calls


@pytest.mark.parametrize("plan", ["Free", "Pro", "Premium"])
async def test_select_plan_accepts_each_tier(select_plan, plan):
    async with _profile_client() as c:
        r = await c.post("/api/profile/plan", json={"plan": plan})

    assert r.status_code == 200
    assert r.json()["plan"] == plan


async def test_select_plan_uses_the_authenticated_user_not_the_body(select_plan):
    # A client must not be able to change someone else's plan by supplying a
    # user_id; the route only ever reads user["user_id"] from the token.
    async with _profile_client() as c:
        r = await c.post(
            "/api/profile/plan",
            json={"plan": "Pro", "user_id": "00000000-0000-0000-0000-0000000000ff"},
        )

    assert r.status_code == 200
    assert select_plan[0][0] == FAKE_USER["user_id"]


async def test_select_plan_requires_a_plan(select_plan):
    async with _profile_client() as c:
        r = await c.post("/api/profile/plan", json={})

    assert r.status_code == 422
    assert select_plan == []
