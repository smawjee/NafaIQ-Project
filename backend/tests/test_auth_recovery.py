"""Password-recovery endpoint + service.

The whole point of this feature is that it gives nothing away. These pin the
behaviours that make that true and are easy to regress into a leak:

- an unregistered address must be indistinguishable from a registered one,
- a suspended account must not be handed a way back in,
- a single mailbox must not be usable as a free mail cannon,
- and the route must stay reachable with no Authorization header at all.

No database and no network: the Supabase admin API, the mail sender and the
profile lookup are all monkeypatched.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

USER_ID = "00000000-0000-0000-0000-000000000001"
CODE = "482913"


class _FakeProperties:
    def __init__(self, email_otp: str) -> None:
        self.email_otp = email_otp


class _FakeUser:
    def __init__(self, user_id: str) -> None:
        self.id = user_id


class _FakeLinkResponse:
    def __init__(self, email_otp: str = CODE, user_id: str = USER_ID) -> None:
        self.properties = _FakeProperties(email_otp)
        self.user = _FakeUser(user_id)


@pytest.fixture
def recovery(monkeypatch):
    """auth_recovery with its two outbound edges captured and its throttle clean."""
    from app.services import auth_recovery

    auth_recovery._reset_throttle()

    sent: list[tuple[str, str, str]] = []
    state = {"known": True, "status": "active"}

    class _FakeAdmin:
        def generate_link(self, params):
            if not state["known"]:
                raise RuntimeError("User not found")
            return _FakeLinkResponse()

    class _FakeAuth:
        admin = _FakeAdmin()

    class _FakeClient:
        auth = _FakeAuth()

    async def _fake_send_email(to: str, subject: str, html: str) -> bool:
        sent.append((to, subject, html))
        return True

    async def _fake_status(conn, user_id):
        return state["status"]

    class _FakeConn:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(auth_recovery, "get_supabase", lambda: _FakeClient())
    monkeypatch.setattr(auth_recovery, "send_email", _fake_send_email)
    monkeypatch.setattr(auth_recovery, "connect", lambda: _FakeConn())
    monkeypatch.setattr(
        auth_recovery.user_repo, "get_account_status", _fake_status, raising=True
    )

    yield auth_recovery, sent, state
    auth_recovery._reset_throttle()


@pytest.mark.asyncio
async def test_known_address_is_mailed_the_generated_code(recovery) -> None:
    auth_recovery, sent, _ = recovery
    await auth_recovery.send_recovery_code("User@Example.com")

    assert len(sent) == 1
    to, subject, html = sent[0]
    assert to == "user@example.com", "the address must be normalised before sending"
    assert CODE in html
    assert "password reset code" in subject.lower()


@pytest.mark.asyncio
async def test_unknown_address_sends_nothing_and_does_not_raise(recovery) -> None:
    auth_recovery, sent, state = recovery
    state["known"] = False

    await auth_recovery.send_recovery_code("nobody@example.com")

    assert sent == []


@pytest.mark.asyncio
async def test_suspended_account_gets_no_code(recovery) -> None:
    """A suspended account is rejected at the identity boundary anyway — handing
    it a fresh password would only be a way to keep knocking."""
    auth_recovery, sent, state = recovery
    state["status"] = "suspended"

    await auth_recovery.send_recovery_code("user@example.com")

    assert sent == []


@pytest.mark.asyncio
async def test_one_mailbox_is_capped_per_hour(recovery, monkeypatch) -> None:
    auth_recovery, sent, _ = recovery
    from app.config import settings

    monkeypatch.setattr(settings, "password_reset_max_per_hour", 3)

    for _ in range(5):
        await auth_recovery.send_recovery_code("user@example.com")

    assert len(sent) == 3

    # A different mailbox is unaffected by the first one's exhausted allowance.
    await auth_recovery.send_recovery_code("someone.else@example.com")
    assert len(sent) == 4


@pytest.mark.asyncio
async def test_a_provider_failure_is_swallowed(recovery, monkeypatch) -> None:
    """A bounced send must not surface — the caller learns nothing either way."""
    auth_recovery, _, _ = recovery

    async def _refuse(*a, **kw) -> bool:
        return False

    monkeypatch.setattr(auth_recovery, "send_email", _refuse)
    await auth_recovery.send_recovery_code("user@example.com")  # must not raise


def test_urdu_email_is_rendered_right_to_left() -> None:
    from app.services.auth_recovery import recovery_email

    _, en_html = recovery_email(CODE, "en")
    ur_subject, ur_html = recovery_email(CODE, "ur")

    assert 'dir="ltr"' in en_html
    assert 'dir="rtl"' in ur_html
    assert CODE in ur_html
    assert ur_subject != "NafaIQ — your password reset code"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (
        __import__("app.config", fromlist=["settings"]).settings.supabase_url
        and __import__("app.config", fromlist=["settings"]).settings.supabase_service_key
    ),
    reason="Supabase credentials not configured",
)
async def test_the_real_code_fits_what_the_clients_accept() -> None:
    """The minted code must be enterable in the apps.

    GoTrue's MAILER_OTP_LENGTH is a project setting anywhere in 6-10; this
    project issues 8, not the documented default of 6. The web and mobile code
    fields were originally capped at 6 characters, which made the entire flow
    impossible to complete and failed *silently* — the user just couldn't type
    the last two digits. Nothing in a mocked test could catch that, so this one
    mints a real code and checks it against the bounds the clients enforce
    (RECOVERY_CODE_MIN/MAX_LENGTH in @nafaiq/shared).
    """
    import uuid

    import httpx

    from app.config import settings
    from app.db.supabase import get_supabase

    # Must stay in step with frontend/packages/shared/src/api.ts.
    CLIENT_MIN, CLIENT_MAX = 6, 10

    admin = f"{settings.supabase_url}/auth/v1/admin/users"
    sk = settings.supabase_service_key
    headers = {"apikey": sk, "Authorization": f"Bearer {sk}"}
    email = f"otplen_{uuid.uuid4().hex[:10]}@nafaiq-test.local"

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            admin,
            headers=headers,
            json={"email": email, "password": "OtpLen!2026x", "email_confirm": True},
        )
        r.raise_for_status()
        uid = r.json()["id"]

    try:
        resp = await asyncio.to_thread(
            lambda: get_supabase().auth.admin.generate_link(
                {"type": "recovery", "email": email}
            )
        )
        code = resp.properties.email_otp

        assert code.isdigit(), f"the clients accept digits only, got {code!r}"
        assert CLIENT_MIN <= len(code) <= CLIENT_MAX, (
            f"Supabase is issuing a {len(code)}-digit recovery code, which the "
            f"apps cannot accept (they take {CLIENT_MIN}-{CLIENT_MAX} digits). "
            f"Either change MAILER_OTP_LENGTH in the Supabase dashboard or widen "
            f"RECOVERY_CODE_MIN/MAX_LENGTH in frontend/packages/shared/src/api.ts."
        )
    finally:
        async with httpx.AsyncClient(timeout=30) as c:
            await c.delete(f"{admin}/{uid}", headers=headers)


# ---------------------------------------------------------------- HTTP contract


def _app(monkeypatch) -> tuple[FastAPI, list]:
    from app.api import auth as auth_api
    from app.middleware.auth import BearerTokenMiddleware
    from app.middleware.rate_limit import limiter
    from slowapi import _rate_limit_exceeded_handler

    calls: list[tuple[str, str]] = []

    # Record at call time and hand back an inert coroutine — fire_and_forget
    # would otherwise schedule a real detached task in the test loop.
    def _record(email: str, lang: str = "en"):
        calls.append((email, lang))

        async def _noop() -> None:
            return None

        return _noop()

    monkeypatch.setattr(auth_api, "fire_and_forget", lambda coro: coro.close())
    monkeypatch.setattr(auth_api.auth_recovery, "send_recovery_code", _record)

    # Every test in this module shares one process-wide limiter keyed on the
    # client IP, and every request here comes from the same fake one.
    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(BearerTokenMiddleware)
    app.include_router(auth_api.router, prefix="/api")
    return app, calls


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


@pytest.mark.asyncio
async def test_endpoint_is_reachable_with_no_authorization_header(monkeypatch) -> None:
    """The middleware must let this through: a user who has forgotten their
    password has, by definition, no credential to present."""
    from app.config import settings

    monkeypatch.setattr(settings, "psx_api_token", "some-token")
    app, _ = _app(monkeypatch)

    async with _client(app) as c:
        r = await c.post("/api/auth/forgot-password", json={"email": "u@example.com"})

    assert r.status_code == 202
    assert r.json() == {"status": "sent"}


@pytest.mark.asyncio
async def test_response_is_identical_for_a_malformed_address(monkeypatch) -> None:
    app, _ = _app(monkeypatch)
    async with _client(app) as c:
        bad = await c.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    # Shape is rejected before any lookup — that is a validation error about the
    # request, not a statement about whether an account exists.
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_lang_defaults_to_english_and_accepts_urdu(monkeypatch) -> None:
    app, calls = _app(monkeypatch)

    async with _client(app) as c:
        await c.post("/api/auth/forgot-password", json={"email": "a@example.com"})
        await c.post(
            "/api/auth/forgot-password", json={"email": "b@example.com", "lang": "ur"}
        )
        bad = await c.post(
            "/api/auth/forgot-password", json={"email": "c@example.com", "lang": "fr"}
        )

    assert calls == [("a@example.com", "en"), ("b@example.com", "ur")]
    assert bad.status_code == 422
