"""Email + notification delivery primitives.

Two delivery buckets share the Resend sender here:
- Threshold/condition ALERTS go through app.services.alerts.events.record_event
  (gated by email_alerts).
- User-action ACTIVITY/receipts go through notify_activity below (gated by
  email_activity), fired fire-and-forget from service mutation points.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable

import httpx

from app.config import settings
from app.db.supabase import get_supabase
from app.repositories import alerts as alerts_repo
from app.repositories import notifications_repo
from app.repositories.base import begin, connect

log = logging.getLogger(__name__)


def email_html(title: str, body: str, link: str | None = None) -> str:
    """Shared NafaIQ email template."""
    link_html = (
        f'<p><a href="{link}" style="color:#00d4aa;">View details</a></p>'
        if link
        else ""
    )
    return (
        '<div style="font-family:sans-serif;padding:20px;max-width:600px;">'
        f'<h2 style="color:#00d4aa;">{title}</h2>'
        f"<p>{body}</p>"
        f"{link_html}"
        '<hr style="border-color:rgba(255,255,255,0.1);" />'
        '<p style="font-size:12px;color:#64748b;">NafaIQ — Pakistan Stock Exchange Intelligence</p>'
        "</div>"
    )


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend API. Returns True on success."""
    if not settings.resend_api_key:
        log.warning("RESEND_API_KEY not configured; skipping email to %s", to)
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.status_code >= 300:
                log.error("Resend error %s: %s", resp.status_code, resp.text)
                return False
            return True
    except Exception as e:
        log.error("Email send failed: %s", e)
        return False


async def get_user_email(user_id: str) -> str | None:
    """Fetch user email from auth.users via Supabase admin API (service_role)."""
    try:
        def _fetch():
            return get_supabase().auth.admin.get_user_by_id(str(user_id))
        resp = await asyncio.to_thread(_fetch)
        return resp.user.email if resp and resp.user else None
    except Exception as e:
        log.error("Failed to get user email for %s: %s", user_id, e)
        return None


async def notify_activity(
    user_id: str,
    kind: str,
    title: str,
    body: str,
    link: str | None = None,
) -> None:
    """Deliver a user-activity notification (in-app + email), each gated by the
    user's prefs. Self-contained (own DB connections) so it is safe to run
    detached via fire_and_forget, and resilient — a failure here must never
    surface to the triggering request.
    """
    try:
        async with connect() as conn:
            prefs = await notifications_repo.get_prefs(conn, user_id)
        in_app = prefs.get("in_app_alerts", True) if prefs else True
        email_on = prefs.get("email_activity", False) if prefs else False

        if in_app:
            async with begin() as conn:
                await alerts_repo.insert_in_app_notification(
                    conn, user_id, kind, title, body, link
                )
        if email_on:
            email = await get_user_email(user_id)
            if email:
                await send_email(email, title, email_html(title, body, link))
    except Exception:
        log.warning("activity notification failed for %s", user_id, exc_info=True)


def fire_and_forget(coro: Awaitable[Any]) -> None:
    """Schedule a coroutine to run detached from the request lifecycle, logging
    any exception instead of raising. Use for best-effort side effects (e.g.
    activity notifications) that must not block or break the caller."""
    task = asyncio.ensure_future(coro)

    def _log_exc(t: "asyncio.Future[Any]") -> None:
        exc = t.exception()
        if exc is not None:
            log.warning("fire_and_forget task failed: %s", exc)

    task.add_done_callback(_log_exc)
