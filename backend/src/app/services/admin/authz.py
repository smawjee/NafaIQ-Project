"""Admin authorization: resolve an authenticated user's admin roles/permissions
from the DB (never from the JWT) and expose FastAPI dependencies that gate
admin routes.

Security notes:
  * Admin status is assignment-based (admin_role_assignments). A normal or demo
    user has no assignment, so `require_admin` denies them — there is no way to
    self-grant from the client because the admin_* tables are RLS-denied to
    anon/authenticated and only ever written through this backend.
  * super_admin implicitly satisfies every permission (belt-and-braces on top of
    the DB seed that already maps every permission to super_admin).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request

from app.api.deps import require_user
from app.repositories.admin import roles_repo
from app.repositories.base import connect

SUPER_ADMIN = "super_admin"


@dataclass
class AdminContext:
    user_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    @property
    def is_admin(self) -> bool:
        return bool(self.roles)

    @property
    def is_super_admin(self) -> bool:
        return SUPER_ADMIN in self.roles

    def has(self, permission: str) -> bool:
        return self.is_super_admin or permission in self.permissions


async def resolve_admin_context(user: dict) -> AdminContext:
    """Build the caller's admin context from active role assignments."""
    ctx = AdminContext(user_id=user["user_id"], email=user.get("email", ""))
    async with connect() as conn:
        rows = await roles_repo.get_context_rows(conn, user["user_id"])
    for row in rows:
        role = row["role_slug"]
        if role not in ctx.roles:
            ctx.roles.append(role)
        perm = row.get("permission_slug")
        if perm:
            ctx.permissions.add(perm)
    return ctx


async def require_admin(user: dict = Depends(require_user)) -> AdminContext:
    """Any admin role. 403 for everyone else (normal users, demo users)."""
    ctx = await resolve_admin_context(user)
    if not ctx.is_admin:
        raise HTTPException(403, "Admin access required")
    return ctx


def require_permission(permission: str):
    """Dependency factory gating a route on a single permission slug."""

    async def _dep(ctx: AdminContext = Depends(require_admin)) -> AdminContext:
        if not ctx.has(permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return ctx

    return _dep


@dataclass
class RequestMeta:
    request_id: str
    ip: str | None


async def request_meta(request: Request) -> RequestMeta:
    """Correlation id + client IP for audit rows. Honors an inbound
    X-Request-ID (e.g. from a proxy) or mints one."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    ip = request.headers.get("X-Forwarded-For")
    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    return RequestMeta(request_id=rid, ip=ip)
