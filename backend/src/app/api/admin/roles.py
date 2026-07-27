"""Admin roles & permissions routes (thin)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.admin import roles as roles_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)
from app.schemas.admin import (
    AdminListItem,
    PermissionInfo,
    RoleGrantRequest,
    RoleInfo,
)

router = APIRouter()


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(
    _: Annotated[AdminContext, Depends(require_permission("roles.read"))],
) -> list[RoleInfo]:
    return await roles_service.list_roles()


@router.get("/permissions", response_model=list[PermissionInfo])
async def list_permissions(
    _: Annotated[AdminContext, Depends(require_permission("roles.read"))],
) -> list[PermissionInfo]:
    return await roles_service.list_permissions()


@router.get("/admins", response_model=list[AdminListItem])
async def list_admins(
    _: Annotated[AdminContext, Depends(require_permission("roles.read"))],
) -> list[AdminListItem]:
    return await roles_service.list_admins()


@router.post("/users/{user_id}/roles")
async def assign_role(
    user_id: str,
    body: RoleGrantRequest,
    ctx: Annotated[AdminContext, Depends(require_permission("roles.assign"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    return await roles_service.assign_role(
        actor=ctx, meta=meta, user_id=user_id, role_slug=body.role_slug, reason=body.reason
    )


@router.delete("/users/{user_id}/roles/{role_slug}")
async def revoke_role(
    user_id: str,
    role_slug: str,
    ctx: Annotated[AdminContext, Depends(require_permission("roles.revoke"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    return await roles_service.revoke_role(
        actor=ctx, meta=meta, user_id=user_id, role_slug=role_slug, reason=None
    )
