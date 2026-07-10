"""Stock price alerts CRUD."""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import alerts as repo
from app.repositories.base import begin
from app.services.permissions import check_count_limit


async def create_price_alert(
    user: dict,
    symbol: str,
    condition: str,
    price: float,
    *,
    one_time: bool = True,
    notify_push: bool = False,
    notify_email: bool = True,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    if condition not in ("above", "below", "cross_above", "cross_below"):
        raise ValueError("invalid condition")
    if price < 0:
        raise ValueError("price must be >= 0")
    user_id = user["user_id"]
    async with begin() as conn:
        # Idempotent: re-arming an identical active alert returns the existing
        # row instead of creating a duplicate.
        existing = await repo.find_active_price_alert(conn, user_id, symbol, condition, price)
        if existing is not None:
            return existing
        current = await repo.count_price_alerts(conn, user_id)
        check_count_limit(user, feature_key="max_price_alerts", current=current, label="Price alerts")
        return await repo.insert_price_alert(
            conn, user_id, symbol, condition, price, one_time, notify_push, notify_email, notes
        )


async def delete_price_alert(user_id: str, alert_id: int) -> bool:
    async with begin() as conn:
        deleted = await repo.delete_price_alert(conn, user_id, alert_id)
    return deleted is not None
