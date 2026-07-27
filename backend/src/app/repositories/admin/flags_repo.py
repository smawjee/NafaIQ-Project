"""Platform feature-flag data access. Values are jsonb; typing is validated in
the service layer before write."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def list_flags(conn: Executor) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                "SELECT key, type, value, allowed, enabled, description, "
                "updated_by, updated_at FROM platform_flags ORDER BY key"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def get_flag(conn: Executor, key: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                "SELECT key, type, value, allowed, enabled, description, "
                "updated_by, updated_at FROM platform_flags WHERE key = :k"
            ),
            {"k": key},
        )
    ).mappings().first()
    return dict(row) if row else None


async def update_flag(
    conn: Executor,
    *,
    key: str,
    value: Any,
    enabled: Optional[bool],
    updated_by: Optional[str],
) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                UPDATE platform_flags
                SET value = CAST(:value AS jsonb),
                    enabled = COALESCE(:enabled, enabled),
                    updated_by = :by,
                    updated_at = now()
                WHERE key = :k
                RETURNING key, type, value, allowed, enabled, description,
                          updated_by, updated_at
                """
            ),
            {
                "k": key,
                "value": json.dumps(value),
                "enabled": enabled,
                "by": updated_by,
            },
        )
    ).mappings().first()
    return dict(row) if row else None
