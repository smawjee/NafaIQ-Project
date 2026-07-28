"""Notification endpoint tests. The whole /api/notifications surface (4 routes)
plus services.notifications had no test at all.

Auth is DI-overridden and the service layer is monkeypatched, so no DB is
required. Follows tests/test_reports_api.py.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {"user_id": "00000000-0000-0000-0000-000000000001", "email": "t@example.com"}


def _make_app() -> FastAPI:
    from app.api import notifications as notifications_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(notifications_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_make_app()), base_url="http://t")


@pytest.fixture
def svc(monkeypatch):
    from app.api import notifications as notifications_api

    calls: dict[str, list] = {}

    def stub(name, result):
        async def _fn(*args, **kwargs):
            calls.setdefault(name, []).append((args, kwargs))
            return result

        monkeypatch.setattr(notifications_api.notifications_service, name, _fn)

    stub("list_notifications", [{"id": 1, "title": "Bill due", "read_at": None}])
    stub("mark_read", {"id": 1, "read_at": "2026-07-28T09:00:00Z"})
    stub("get_prefs", {"email_alerts": True, "push_alerts": False})
    stub("update_prefs", {"email_alerts": False, "push_alerts": False})
    return calls


async def test_list_notifications_scopes_to_the_caller(svc):
    async with _client() as c:
        r = await c.get("/api/notifications/list")

    assert r.status_code == 200
    assert r.json()[0]["title"] == "Bill due"
    assert svc["list_notifications"][0][0][0] == FAKE_USER["user_id"]


async def test_list_notifications_defaults_the_limit_to_50(svc):
    async with _client() as c:
        await c.get("/api/notifications/list")

    # limit is positional in the service signature.
    assert svc["list_notifications"][0][0][1] == 50


async def test_list_notifications_honours_an_explicit_limit(svc):
    async with _client() as c:
        await c.get("/api/notifications/list?limit=5")

    assert svc["list_notifications"][0][0][1] == 5


async def test_list_notifications_rejects_a_non_integer_limit(svc):
    async with _client() as c:
        r = await c.get("/api/notifications/list?limit=lots")

    assert r.status_code == 422
    assert "list_notifications" not in svc


async def test_mark_read_passes_the_callers_id_and_the_path_id(svc):
    async with _client() as c:
        r = await c.patch("/api/notifications/1/read")

    assert r.status_code == 200
    assert svc["mark_read"][0][0] == (FAKE_USER["user_id"], 1)


async def test_mark_read_rejects_a_non_integer_id(svc):
    async with _client() as c:
        r = await c.patch("/api/notifications/abc/read")

    assert r.status_code == 422
    assert "mark_read" not in svc


async def test_get_prefs_returns_the_stored_preferences(svc):
    async with _client() as c:
        r = await c.get("/api/notifications/preferences")

    assert r.status_code == 200
    assert r.json() == {"email_alerts": True, "push_alerts": False}
    assert svc["get_prefs"][0][0][0] == FAKE_USER["user_id"]


async def test_update_prefs_forwards_the_parsed_model(svc):
    async with _client() as c:
        r = await c.patch("/api/notifications/preferences", json={"email_alerts": False})

    assert r.status_code == 200
    user_id, body = svc["update_prefs"][0][0]
    assert user_id == FAKE_USER["user_id"]
    # The route hands the service the pydantic model, not a raw dict — the
    # service relies on exclude_unset to do a partial update.
    assert body.__class__.__name__ == "NotifPrefsUpdate"


async def test_update_prefs_accepts_an_empty_partial_body(svc):
    async with _client() as c:
        r = await c.patch("/api/notifications/preferences", json={})

    assert r.status_code == 200


async def test_update_prefs_rejects_a_wrongly_typed_field(svc):
    async with _client() as c:
        r = await c.patch("/api/notifications/preferences", json={"email_alerts": "yes please"})

    assert r.status_code == 422
    assert "update_prefs" not in svc
