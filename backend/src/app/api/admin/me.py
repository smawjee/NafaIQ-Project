"""Who-am-I for the admin surface: the caller's roles + permissions.

Returns 403 for any non-admin (require_admin), which the frontend guard uses to
decide whether to render /admin at all. The server, not this endpoint, is the
authority — every other admin route re-checks its own permission.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.admin.authz import AdminContext, require_admin
from app.schemas.admin import AdminMe

router = APIRouter()


@router.get("/me", response_model=AdminMe)
async def whoami(ctx: Annotated[AdminContext, Depends(require_admin)]) -> AdminMe:
    return AdminMe(
        user_id=ctx.user_id,
        email=ctx.email,
        roles=ctx.roles,
        permissions=sorted(ctx.permissions),
    )
