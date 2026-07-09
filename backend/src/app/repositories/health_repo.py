"""Health data access: a trivial DB liveness probe."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.sqlalchemy import ensure_reflected

Executor = Any


async def ping(conn: Executor) -> None:
    await ensure_reflected()
    await conn.execute(text("SELECT 1"))
