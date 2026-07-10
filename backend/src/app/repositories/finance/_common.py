"""Shared helpers for the finance data-access package."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.orm import get_table
from app.db.sqlalchemy import ensure_reflected

Executor = Any


async def table(name: str):
    await ensure_reflected()
    return get_table(name)


async def count_owned(conn: Executor, table_name: str, uid: str) -> int:
    result = await conn.execute(
        text(f"SELECT COUNT(*) FROM {table_name} WHERE user_id = :uid"), {"uid": uid}
    )
    return int(result.scalar() or 0)
