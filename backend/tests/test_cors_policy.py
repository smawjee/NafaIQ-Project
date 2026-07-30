"""CORS must pin the public origins WITHOUT breaking local development.

Regression: CORS_ORIGINS was set on Railway to the production origin plus
`http://localhost:5173`. That looked complete and broke every local run against
the deployed backend, because the e2e web server listens on `127.0.0.1:8080` and
a browser treats `127.0.0.1` and `localhost` as different origins. The whole
Playwright suite went red with 40+ "blocked by CORS policy" console errors.

The fix allows loopback on any port via an anchored regex. These tests exist to
prove the regex is anchored — an unanchored one would hand `localhost.evil.com`
the same access, which is the trap this pattern usually falls into.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def client(monkeypatch):
    """An app instance with CORS_ORIGINS pinned, as in production.

    Two deliberate choices, both learned from CI:

    1. The pinned origins are monkeypatched onto the EXISTING settings object,
       never via `importlib.reload(config)`. A reload replaces the settings
       singleton, and every module that did `from app.config import settings`
       keeps the stale object — later tests then monkeypatch a settings the
       code under test never reads (this broke test_provider_key_pool in CI).
       Only `app.main` is reloaded, because it snapshots cors_origins at
       import time.
    2. No `with TestClient(...)`: entering the context runs the lifespan, and
       main.py's lifespan calls ensure_reflected(), which needs a real
       SUPABASE_DATABASE_PASSWORD. CI runs with Supabase env empty by design
       (see ci.yml). CORS is middleware wired at app construction, so the
       lifespan adds nothing to what these tests assert.
    """
    from fastapi.testclient import TestClient

    from app.config import settings

    monkeypatch.setattr(
        settings, "cors_origins", "https://nafaiq.vercel.app,http://localhost:5173"
    )
    import app.main as main_mod

    importlib.reload(main_mod)
    yield TestClient(main_mod.app)
    # Rebuild main against the restored origins for the rest of the suite.
    monkeypatch.undo()
    importlib.reload(main_mod)


def _allowed(client, origin: str) -> bool:
    r = client.options(
        "/api/market/snapshot",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    return r.headers.get("access-control-allow-origin") is not None


@pytest.mark.parametrize(
    "origin,reason",
    [
        ("https://nafaiq.vercel.app", "the production web app"),
        ("http://localhost:5173", "explicitly allow-listed dev port"),
        ("http://127.0.0.1:8080", "the e2e web server — the case that broke"),
        ("http://localhost:8080", "same port, other spelling"),
        ("http://127.0.0.1:4321", "any dev port a developer picks"),
        ("http://[::1]:8080", "ipv6 loopback"),
    ],
)
def test_allowed_origins(client, origin, reason):
    assert _allowed(client, origin), f"{origin} must be allowed ({reason})"


@pytest.mark.parametrize(
    "origin,reason",
    [
        ("https://evil.example.com", "an unrelated site"),
        ("http://localhost.evil.com", "suffix attack — an UNANCHORED regex allows this"),
        ("http://127.0.0.1.evil.com", "ip-prefix attack"),
        ("https://nafaiq.vercel.app.evil.com", "production-origin suffix attack"),
    ],
)
def test_rejected_origins(client, origin, reason):
    assert not _allowed(client, origin), f"{origin} must be refused ({reason})"


def test_credentials_are_enabled_only_with_pinned_origins(client):
    """`Access-Control-Allow-Credentials` with a wildcard origin is rejected by
    browsers outright, so it must only appear alongside a specific origin."""
    r = client.options(
        "/api/market/snapshot",
        headers={"Origin": "https://nafaiq.vercel.app", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "https://nafaiq.vercel.app"
    assert r.headers.get("access-control-allow-credentials") == "true"
