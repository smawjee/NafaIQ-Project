"""Post-deploy smoke test for the password-recovery flow.

Drives the whole loop against a live Supabase project using a disposable auth
user it creates and deletes: mint a code through the real service, exchange it
for a session exactly as supabase-js does, set a new password, sign in with it,
and confirm the code cannot be replayed.

This exists because the one defect that actually shipped in this feature was
invisible to unit tests: the project issues 8-digit OTPs (GoTrue's
MAILER_OTP_LENGTH is a per-project setting in the 6-10 range, not the documented
default of 6), while both clients capped the input at 6 characters. Every mocked
test passed and the flow was impossible to complete. Only a real code caught it.

    cd backend
    python scripts/verify_password_recovery.py
    python scripts/verify_password_recovery.py --email you@example.com

Without --email the message is captured instead of sent, so the run is silent.
With --email the message is really delivered to that address, so you can confirm
the template renders and the provider is reachable. Use an address you own.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid

import httpx

from app.config import settings
from app.db.supabase import get_supabase
from app.services import auth_recovery

# Must stay in step with RECOVERY_CODE_MIN/MAX_LENGTH in
# frontend/packages/shared/src/api.ts — that is the bound the apps enforce.
CLIENT_MIN_LENGTH = 6
CLIENT_MAX_LENGTH = 10

OLD_PASSWORD = "SmokeOld!2026x"
NEW_PASSWORD = "SmokeNew!2026x"

ADMIN_URL = f"{settings.supabase_url}/auth/v1/admin/users"
AUTH_URL = f"{settings.supabase_url}/auth/v1"
SERVICE_KEY = settings.supabase_service_key
ANON_KEY = settings.supabase_publishable_key or settings.supabase_anon_key

_failures: list[str] = []


def check(condition: bool, description: str, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {description}")
    else:
        print(f"  FAIL  {description}{f' — {detail}' if detail else ''}")
        _failures.append(description)


def _admin_headers() -> dict[str, str]:
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


async def _create_user(email: str) -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            ADMIN_URL,
            headers=_admin_headers(),
            json={"email": email, "password": OLD_PASSWORD, "email_confirm": True},
        )
        r.raise_for_status()
        return r.json()["id"]


async def _delete_user(user_id: str) -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        await c.delete(f"{ADMIN_URL}/{user_id}", headers=_admin_headers())


async def _verify_otp(email: str, code: str) -> httpx.Response:
    """Byte-for-byte what supabase-js verifyOtp({type:'recovery'}) sends."""
    async with httpx.AsyncClient(timeout=30) as c:
        return await c.post(
            f"{AUTH_URL}/verify",
            headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
            json={"email": email, "token": code, "type": "recovery"},
        )


async def _update_password(access_token: str, password: str) -> httpx.Response:
    """Byte-for-byte what supabase-js updateUser({password}) sends."""
    async with httpx.AsyncClient(timeout=30) as c:
        return await c.put(
            f"{AUTH_URL}/user",
            headers={
                "apikey": ANON_KEY,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"password": password},
        )


async def _sign_in(email: str, password: str) -> int:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{AUTH_URL}/token?grant_type=password",
            headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        return r.status_code


async def run(deliver_to: str | None) -> None:
    if not (settings.supabase_url and SERVICE_KEY and ANON_KEY):
        sys.exit("Supabase is not configured — set SUPABASE_URL and the keys first.")

    email = deliver_to or f"pwreset_{uuid.uuid4().hex[:10]}@nafaiq-test.local"
    print(f"\nProject : {settings.supabase_url}")
    print(f"Mailbox : {email}{'' if deliver_to else '  (capture only, nothing sent)'}\n")

    captured: list[tuple[str, str, str]] = []
    original_send = auth_recovery.send_email

    if not deliver_to:
        async def capture(to: str, subject: str, html: str) -> bool:
            captured.append((to, subject, html))
            return True

        auth_recovery.send_email = capture  # type: ignore[assignment]

    user_id = await _create_user(email)
    try:
        auth_recovery._reset_throttle()
        await auth_recovery.send_recovery_code(email, "en")

        if deliver_to:
            check(True, "send_recovery_code ran (check the inbox for the message)")
            # The delivered code is not readable from here, so mint a fresh one
            # to assert against. This invalidates the emailed one by design.
            response = await asyncio.to_thread(
                lambda: get_supabase().auth.admin.generate_link(
                    {"type": "recovery", "email": email}
                )
            )
            code = response.properties.email_otp
        else:
            check(bool(captured), "an email was composed")
            if not captured:
                return
            _, subject, html = captured[0]
            check("password reset" in subject.lower(), f"subject reads {subject!r}")
            match = re.search(r">(\d+)<", html)
            check(match is not None, "a numeric code is rendered in the body")
            if not match:
                return
            code = match.group(1)

        check(code.isdigit(), f"the code is numeric ({code!r})")
        check(
            CLIENT_MIN_LENGTH <= len(code) <= CLIENT_MAX_LENGTH,
            f"the {len(code)}-digit code fits what the apps accept "
            f"({CLIENT_MIN_LENGTH}-{CLIENT_MAX_LENGTH})",
            "widen RECOVERY_CODE_MIN/MAX_LENGTH in @nafaiq/shared, or change "
            "MAILER_OTP_LENGTH in the Supabase dashboard",
        )

        verified = await _verify_otp(email, code)
        token = verified.json().get("access_token") if verified.status_code == 200 else None
        check(bool(token), "verifyOtp(type='recovery') returns a session", str(verified.status_code))
        if not token:
            return

        wrong = await _verify_otp(email, "0" * len(code))
        check(wrong.status_code != 200, f"a wrong code is refused ({wrong.status_code})")

        updated = await _update_password(token, NEW_PASSWORD)
        check(updated.status_code == 200, "updateUser({password}) succeeds", str(updated.status_code))

        check(await _sign_in(email, NEW_PASSWORD) == 200, "the new password signs in")
        check(await _sign_in(email, OLD_PASSWORD) != 200, "the old password no longer works")

        replay = await _verify_otp(email, code)
        check(replay.status_code != 200, f"the code is single-use ({replay.status_code} on replay)")
    finally:
        auth_recovery.send_email = original_send  # type: ignore[assignment]
        await _delete_user(user_id)
        print(f"\nDisposable user {user_id} deleted.")

    if _failures:
        sys.exit(f"\n{len(_failures)} check(s) failed: " + "; ".join(_failures))
    print("All checks passed.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email",
        metavar="ADDRESS",
        help="really deliver the message to ADDRESS (use an inbox you own)",
    )
    asyncio.run(run(parser.parse_args().email))
