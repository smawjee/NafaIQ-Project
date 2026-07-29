"""Shared helpers for the finance data-access package."""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, text

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


async def delete_all_rows(conn: Executor, table_name: str, uid: str) -> int:
    """Delete EVERY row this user owns in `table_name`; returns the count.

    Scoped to `user_id = uid`, so a user can only ever clear their own data.
    `table_name` comes from a fixed service-side whitelist, never raw request
    input (it is interpolated into the reflected-table lookup)."""
    t = await table(table_name)
    result = await conn.execute(
        delete(t).where(t.c.user_id == uid).returning(t.c.id)
    )
    return len(result.fetchall())
