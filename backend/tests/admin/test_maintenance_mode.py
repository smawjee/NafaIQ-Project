"""End-to-end behaviour of the `maintenance_mode` flag.

Maintenance mode is the one flag that can lock everyone out, so its exemptions
matter as much as its enforcement: an admin must still be able to reach the
console to switch it back off, the health probe must keep returning 200 so the
platform isn't restarted underneath us, and the public flag endpoint must stay
readable so the web app can render a maintenance screen instead of a raw 503.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import flags


@pytest.fixture
def client():
    # No lifespan: these assertions only exercise middleware, and running
    # startup would try to reflect the live schema and start the scheduler.
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    flags.invalidate()
    yield
    flags.invalidate()


@pytest.fixture
def maintenance_on(monkeypatch):
    async def _on(key, default=True):
        return key == "maintenance_mode"

    monkeypatch.setattr(flags, "is_enabled", _on)


@pytest.fixture
def maintenance_off(monkeypatch):
    async def _off(key, default=True):
        return False if key == "maintenance_mode" else default

    monkeypatch.setattr(flags, "is_enabled", _off)


# --- Enforcement ------------------------------------------------------------


def test_api_returns_503_during_maintenance(client, maintenance_on):
    r = client.get("/api/market/snapshot")
    assert r.status_code == 503
    assert "maintenance" in r.json()["detail"].lower()


def test_503_carries_retry_after(client, maintenance_on):
    """Clients and proxies need a backoff hint, not a bare 503."""
    r = client.get("/api/market/snapshot")
    assert r.headers.get("Retry-After") == "300"


# --- Exemptions -------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/platform/flags",
        "/api/admin/me",
    ],
)
def test_exempt_paths_are_not_blocked(client, maintenance_on, path):
    """These must never 503 — they're how you observe and undo maintenance."""
    r = client.get(path)
    assert r.status_code != 503, f"{path} was blocked by maintenance mode"


def test_admin_console_reachable_during_maintenance(client, maintenance_on):
    """/api/admin/me without a JWT is 401/403 — the point is it isn't 503."""
    r = client.get("/api/admin/me")
    assert r.status_code in (401, 403)


# --- Off state --------------------------------------------------------------


def test_traffic_flows_when_maintenance_is_off(client, maintenance_off):
    """The middleware must not intercept when the flag is off.

    Asserts on the maintenance RESPONSE rather than a bare `!= 503`: this route
    reaches a live upstream, which can legitimately return 503 of its own accord.
    Checking the body and the Retry-After header isolates the middleware from
    upstream health, so the test measures what it claims to.
    """
    r = client.get("/api/market/snapshot")
    assert "Retry-After" not in r.headers
    body = r.text.lower()
    assert "maintenance" not in body


# --- Public flag endpoint ---------------------------------------------------


def test_public_flags_endpoint_is_anonymous(client, monkeypatch):
    """No Authorization header: the sign-up screen reads this before a session
    exists, so the auth middleware must let it through."""

    async def fake_public():
        return {"registration_enabled": True, "maintenance_mode": False}

    monkeypatch.setattr(flags, "public_flags", fake_public)

    r = client.get("/api/platform/flags")
    assert r.status_code == 200
    assert r.json() == {"registration_enabled": True, "maintenance_mode": False}
