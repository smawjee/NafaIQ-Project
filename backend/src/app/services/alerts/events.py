"""Alert events: notification-history reads + the event recorder that mirrors
into the in-app notification bell."""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import alerts as repo
from app.repositories.base import begin, connect


async def list_alert_events(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_alert_events(conn, user_id, limit)


async def mark_event_read(user_id: str, event_id: int) -> bool:
    async with begin() as conn:
        return await repo.mark_event_read(conn, user_id, event_id)


async def record_event(
    user_id: str,
    alert_id: Optional[int],
    alert_type: str,
    symbol: Optional[str],
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    """Persist an alert event and mirror it into the notification bell."""
    # in_app_notifications.kind uses "price_alert"; alert_events uses
    # "stock_price". Map so the CHECK constraint is satisfied.
    kind = "price_alert" if alert_type == "stock_price" else alert_type
    async with begin() as conn:
        await repo.insert_alert_event(
            conn, user_id, alert_id, alert_type, symbol, title, body, payload
        )
        await repo.insert_in_app_notification(conn, user_id, kind, title, body, None)
