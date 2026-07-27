"""Audit log data access. INSERT-only writes; the DB trigger blocks UPDATE/DELETE."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

Executor = Any


def _jsonb(value: Any) -> Optional[str]:
    """Serialize a dict/list to a JSON string for a jsonb bind, or None."""
    if value is None:
        return None
    return json.dumps(value, default=str)


async def insert(
    conn: Executor,
    *,
    actor_user_id: Optional[str],
    actor_email: Optional[str],
    actor_roles: list[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
    status: str = "success",
) -> int:
    row = await conn.execute(
        text(
            """
            INSERT INTO admin_audit_log
                (actor_user_id, actor_email, actor_roles, action, resource_type,
                 resource_id, target_user_id, before, after, reason, request_id, ip, status)
            VALUES
                (:actor_user_id, :actor_email, :actor_roles, :action, :resource_type,
                 :resource_id, :target_user_id, CAST(:before AS jsonb), CAST(:after AS jsonb),
                 :reason, :request_id, :ip, :status)
            RETURNING id
            """
        ),
        {
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "actor_roles": actor_roles,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "target_user_id": target_user_id,
            "before": _jsonb(before),
            "after": _jsonb(after),
            "reason": reason,
            "request_id": request_id,
            "ip": ip,
            "status": status,
        },
    )
    return int(row.scalar())


async def query(
    conn: Executor,
    *,
    action: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Filtered, paginated audit rows (newest first) + total count.

    Filters are bound parameters (never string-interpolated). Sort is fixed to
    created_at DESC — the audit log has one meaningful order.
    """
    where = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if action:
        where.append("action = :action")
        params["action"] = action
    if actor_user_id:
        where.append("actor_user_id = :actor_user_id")
        params["actor_user_id"] = actor_user_id
    if target_user_id:
        where.append("target_user_id = :target_user_id")
        params["target_user_id"] = target_user_id
    if status:
        where.append("status = :status")
        params["status"] = status
    clause = " AND ".join(where)

    total = (
        await conn.execute(
            text(f"SELECT count(*) FROM admin_audit_log WHERE {clause}"), params
        )
    ).scalar() or 0

    rows = (
        await conn.execute(
            text(
                f"""
                SELECT id, actor_user_id, actor_email, actor_roles, action,
                       resource_type, resource_id, target_user_id, before, after,
                       reason, request_id, ip, status, created_at
                FROM admin_audit_log
                WHERE {clause}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


async def recent_for_overview(conn: Executor, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT id, actor_email, action, resource_type, target_user_id,
                       status, created_at
                FROM admin_audit_log
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()
    return [dict(r) for r in rows]
