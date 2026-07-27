"""Security-guard tests for the admin services: flag typing, role-escalation
protection, last-super-admin protection, suspension enforcement, and bootstrap
email parsing. DB-free — the transaction context and repos are monkeypatched.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.services.admin.authz import AdminContext, RequestMeta

META = RequestMeta(request_id="req-1", ip="127.0.0.1")


@asynccontextmanager
async def _fake_begin():
    yield object()  # sentinel connection; repos are patched so it's never used


# --- Flag typing validation -------------------------------------------------
def test_flag_validation_rejects_wrong_type():
    from app.services.admin import flags

    with pytest.raises(HTTPException) as ei:
        flags._validate({"key": "maintenance_mode", "type": "bool"}, "not-a-bool")
    assert ei.value.status_code == 422


def test_flag_validation_rejects_bool_for_int():
    from app.services.admin import flags

    with pytest.raises(HTTPException):
        flags._validate({"key": "x", "type": "int"}, True)  # bool is not int here


def test_flag_validation_enum_membership():
    from app.services.admin import flags

    flags._validate({"key": "mode", "type": "enum", "allowed": ["a", "b"]}, "a")
    with pytest.raises(HTTPException):
        flags._validate({"key": "mode", "type": "enum", "allowed": ["a", "b"]}, "z")


def test_flag_validation_accepts_correct_types():
    from app.services.admin import flags

    flags._validate({"key": "b", "type": "bool"}, True)
    flags._validate({"key": "i", "type": "int"}, 5)
    flags._validate({"key": "s", "type": "string"}, "hi")


# --- Role escalation guards -------------------------------------------------
@pytest.mark.asyncio
async def test_non_super_cannot_grant_super_admin(monkeypatch):
    from app.services.admin import roles
    from app.repositories.admin import roles_repo, users_repo

    monkeypatch.setattr(roles, "begin", _fake_begin)
    monkeypatch.setattr(roles_repo, "role_exists", lambda *a, **k: _true())
    monkeypatch.setattr(users_repo, "get_user", lambda *a, **k: _dict())

    actor = AdminContext(user_id="u", email="e", roles=["finance_admin"], permissions={"users.tier.write"})
    with pytest.raises(HTTPException) as ei:
        await roles.assign_role(actor=actor, meta=META, user_id="target", role_slug="super_admin", reason=None)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_non_super_cannot_grant_permissions_beyond_own(monkeypatch):
    from app.services.admin import roles
    from app.repositories.admin import roles_repo, users_repo

    monkeypatch.setattr(roles, "begin", _fake_begin)
    monkeypatch.setattr(roles_repo, "role_exists", lambda *a, **k: _true())
    monkeypatch.setattr(users_repo, "get_user", lambda *a, **k: _dict())
    # data_admin maps to permissions the actor doesn't hold.
    monkeypatch.setattr(
        roles_repo, "list_roles",
        lambda *a, **k: _list([{"slug": "data_admin", "permissions": ["market_data.refresh", "signals.read"]}]),
    )

    actor = AdminContext(user_id="u", email="e", roles=["support_admin"], permissions={"users.read"})
    with pytest.raises(HTTPException) as ei:
        await roles.assign_role(actor=actor, meta=META, user_id="target", role_slug="data_admin", reason=None)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_cannot_revoke_last_super_admin(monkeypatch):
    from app.services.admin import roles
    from app.repositories.admin import roles_repo

    monkeypatch.setattr(roles, "begin", _fake_begin)
    monkeypatch.setattr(roles_repo, "count_active_super_admins", lambda *a, **k: _int(1))

    actor = AdminContext(user_id="u", email="e", roles=["super_admin"], permissions=set())
    with pytest.raises(HTTPException) as ei:
        await roles.revoke_role(actor=actor, meta=META, user_id="target", role_slug="super_admin", reason=None)
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_non_super_cannot_revoke_super_admin(monkeypatch):
    from app.services.admin import roles

    monkeypatch.setattr(roles, "begin", _fake_begin)
    actor = AdminContext(user_id="u", email="e", roles=["support_admin"], permissions={"users.suspend"})
    with pytest.raises(HTTPException) as ei:
        await roles.revoke_role(actor=actor, meta=META, user_id="target", role_slug="super_admin", reason=None)
    assert ei.value.status_code == 403


# --- Suspension enforcement at the identity boundary ------------------------
@pytest.mark.asyncio
async def test_suspended_user_rejected_at_auth(monkeypatch):
    import jwt
    from app.services import auth
    from app.config import settings

    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")

    async def _fake_plan_features(_uid):
        return ("Free", {}, "suspended")

    monkeypatch.setattr(auth, "get_user_plan_features", _fake_plan_features)
    token = jwt.encode({"sub": "u1", "email": "s@example.com"}, "test-secret", algorithm="HS256")

    with pytest.raises(HTTPException) as ei:
        await auth.resolve_supabase_user(token)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_active_user_passes_auth(monkeypatch):
    import jwt
    from app.services import auth
    from app.config import settings

    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")

    async def _fake_plan_features(_uid):
        return ("Pro", {"max_watchlist": 50}, "active")

    monkeypatch.setattr(auth, "get_user_plan_features", _fake_plan_features)
    token = jwt.encode({"sub": "u1", "email": "a@example.com"}, "test-secret", algorithm="HS256")

    user = await auth.resolve_supabase_user(token)
    assert user["plan"] == "Pro"
    assert user["account_status"] == "active"


# --- Bootstrap email parsing ------------------------------------------------
def test_bootstrap_email_list_parsing(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_emails", " A@x.com , b@x.com ,,a@x.com ")
    assert settings.admin_bootstrap_email_list == ["a@x.com", "b@x.com"]


def test_bootstrap_email_list_empty(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_emails", "")
    assert settings.admin_bootstrap_email_list == []


# --- small async return helpers (repos are async) ---------------------------
async def _true():
    return True


async def _int(n):
    return n


async def _dict():
    return {"id": "target", "plan": "Free", "account_status": "active"}


async def _list(v):
    return v
