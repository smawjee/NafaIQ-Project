"""Password recovery: mint a Supabase recovery OTP and mail it ourselves.

Supabase can send this email on its own, but its built-in mailer is rate-limited
to a couple of messages an hour per project and its template lives in a dashboard
rather than in this repo. So we mint the token with the service-role admin API
(`generate_link`, which generates but does NOT send) and deliver the 6-digit code
through the same Brevo/Resend sender the alerts pipeline already uses — which
gets us a bilingual template under version control and our own rate limits.

The client then calls `supabase.auth.verifyOtp({type: "recovery"})` with that
code and, once a session exists, `updateUser({password})`.

Nothing in here raises. `send_recovery_code` is fired detached from the request
(see api/auth.py) precisely so the caller learns nothing — not from the status
code, not from the response time — about whether the address has an account.
"""
from __future__ import annotations

import asyncio
import logging
import time
from html import escape

from app.config import settings
from app.db.supabase import get_supabase
from app.repositories import user_repo
from app.repositories.base import connect
from app.services.notifier import send_email

log = logging.getLogger(__name__)

# email -> [monotonic timestamps of sends within the window]
#
# In-process, which is enough today: the API runs as a single Railway replica
# (railway.json, numReplicas 1) and the slowapi limiter it sits behind is
# in-process too. If the API is ever scaled out, this becomes per-replica and
# should move to Postgres or Redis.
_sends: dict[str, list[float]] = {}
_WINDOW_SECONDS = 3600


def _throttled(email: str) -> bool:
    """True when this mailbox has already had its hourly allowance."""
    now = time.monotonic()
    recent = [t for t in _sends.get(email, []) if now - t < _WINDOW_SECONDS]
    if len(recent) >= settings.password_reset_max_per_hour:
        _sends[email] = recent
        return True
    recent.append(now)
    _sends[email] = recent
    return False


def _reset_throttle() -> None:
    """Test hook — clears the in-process send history."""
    _sends.clear()


async def send_recovery_code(email: str, lang: str = "en") -> None:
    """Mail a password-recovery code to `email`, if that account exists.

    Silent about everything: unknown address, suspended account, throttled
    mailbox and provider failure all return the same way (nothing), and the only
    trace is a server-side log line.
    """
    address = email.strip().lower()
    if not address:
        return

    try:
        if _throttled(address):
            log.info("password recovery throttled for a mailbox")
            return

        try:
            resp = await asyncio.to_thread(
                lambda: get_supabase().auth.admin.generate_link(
                    {"type": "recovery", "email": address}
                )
            )
        except Exception as e:
            # Overwhelmingly "user not found", which is the normal path for a
            # typo'd address — not worth an error-level log.
            log.info("password recovery: no link minted (%s)", type(e).__name__)
            return

        user_id = getattr(resp.user, "id", None)
        if user_id:
            async with connect() as conn:
                status = await user_repo.get_account_status(conn, str(user_id))
            if status == "suspended":
                # A suspended account is rejected at the identity boundary
                # anyway (services/auth.py), so a new password would buy nothing.
                log.info("password recovery skipped for a suspended account")
                return

        code = resp.properties.email_otp
        if not code:
            log.error("password recovery: generate_link returned no email_otp")
            return

        subject, html = recovery_email(code, lang)
        sent = await send_email(address, subject, html)
        if not sent:
            log.error("password recovery: email provider rejected the send")
    except Exception:
        log.warning("password recovery failed", exc_info=True)


def recovery_email(code: str, lang: str) -> tuple[str, str]:
    """(subject, html) for the recovery code, in English or Urdu."""
    minutes = settings.password_reset_code_ttl_minutes
    is_ur = lang == "ur"

    if is_ur:
        subject = "نفع آئی کیو — پاس ورڈ ری سیٹ کوڈ"
        heading = "اپنا پاس ورڈ ری سیٹ کریں"
        intro = "اپنا نیا پاس ورڈ بنانے کے لیے یہ کوڈ نفع آئی کیو میں درج کریں۔"
        expiry = f"یہ کوڈ {minutes} منٹ میں ختم ہو جائے گا۔"
        ignore = (
            "اگر آپ نے پاس ورڈ ری سیٹ کی درخواست نہیں کی تھی تو اس ای میل کو "
            "نظر انداز کر دیں — آپ کا پاس ورڈ تبدیل نہیں ہوگا۔"
        )
        footer = "نفع آئی کیو — پاکستان اسٹاک ایکسچینج انٹیلیجنس"
    else:
        subject = "NafaIQ — your password reset code"
        heading = "Reset your password"
        intro = "Enter this code in NafaIQ to set a new password."
        expiry = f"This code expires in {minutes} minutes."
        ignore = (
            "If you didn't ask to reset your password, ignore this email — "
            "your password will not change."
        )
        footer = "NafaIQ — Pakistan Stock Exchange Intelligence"

    direction = 'dir="rtl"' if is_ur else 'dir="ltr"'
    safe_code = escape(code)

    return subject, (
        f'<div {direction} style="font-family:sans-serif;padding:20px;max-width:600px;">'
        f'<h2 style="color:#00d4aa;">{heading}</h2>'
        f"<p>{intro}</p>"
        '<p style="font-family:monospace;font-size:32px;font-weight:700;'
        'letter-spacing:8px;color:#0d1424;background:#f1f5f9;border-radius:8px;'
        f'padding:16px;text-align:center;">{safe_code}</p>'
        f'<p style="color:#64748b;">{expiry}</p>'
        f"<p>{ignore}</p>"
        '<hr style="border-color:rgba(0,0,0,0.1);" />'
        f'<p style="font-size:12px;color:#64748b;">{footer}</p>'
        "</div>"
    )
