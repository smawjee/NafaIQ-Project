"""Finance savings-goals data access (user_goals)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, insert, select, text, update

from app.repositories.finance._common import count_owned, table

Executor = Any


def _goal(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["user_id"]),
        "emoji": row["emoji"],
        "name": row["name"],
        "target": float(row["target"]),
        "saved": float(row["saved"]),
        "color": row["color"],
        "ai_tip": row["ai_tip"],
        "target_date": str(row["target_date"])[:10] if row["target_date"] else None,
        "created_at": str(row["created_at"]),
    }


async def count_goals(conn: Executor, uid: str) -> int:
    return await count_owned(conn, "user_goals", uid)


async def list_goals(conn: Executor, uid: str) -> list[dict[str, Any]]:
    goals = await table("user_goals")
    result = await conn.execute(
        select(goals).where(goals.c.user_id == uid).order_by(goals.c.created_at.desc())
    )
    return [_goal(r) for r in result.mappings().all()]


async def insert_goal(conn: Executor, values: dict[str, Any]) -> dict[str, Any]:
    goals = await table("user_goals")
    result = await conn.execute(insert(goals).values(**values).returning(goals))
    return _goal(result.mappings().first())


async def contribute_goal(
    conn: Executor, uid: str, goal_id: int, amount: float
) -> Optional[dict[str, Any]]:
    goals = await table("user_goals")
    result = await conn.execute(
        update(goals)
        .where(goals.c.id == goal_id, goals.c.user_id == uid)
        .values(saved=text("LEAST(saved + :amount, target)"))
        .returning(goals),
        {"amount": amount},
    )
    row = result.mappings().first()
    return _goal(row) if row else None


async def delete_goal(conn: Executor, uid: str, goal_id: int) -> Optional[int]:
    goals = await table("user_goals")
    result = await conn.execute(
        delete(goals).where(goals.c.id == goal_id, goals.c.user_id == uid).returning(goals.c.id)
    )
    row = result.first()
    return goal_id if row else None
