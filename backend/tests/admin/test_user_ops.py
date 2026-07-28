"""User lifecycle actions: session revocation, recovery mail, anonymisation.

The security-critical assertion here is that a password-recovery URL never
escapes `user_ops` — not in the response, not in the audit row. `generate_link`
style flows hand back a live single-use URL that grants control of the account,
so leaking it would turn `users.suspend` into an account-takeover primitive.

DB-free: the Supabase client, the repo and the transaction context are all
monkeypatched.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.admin import user_ops
from app.services.admin.authz import AdminContext, RequestMeta

ACTOR = AdminContext(user_id="admin-1", email="admin@x.com", roles=["super_admin"])
META = RequestMeta(request_id="req-1", ip="127.0.0.1")

# A realistic-looking recovery URL. No assertion may ever find this string in a
# response body or an audit row.
SECRET_LINK = "https://supabase.co/auth/v1/verify?token=SUPER_SECRET_RECOVERY_TOKEN"


class FakeAdmin:
    def __init__(self, user):
        self._user = user
        self.calls: list[tuple] = []

    def get_user_by_id(self, uid):
        self.calls.append(("get_user_by_id", uid))
        return SimpleNamespace(user=self._user)

    def sign_out(self, uid):
        self.calls.append(("sign_out", uid))
        return None

    def update_user_by_id(self, uid, attrs):
        self.calls.append(("update_user_by_id", uid, attrs))
        self._user.email = attrs.get("email", self._user.email)
        return SimpleNamespace(user=self._user)

    def generate_link(self, *a, **k):
        self.calls.append(("generate_link", a, k))
        return SimpleNamespace(properties=SimpleNamespace(action_link=SECRET_LINK))


class FakeAuth:
    def __init__(self, admin):
        self.admin = admin
        self.sent: list[tuple] = []

    def reset_password_for_email(self, email):
        self.sent.append(("reset", email))
        return SimpleNamespace(action_link=SECRET_LINK)

    def resend(self, payload):
        self.sent.append(("resend", payload))
        return None


@pytest.fixture
def env(monkeypatch):
    user = SimpleNamespace(
        id="user-9", email="usman@example.com", email_confirmed_at="2026-01-01T00:00:00Z"
    )
    admin = FakeAdmin(user)
    auth = FakeAuth(admin)
    audits: list[dict] = []
    profile_calls: list[str] = []

    monkeypatch.setattr(user_ops, "get_supabase", lambda: SimpleNamespace(auth=auth))

    @asynccontextmanager
    async def fake_begin():
        yield object()

    async def fake_audit(_conn, **kwargs):
        audits.append(kwargs)
        return 1

    async def fake_anon(_conn, *, user_id):
        profile_calls.append(user_id)
        return {"id": user_id, "account_status": "suspended"}

    monkeypatch.setattr(user_ops, "begin", fake_begin)
    monkeypatch.setattr(user_ops, "write_audit", fake_audit)
    monkeypatch.setattr(user_ops.users_repo, "anonymise_profile", fake_anon)

    return SimpleNamespace(
        user=user, admin=admin, auth=auth, audits=audits, profile_calls=profile_calls
    )


def _no_secret_anywhere(payload) -> bool:
    return "SUPER_SECRET_RECOVERY_TOKEN" not in repr(payload)


# --- redaction --------------------------------------------------------------


def test_redact_email_keeps_shape_only():
    assert user_ops.redact_email("usman@example.com") == "u***@e***.com"


def test_redact_email_handles_missing_and_malformed():
    assert user_ops.redact_email(None) is None
    assert user_ops.redact_email("not-an-email") is None


# --- force sign-out ---------------------------------------------------------


@pytest.mark.asyncio
async def test_force_sign_out_revokes_and_audits(env):
    out = await user_ops.force_sign_out(actor=ACTOR, meta=META, user_id="user-9")
    assert out["status"] == "ok"
    assert ("sign_out", "user-9") in env.admin.calls
    assert env.audits[0]["action"] == "admin.user.sign_out"
    assert env.audits[0]["target_user_id"] == "user-9"


# --- password reset ---------------------------------------------------------


@pytest.mark.asyncio
async def test_password_reset_sends_mail(env):
    out = await user_ops.send_password_reset(actor=ACTOR, meta=META, user_id="user-9")
    assert out["status"] == "ok"
    assert ("reset", "usman@example.com") in env.auth.sent


@pytest.mark.asyncio
async def test_password_reset_never_returns_the_link(env):
    """The whole point of the endpoint's shape."""
    out = await user_ops.send_password_reset(actor=ACTOR, meta=META, user_id="user-9")
    assert _no_secret_anywhere(out)


