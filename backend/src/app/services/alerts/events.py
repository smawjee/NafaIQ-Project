"""Alert events: notification-history reads + the event recorder that delivers
to the channels a user has enabled (in-app bell + email), respecting their
notification preferences."""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories import alerts as repo
from app.repositories import notifications_repo
from app.repositories.base import begin, connect
from app.services import notifier

log = logging.getLogger(__name__)


async def list_alert_events(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_alert_events(conn, user_id, limit)


async def mark_event_read(user_id: str, event_id: int) -> bool:
    async with begin() as conn:
        return await repo.mark_event_read(conn, user_id, event_id)


def _email_html(title: str, body: str) -> str:
    return (
        '<div style="font-family:sans-serif;padding:20px;max-width:600px;">'
        f'<h2 style="color:#00d4aa;">{title}</h2>'
        f"<p>{body}</p>"
        '<hr style="border-color:rgba(255,255,255,0.1);" />'
        '<p style="font-size:12px;color:#64748b;">NafaIQ — Pakistan Stock Exchange Intelligence</p>'
        "</div>"
    )


async def record_event(
    user_id: str,
    alert_id: Optional[int],
    alert_type: str,
    symbol: Optional[str],
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    """Persist the event (always, for history) and deliver it to the channels
    the user has enabled: in-app bell (in_app_alerts) and email (email_alerts).
    """
    # in_app_notifications.kind uses "price_alert"; alert_events uses
    # "stock_price". Map so the CHECK constraint is satisfied.
    kind = "price_alert" if alert_type == "stock_price" else alert_type

    async with connect() as conn:
        prefs = await notifications_repo.get_prefs(conn, user_id)
    in_app = prefs.get("in_app_alerts", True) if prefs else True
    email_on = prefs.get("email_alerts", False) if prefs else False

    async with begin() as conn:
        await repo.insert_alert_event(
            conn, user_id, alert_id, alert_type, symbol, title, body, payload
        )
        if in_app:
            await repo.insert_in_app_notification(conn, user_id, kind, title, body, None)

    if email_on:
        try:
            email = await notifier.get_user_email(user_id)
            if email:
                await notifier.send_email(email, title, _email_html(title, body))
        except Exception:
            log.warning("alert email delivery failed for %s", user_id, exc_info=True)
