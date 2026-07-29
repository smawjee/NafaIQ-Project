"""App-level alerts (bill / budget / goal / stock_price) CRUD, plus the shared
list dispatcher for price vs app alerts."""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import alerts as repo
from app.repositories.base import begin, connect


async def list_alerts(user_id: str, alert_type: Optional[str] = None) -> list[dict[str, Any]]:
    async with connect() as conn:
        if alert_type == "price":
            return await repo.list_price_alerts(conn, user_id)
        return await repo.list_user_alerts(conn, user_id)


async def create_user_alert(
    user_id: str,
    alert_type: str,
    title: str,
    meta: Optional[dict[str, Any]] = None,
    enabled: bool = True,
) -> dict[str, Any]:
    async with begin() as conn:
        return await repo.insert_user_alert(conn, user_id, alert_type, title, meta or {}, enabled)


async def toggle_alert(user_id: str, alert_id: int, enabled: bool) -> Optional[dict[str, Any]]:
    async with begin() as conn:
        updated = await repo.toggle_user_alert(conn, user_id, alert_id, enabled)
    if updated is None:
        return None
    return {"id": alert_id, "enabled": enabled}


async def delete_alert(user_id: str, alert_id: int) -> bool:
    async with begin() as conn:
        return await repo.delete_user_alert(conn, user_id, alert_id)