@pytest.mark.asyncio
async def test_password_reset_never_audits_the_link_or_plaintext_email(env):
    await user_ops.send_password_reset(actor=ACTOR, meta=META, user_id="user-9")
    row = env.audits[0]
    assert _no_secret_anywhere(row)
    # The audit log is readable by every audit.read holder — redacted only.
    assert "usman@example.com" not in repr(row)
    assert row["after"]["sent_to"] == "u***@e***.com"


# --- resend verification ----------------------------------------------------


@pytest.mark.asyncio
async def test_resend_verification_refuses_confirmed_address(env):
    with pytest.raises(HTTPException) as ei:
        await user_ops.resend_verification(actor=ACTOR, meta=META, user_id="user-9")
    assert ei.value.status_code == 409
    assert env.auth.sent == []


@pytest.mark.asyncio
async def test_resend_verification_sends_for_unconfirmed(env):
    env.user.email_confirmed_at = None
    out = await user_ops.resend_verification(actor=ACTOR, meta=META, user_id="user-9")
    assert out["status"] == "ok"
    assert env.auth.sent[0][0] == "resend"


# --- anonymise --------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymise_tombstones_email_on_reserved_domain(env):
    await user_ops.anonymise(actor=ACTOR, meta=META, user_id="user-9", reason=None)
    assert env.user.email.endswith("@anonymised.invalid")
    assert env.user.email.startswith("deleted-")


@pytest.mark.asyncio
async def test_anonymise_scrubs_profile_and_revokes_sessions(env):
    await user_ops.anonymise(actor=ACTOR, meta=META, user_id="user-9", reason=None)
    assert env.profile_calls == ["user-9"]
    assert ("sign_out", "user-9") in env.admin.calls


@pytest.mark.asyncio
async def test_anonymise_audits_only_a_redacted_address(env):
    await user_ops.anonymise(actor=ACTOR, meta=META, user_id="user-9", reason="gdpr")
    row = env.audits[-1]
    assert row["action"] == "admin.user.anonymise"
    assert row["before"]["email"] == "u***@e***.com"
    assert "usman@example.com" not in repr(row)
    assert row["reason"] == "gdpr"


@pytest.mark.asyncio
async def test_anonymise_refuses_self(env):
    """Cheap guard against the most obvious foot-gun."""
    with pytest.raises(HTTPException) as ei:
        await user_ops.anonymise(
            actor=ACTOR, meta=META, user_id=ACTOR.user_id, reason=None
        )
    assert ei.value.status_code == 422
    assert env.profile_calls == []


@pytest.mark.asyncio
async def test_anonymise_survives_session_revocation_failure(env, monkeypatch):
    """Identity is already destroyed by then — aborting would leave it half-done."""
    original = env.admin.sign_out

    def flaky(uid):
        original(uid)
        raise RuntimeError("network")

    monkeypatch.setattr(env.admin, "sign_out", flaky)
    out = await user_ops.anonymise(actor=ACTOR, meta=META, user_id="user-9", reason=None)
    assert out["status"] == "ok"
    assert env.profile_calls == ["user-9"]


# --- failure surfaces -------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_auth_user_404s(env, monkeypatch):
    monkeypatch.setattr(
        env.admin, "get_user_by_id", lambda uid: SimpleNamespace(user=None)
    )
    with pytest.raises(HTTPException) as ei:
        await user_ops.send_password_reset(actor=ACTOR, meta=META, user_id="ghost")
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_upstream_failure_is_502_not_500(env, monkeypatch):
    def boom(uid):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(env.admin, "sign_out", boom)
    with pytest.raises(HTTPException) as ei:
        await user_ops.force_sign_out(actor=ACTOR, meta=META, user_id="user-9")
    assert ei.value.status_code == 502
