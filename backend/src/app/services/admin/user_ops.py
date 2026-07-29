"""User lifecycle actions backed by the Supabase Auth admin API.

These are the operations an administrator needs beyond suspend/reactivate:
recovering a locked-out user, re-sending a verification mail, forcibly ending
sessions, and honouring an erasure request.

The Supabase Python SDK is synchronous, so every call is pushed to a thread the
way `services/notifier.py` already does it.

SECURITY — recovery links never leave this module.
`auth.admin.generate_link` returns a live, single-use URL that grants control of
the account. Returning it to the caller (or writing it to a log or an audit row)
would turn `users.suspend` into an account-takeover primitive: any support admin
could mint a link for any account, including a super admin's. So the link is
generated, handed to the mailer, and dropped. The API returns only a status.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

from fastapi import HTTPException

from app.db.supabase import get_supabase
from app.repositories.admin import users_repo
from app.repositories.base import begin
from app.services.admin.audit import write_audit
from app.services.admin.authz import AdminContext, RequestMeta

log = logging.getLogger(__name__)

ANONYMISED_DOMAIN = "anonymised.invalid"


def redact_email(email: Optional[str]) -> Optional[str]:
    """u***@d***.com — enough to correlate, not enough to re-identify.

    The audit log is readable by every admin with `audit.read`, so an
    anonymisation record must not be the one place the original address survives.
    """
    if not email or "@" not in email:
        return None
    local, _, domain = email.partition("@")
    tld = domain.rpartition(".")[2]
    return f"{local[:1]}***@{domain[:1]}***.{tld}" if tld else f"{local[:1]}***@{domain[:1]}***"


async def _auth_admin(fn_name: str, *args, **kwargs) -> Any:
    """Call a supabase.auth.admin method off the event loop."""

    def _call():
        admin = get_supabase().auth.admin
        return getattr(admin, fn_name)(*args, **kwargs)

    return await asyncio.to_thread(_call)


async def _get_auth_user(user_id: str) -> Any:
    try:
        resp = await _auth_admin("get_user_by_id", user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("auth.admin.get_user_by_id failed for %s", user_id, exc_info=True)
        raise HTTPException(502, f"Could not read the account: {e}") from e
    user = getattr(resp, "user", None)
    if not user:
        raise HTTPException(404, "No auth account for that user id")
    return user


# ---------------------------------------------------------------------------
# Session revocation
# ---------------------------------------------------------------------------


async def force_sign_out(*, actor: AdminContext, meta: RequestMeta, user_id: str) -> dict:
    """Revoke every active session for a user.

    Complements suspension rather than duplicating it: suspension is enforced when
    the next request arrives, while this invalidates the refresh tokens so the
    client cannot mint a new access token at all.
    """
    try:
        await _auth_admin("sign_out", user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("force sign-out failed for %s", user_id, exc_info=True)
        raise HTTPException(502, f"Could not revoke sessions: {e}") from e

    async with begin() as conn:
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.sign_out",
            resource_type="auth.users",
            resource_id=user_id,
            target_user_id=user_id,
            meta=meta,
        )
    return {"status": "ok", "detail": "All sessions revoked."}


# ---------------------------------------------------------------------------
# Recovery / verification mail
# ---------------------------------------------------------------------------


async def send_password_reset(*, actor: AdminContext, meta: RequestMeta, user_id: str) -> dict:
    """Send the account's own password-recovery email.

    Uses the standard `reset_password_for_email` flow so Supabase both generates
    and delivers the link — the backend never holds it.
    """
    user = await _get_auth_user(user_id)
    email = getattr(user, "email", None)
    if not email:
        raise HTTPException(422, "That account has no email address to send to.")

    try:
        await asyncio.to_thread(
            lambda: get_supabase().auth.reset_password_for_email(email)
        )
    except Exception as e:  # noqa: BLE001
        log.warning("password reset send failed for %s", user_id, exc_info=True)
        raise HTTPException(502, f"Could not send the reset email: {e}") from e

    async with begin() as conn:
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.password_reset_sent",
            resource_type="auth.users",
            resource_id=user_id,
            target_user_id=user_id,
            # Deliberately no link, and no plaintext address, in the audit row.
            after={"sent_to": redact_email(email)},
            meta=meta,
        )
    return {"status": "ok", "detail": "Password reset email sent to the account holder."}


async def resend_verification(*, actor: AdminContext, meta: RequestMeta, user_id: str) -> dict:
    """Re-send the sign-up confirmation mail to an unverified account."""
    user = await _get_auth_user(user_id)
    email = getattr(user, "email", None)
    if not email:
        raise HTTPException(422, "That account has no email address to send to.")
    if getattr(user, "email_confirmed_at", None):
        # Not an error the admin caused — say plainly why nothing was sent.
        raise HTTPException(409, "That email address is already confirmed.")

    try:
        await asyncio.to_thread(
            lambda: get_supabase().auth.resend({"type": "signup", "email": email})
        )
    except Exception as e:  # noqa: BLE001
        log.warning("verification resend failed for %s", user_id, exc_info=True)
        raise HTTPException(502, f"Could not resend the verification email: {e}") from e

    async with begin() as conn:
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.verification_resent",
            resource_type="auth.users",
            resource_id=user_id,
            target_user_id=user_id,
            after={"sent_to": redact_email(email)},
            meta=meta,
        )
    return {"status": "ok", "detail": "Verification email resent."}


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------


async def anonymise(
    *, actor: AdminContext, meta: RequestMeta, user_id: str, reason: Optional[str]
) -> dict:
    """Scrub a user's personal data while keeping their records.

    Erasure semantics chosen for this platform: identity is destroyed, activity is
    not. Portfolios, holdings, transactions and finance rows survive, so platform
    aggregates and the audit trail stay truthful — but nothing left points back to
    a person.

    Irreversible. The original address is not recoverable from this system
    afterwards, including from the audit log.
    """
    if user_id == actor.user_id:
        # Cheap guard against the most obvious foot-gun.
        raise HTTPException(422, "You cannot anonymise your own account.")

    user = await _get_auth_user(user_id)
    original_email = getattr(user, "email", None)

    # `.invalid` is reserved by RFC 2606 and can never be registered or routed,
    # so the tombstone address can't collide with a real user or receive mail.
    tombstone = f"deleted-{uuid.uuid4().hex[:8]}@{ANONYMISED_DOMAIN}"

    try:
        await _auth_admin(
            "update_user_by_id",
            user_id,
            {"email": tombstone, "user_metadata": {}},
        )
    except Exception as e:  # noqa: BLE001
        log.warning("anonymise: auth update failed for %s", user_id, exc_info=True)
        raise HTTPException(502, f"Could not anonymise the auth record: {e}") from e

    # Best-effort: the identity is already destroyed above, so a session that
    # outlives this call is a smaller problem than aborting half-way.
    try:
        await _auth_admin("sign_out", user_id)
    except Exception:  # noqa: BLE001
        log.warning("anonymise: session revocation failed for %s", user_id, exc_info=True)

    async with begin() as conn:
        await users_repo.anonymise_profile(conn, user_id=user_id)
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.anonymise",
            resource_type="profiles",
            resource_id=user_id,
            target_user_id=user_id,
            before={"email": redact_email(original_email)},
            after={"email": tombstone, "display_name": None},
            reason=reason,
            meta=meta,
        )

    return {
        "status": "ok",
        "detail": "Account anonymised. Portfolio and finance records were kept.",
    }
