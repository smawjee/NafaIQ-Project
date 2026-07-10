from __future__ import annotations

import logging

import httpx
from sqlalchemy import text

from app.config import settings
from app.db.sqlalchemy import get_engine
from app.db.supabase import get_supabase

log = logging.getLogger(__name__)


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


async def create_in_app_notification(
    user_id: str,
    kind: str,
    title: str,
    body: str,
    link: str | None = None,
) -> None:
    """Insert a row into in_app_notifications."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO in_app_notifications (user_id, kind, title, body, link)
                VALUES (:uid, :kind, :title, :body, :link)
            """),
            {"uid": user_id, "kind": kind, "title": title, "body": body, "link": link},
        )


async def get_user_email(user_id: str) -> str | None:
    """Fetch user email from auth.users via Supabase admin API (service_role)."""
    try:
        supabase = get_supabase()
        # user_id may arrive as an asyncpg UUID object; the client expects a str.
        resp = supabase.auth.admin.get_user_by_id(str(user_id))
        return resp.user.email if resp and resp.user else None
    except Exception as e:
        log.error("Failed to get user email for %s: %s", user_id, e)
        return None


async def get_notification_prefs(user_id: str) -> dict[str, bool]:
    """Fetch user notification prefs. Returns defaults if no row."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT email_alerts, push_alerts, in_app_alerts FROM user_notification_prefs WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.mappings().first()
    if not row:
        return {"email_alerts": True, "push_alerts": False, "in_app_alerts": True}
    return dict(row)


async def fire_alert(
    user_id: str,
    alert_type: str,
    title: str,
    body: str,
    link: str | None = None,
) -> None:
    """Fire an alert: in-app notification + email (if user prefs allow)."""
    prefs = await get_notification_prefs(user_id)
    if prefs.get("in_app_alerts", True):
        # in_app_notifications.kind uses "price_alert" (alert_type is "stock_price")
        kind = "price_alert" if alert_type == "stock_price" else alert_type
        await create_in_app_notification(user_id, kind, title, body, link)
    if prefs.get("email_alerts", False):
        email = await get_user_email(user_id)
        if email:
            html = f"""
            <div style="font-family: sans-serif; padding: 20px; max-width: 600px;">
                <h2 style="color: #00d4aa;">{title}</h2>
                <p>{body}</p>
                {f'<p><a href="{link}" style="color: #00d4aa;">View details</a></p>' if link else ''}
                <hr style="border-color: rgba(255,255,255,0.1);" />
                <p style="font-size: 12px; color: #64748b;">NafaIQ — Pakistan Stock Exchange Intelligence</p>
            </div>
            """
            await send_email(email, title, html)
