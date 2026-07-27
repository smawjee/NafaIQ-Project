"""Admin role administration with privilege-escalation guards.

Guardrails:
  * Only a super_admin may assign or revoke the super_admin role.
  * A non-super admin may only grant a role whose permission set is a SUBSET of
    their own — they can never elevate someone above themselves.
  * The last active super_admin can never be revoked.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.repositories.admin import roles_repo, users_repo
from app.repositories.base import begin, connect
from app.services.admin.audit import write_audit
from app.services.admin.authz import SUPER_ADMIN, AdminContext, RequestMeta
from app.schemas.admin import AdminListItem, PermissionInfo, RoleInfo


async def list_roles() -> list[RoleInfo]:
    async with connect() as conn:
        rows = await roles_repo.list_roles(conn)
    return [
        RoleInfo(
            slug=r["slug"],
            name=r["name"],
            description=r.get("description"),
            permissions=list(r.get("permissions") or []),
        )
        for r in rows
    ]


async def list_permissions() -> list[PermissionInfo]:
    async with connect() as conn:
        rows = await roles_repo.list_permissions(conn)
    return [PermissionInfo(**r) for r in rows]


async def list_admins() -> list[AdminListItem]:
    async with connect() as conn:
        rows = await roles_repo.list_admins(conn)
    return [
        AdminListItem(
            user_id=str(r["user_id"]),
            email=r.get("email"),
            roles=list(r.get("roles") or []),
            first_granted_at=r.get("first_granted_at"),
        )
        for r in rows
    ]


async def _role_permission_set(conn, role_slug: str) -> set[str]:
    for role in await roles_repo.list_roles(conn):
        if role["slug"] == role_slug:
            return set(role.get("permissions") or [])
    return set()


async def assign_role(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    user_id: str,
    role_slug: str,
    reason: Optional[str],
) -> dict:
    async with begin() as conn:
        if not await roles_repo.role_exists(conn, role_slug):
            raise HTTPException(404, f"Unknown role: {role_slug}")
        if not await users_repo.get_user(conn, user_id):
            raise HTTPException(404, "User not found")
        if role_slug == SUPER_ADMIN and not actor.is_super_admin:
            raise HTTPException(403, "Only a super admin can grant super_admin")
        # Privilege ceiling: a non-super admin cannot grant permissions they
        # don't themselves hold.
        if not actor.is_super_admin:
            role_perms = await _role_permission_set(conn, role_slug)
            if not role_perms.issubset(actor.permissions):
                raise HTTPException(
                    403, "You cannot grant a role with permissions beyond your own"
                )
        added = await roles_repo.assign_role(
            conn,
            user_id=user_id,
            role_slug=role_slug,
            granted_by=actor.user_id,
            reason=reason,
        )
        await write_audit(
            conn,
            actor=actor,
            action="admin.role.assign",
            resource_type="admin_role_assignment",
            resource_id=role_slug,
            target_user_id=user_id,
            after={"role": role_slug, "added": added},
            reason=reason,
            meta=meta,
        )
    return {"role_slug": role_slug, "granted": added}


async def revoke_role(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    user_id: str,
    role_slug: str,
    reason: Optional[str],
) -> dict:
    async with begin() as conn:
        if role_slug == SUPER_ADMIN:
            if not actor.is_super_admin:
                raise HTTPException(403, "Only a super admin can revoke super_admin")
            if await roles_repo.count_active_super_admins(conn) <= 1:
                raise HTTPException(409, "Cannot revoke the last active super_admin")
        revoked = await roles_repo.revoke_role(
            conn,
            user_id=user_id,
            role_slug=role_slug,
            revoked_by=actor.user_id,
            reason=reason,
        )
        if not revoked:
            raise HTTPException(404, "No active assignment for that role")
        await write_audit(
            conn,
            actor=actor,
            action="admin.role.revoke",
            resource_type="admin_role_assignment",
            resource_id=role_slug,
            target_user_id=user_id,
            before={"role": role_slug},
            reason=reason,
            meta=meta,
        )
    return {"role_slug": role_slug, "revoked": revoked}
