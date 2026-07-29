"""Finance savings goals: business logic over finance."""
from __future__ import annotations

import importlib
import math
from typing import Any

from fastapi import HTTPException

from app.repositories import finance as repo
from app.repositories.base import begin, connect
from app.schemas.finance import GoalCreate
from app.services.finance._common import as_timestamp
from app.services.notifier import fire_and_forget, notify_activity
from app.services.permissions import check_count_limit

finance_summary = importlib.import_module("app.services.finance.summary")


def _fmt_pkr(value: float) -> str:
    return f"PKR {value:,.0f}"


def _computed_goal_tip(goal: dict[str, Any], monthly_savings: float) -> str:
    if goal.get("ai_tip"):
        return str(goal["ai_tip"])
    target = float(goal.get("target") or 0.0)
    saved = float(goal.get("saved") or 0.0)
    remaining = max(target - saved, 0.0)
    if target <= 0:
        return "Add a target amount to unlock goal guidance."
    progress = round((saved / target) * 100.0)
    if remaining <= 0:
        return f"This goal is fully funded at {progress}%."
    if monthly_savings > 0:
        months = max(math.ceil(remaining / monthly_savings), 1)
        return (
            f"At your current monthly surplus of {_fmt_pkr(monthly_savings)}, "
            f"this goal is about {months} month{'s' if months != 1 else ''} away."
        )
    return (
        f"{_fmt_pkr(remaining)} remaining. Add contributions to build a clearer "
        "timeline for this goal."
    )


async def _monthly_savings(uid: str) -> float:
    try:
        summ = await finance_summary.summary(uid)
        return max(float(summ.savings or 0.0), 0.0)
    except Exception:
        return 0.0


def _with_computed_tip(goal: dict[str, Any], monthly_savings: float) -> dict[str, Any]:
    row = dict(goal)
    row["ai_tip"] = _computed_goal_tip(row, monthly_savings)
    return row


async def list_goals(uid: str) -> list[dict[str, Any]]:
    monthly_savings = await _monthly_savings(uid)
    async with connect() as conn:
        rows = await repo.list_goals(conn, uid)
    return [_with_computed_tip(row, monthly_savings) for row in rows]


async def create_goal(uid: str, body: GoalCreate, user: dict) -> dict[str, Any]:
    monthly_savings = await _monthly_savings(uid)
    async with begin() as conn:
        current = await repo.count_goals(conn, uid)
        check_count_limit(user, feature_key="max_goals", current=current, label="Savings goals")
        row = await repo.insert_goal(
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
    return _with_computed_tip(row, monthly_savings)


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
    return _with_computed_tip(row, await _monthly_savings(uid))


async def delete_goal(uid: str, goal_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_goal(conn, uid, goal_id)
    if deleted is None:
        raise HTTPException(404, "Goal not found")
    return {"deleted": goal_id}
