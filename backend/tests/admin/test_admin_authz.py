"""Admin authorization tests.

Router-only FastAPI app with require_user DI-overridden and the DB-backed admin
context resolver monkeypatched — no network, no DB. Verifies that non-admins,
demo/plain users, and under-privileged admins are denied, and that permission
scoping and super-admin implicit access work.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.services.admin.authz import AdminContext

PLAIN_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "user@example.com",
    "plan": "Free",
    "features": {},
}


def _make_app() -> FastAPI:
    from app.api.admin import router as admin_router
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: PLAIN_USER
    return app


def _patch_context(monkeypatch, ctx: AdminContext) -> None:
    """Force resolve_admin_context (the only DB touch in the authz path) to
    return a fixed context, so the whole suite is DB-free."""
    async def _fake(_user: dict) -> AdminContext:
        return ctx

    monkeypatch.setattr("app.services.admin.authz.resolve_admin_context", _fake)


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


# --- AdminContext unit behavior --------------------------------------------
def test_super_admin_has_every_permission():
    ctx = AdminContext(user_id="u", email="e", roles=["super_admin"], permissions=set())
    assert ctx.is_admin and ctx.is_super_admin
    assert ctx.has("anything.at.all")
    assert ctx.has("flags.write")


def test_scoped_admin_only_has_mapped_permissions():
    ctx = AdminContext(
        user_id="u", email="e", roles=["support_admin"],
        permissions={"users.read", "users.suspend"},
    )
    assert ctx.has("users.suspend")
    assert not ctx.has("flags.write")
    assert not ctx.is_super_admin


def test_non_admin_context_is_not_admin():
    ctx = AdminContext(user_id="u", email="e", roles=[], permissions=set())
    assert not ctx.is_admin


# --- End-to-end route authorization ----------------------------------------
@pytest.mark.asyncio
async def test_plain_user_denied_admin_me(monkeypatch):
    # No roles => not an admin.
    _patch_context(monkeypatch, AdminContext(user_id="u", email="e", roles=[], permissions=set()))
    async with await _client(_make_app()) as client:
        res = await client.get("/api/admin/me")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_me_returns_roles_and_permissions(monkeypatch):
    ctx = AdminContext(
        user_id="u", email="e", roles=["support_admin"], permissions={"users.read"}
    )
    _patch_context(monkeypatch, ctx)
    async with await _client(_make_app()) as client:
        res = await client.get("/api/admin/me")
    assert res.status_code == 200
    body = res.json()
    assert body["roles"] == ["support_admin"]
    assert "users.read" in body["permissions"]


@pytest.mark.asyncio
async def test_permission_scoping_blocks_flags_write(monkeypatch):
    # support_admin can read users but must NOT reach flags.write.
    ctx = AdminContext(
        user_id="u", email="e", roles=["support_admin"],
        permissions={"users.read", "users.suspend"},
    )
    _patch_context(monkeypatch, ctx)

    # Keep the permitted path DB-free: only the authorization decision matters.
    from app.services.admin import users as users_service
    from app.schemas.admin import Page, PageMeta, UserListItem

    async def _fake_list(**_kw):
        return Page[UserListItem](items=[], meta=PageMeta(page=1, page_size=1, total=0))

    monkeypatch.setattr(users_service, "list_users", _fake_list)

    async with await _client(_make_app()) as client:
        ok = await client.get("/api/admin/users?page=1&page_size=1")
        # Lacks flags.write → 403 before any handler logic.
        denied = await client.put("/api/admin/flags/maintenance_mode", json={"value": True})
    assert ok.status_code == 200
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_missing_permission_returns_403_not_500(monkeypatch):
    ctx = AdminContext(user_id="u", email="e", roles=["ai_admin"], permissions={"ai.read"})
    _patch_context(monkeypatch, ctx)
    async with await _client(_make_app()) as client:
        res = await client.get("/api/admin/audit")  # needs audit.read
    assert res.status_code == 403
