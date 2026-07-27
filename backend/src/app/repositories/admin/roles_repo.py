"""Admin RBAC data access: role assignments, role/permission catalog.

active assignment = revoked_at IS NULL. Revoked rows are retained for history.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def get_context_rows(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    """Rows of (role_slug, permission_slug) for a user's ACTIVE assignments.

    A role with no permissions still yields one row (permission_slug NULL) so
    the caller can see the role even before permissions are mapped.
    """
    rows = (
        await conn.execute(
            text(
                """
                SELECT ara.role_slug, arp.permission_slug
                FROM admin_role_assignments ara
                LEFT JOIN admin_role_permissions arp
                       ON arp.role_slug = ara.role_slug
                WHERE ara.user_id = :uid AND ara.revoked_at IS NULL
                """
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def list_roles(conn: Executor) -> list[dict[str, Any]]:
    """All roles with their mapped permission slugs (aggregated)."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT r.slug, r.name, r.description,
                       COALESCE(
                           array_agg(rp.permission_slug ORDER BY rp.permission_slug)
                           FILTER (WHERE rp.permission_slug IS NOT NULL),
                           '{}'
                       ) AS permissions
                FROM admin_roles r
                LEFT JOIN admin_role_permissions rp ON rp.role_slug = r.slug
                GROUP BY r.slug, r.name, r.description
                ORDER BY r.slug
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def list_permissions(conn: Executor) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text("SELECT slug, description FROM admin_permissions ORDER BY slug")
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def role_exists(conn: Executor, role_slug: str) -> bool:
    row = await conn.execute(
        text("SELECT 1 FROM admin_roles WHERE slug = :s"), {"s": role_slug}
    )
    return row.first() is not None


async def get_active_roles(conn: Executor, user_id: str) -> list[str]:
    rows = (
        await conn.execute(
            text(
                "SELECT role_slug FROM admin_role_assignments "
                "WHERE user_id = :uid AND revoked_at IS NULL ORDER BY role_slug"
            ),
            {"uid": user_id},
        )
    ).all()
    return [r[0] for r in rows]


async def list_admins(conn: Executor) -> list[dict[str, Any]]:
    """Every user holding at least one active admin role, with their roles."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT ara.user_id,
                       u.email,
                       array_agg(ara.role_slug ORDER BY ara.role_slug) AS roles,
                       min(ara.granted_at) AS first_granted_at
                FROM admin_role_assignments ara
                LEFT JOIN auth.users u ON u.id = ara.user_id
                WHERE ara.revoked_at IS NULL
                GROUP BY ara.user_id, u.email
                ORDER BY min(ara.granted_at)
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def assignment_history(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT id, role_slug, granted_by, granted_at,
                       revoked_at, revoked_by, reason
                FROM admin_role_assignments
                WHERE user_id = :uid
                ORDER BY granted_at DESC
                """
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def count_active_super_admins(conn: Executor) -> int:
    row = await conn.execute(
        text(
            "SELECT count(*) FROM admin_role_assignments "
            "WHERE role_slug = 'super_admin' AND revoked_at IS NULL"
        )
    )
    return int(row.scalar() or 0)


async def assign_role(
    conn: Executor,
    *,
    user_id: str,
    role_slug: str,
    granted_by: Optional[str],
    reason: Optional[str],
) -> bool:
    """Grant a role. Idempotent: the active-partial unique index makes a repeat
    grant a no-op (ON CONFLICT DO NOTHING). Returns True if a new row was added.
    """
    row = await conn.execute(
        text(
            """
            INSERT INTO admin_role_assignments (user_id, role_slug, granted_by, reason)
            VALUES (:uid, :role, :by, :reason)
            ON CONFLICT (user_id, role_slug) WHERE revoked_at IS NULL DO NOTHING
            RETURNING id
            """
        ),
        {"uid": user_id, "role": role_slug, "by": granted_by, "reason": reason},
    )
    return row.first() is not None


async def revoke_role(
    conn: Executor,
    *,
    user_id: str,
    role_slug: str,
    revoked_by: Optional[str],
    reason: Optional[str],
) -> bool:
    """Revoke a user's active role. Returns True if an active row was revoked."""
    row = await conn.execute(
        text(
            """
            UPDATE admin_role_assignments
            SET revoked_at = now(), revoked_by = :by, reason = COALESCE(:reason, reason)
            WHERE user_id = :uid AND role_slug = :role AND revoked_at IS NULL
            RETURNING id
            """
        ),
        {"uid": user_id, "role": role_slug, "by": revoked_by, "reason": reason},
    )
    return row.first() is not None
