"""Finance savings goals: business logic over finance."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import finance as repo
from app.repositories.base import begin, connect
from app.schemas.finance import GoalCreate
from app.services.finance._common import as_timestamp
from app.services.notifier import fire_and_forget, notify_activity
from app.services.permissions import check_count_limit


async def list_goals(uid: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_goals(conn, uid)


async def create_goal(uid: str, body: GoalCreate, user: dict) -> dict[str, Any]:
    async with begin() as conn:
        current = await repo.count_goals(conn, uid)
        check_count_limit(user, feature_key="max_goals", current=current, label="Savings goals")
        return await repo.insert_goal(
            conn,
            {
                "user_id": uid,
                "emoji": body.emoji,
                "name": body.name.strip(),
                "target": body.target,
                "saved": body.saved,
                "color": body.color,
                "ai_tip": body.ai_tip,
                # target_date is timestamptz in the live schema: store midnight
                # UTC of the chosen date so the calendar date never shifts.
                "target_date": as_timestamp(body.target_date),
            },
        )


async def contribute_goal(uid: str, goal_id: int, amount: float) -> dict[str, Any]:
    if amount <= 0:
        raise HTTPException(400, "Contribution amount must be positive")
    async with begin() as conn:
        row = await repo.contribute_goal(conn, uid, goal_id, amount)
    if not row:
        raise HTTPException(404, "Goal not found")
    saved, target = row["saved"], row["target"]
    pct = (saved / target * 100) if target > 0 else 0.0
    fire_and_forget(
        notify_activity(
            uid,
            "goal",
            f"Contribution added: {row['name']}",
            f"PKR {amount:,.0f} added. You've saved PKR {saved:,.0f} of "
            f"PKR {target:,.0f} ({pct:.0f}%) for {row['name']}.",
        )
    )
    if target > 0 and saved >= target:
        fire_and_forget(
            notify_activity(
                uid,
                "goal_complete",
                f"Goal reached: {row['name']}",
                f"Congratulations — you've fully funded {row['name']} "
                f"(PKR {target:,.0f}).",
            )
        )
    return row


async def delete_goal(uid: str, goal_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_goal(conn, uid, goal_id)
    if deleted is None:
        raise HTTPException(404, "Goal not found")
    return {"deleted": goal_id}
