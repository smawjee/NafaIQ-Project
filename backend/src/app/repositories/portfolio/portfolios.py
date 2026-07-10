"""Portfolio-row data access (psx_portfolios) + ownership/quota checks."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any  # AsyncConnection | AsyncSession — both expose .execute()


async def list_portfolios(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, name, created_at
            FROM psx_portfolios
            WHERE user_id = :uid
            ORDER BY created_at ASC
            """
        ),
        {"uid": user_id},
    )
    return [
        {"id": r["id"], "name": r["name"], "created_at": str(r["created_at"])}
        for r in result.mappings().all()
    ]


async def insert_portfolio(conn: Executor, user_id: str, name: str) -> dict[str, Any]:
    result = await conn.execute(
        text(
            """
            INSERT INTO psx_portfolios (user_id, name)
            VALUES (:uid, :name)
            RETURNING id, name, created_at
            """
        ),
        {"uid": user_id, "name": name},
    )
    row = result.mappings().first()
    return {"id": row["id"], "name": row["name"], "created_at": str(row["created_at"])}


async def is_portfolio_owned(conn: Executor, user_id: str, portfolio_id: int) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
        {"pid": portfolio_id, "uid": user_id},
    )
    return result.first() is not None


async def get_portfolio_name(
    conn: Executor, user_id: str, portfolio_id: int
) -> Optional[str]:
    result = await conn.execute(
        text("SELECT name FROM psx_portfolios WHERE id = :pid AND user_id = :uid"),
        {"pid": portfolio_id, "uid": user_id},
    )
    row = result.mappings().first()
    return row["name"] if row else None


async def first_portfolio_id(conn: Executor, user_id: str) -> Optional[int]:
    result = await conn.execute(
        text(
            "SELECT id FROM psx_portfolios "
            "WHERE user_id = :uid ORDER BY created_at ASC LIMIT 1"
        ),
        {"uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else None


async def count_user_portfolios(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text("SELECT COUNT(*) AS c FROM psx_portfolios WHERE user_id = :uid"),
        {"uid": user_id},
    )
    return int(result.scalar() or 0)
