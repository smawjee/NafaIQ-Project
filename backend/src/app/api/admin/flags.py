"""Platform feature-flag routes (thin)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.admin import flags as flags_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)
from app.schemas.admin import FlagInfo, FlagUpdate

router = APIRouter()


@router.get("/flags", response_model=list[FlagInfo])
async def list_flags(
    _: Annotated[AdminContext, Depends(require_permission("flags.read"))],
) -> list[FlagInfo]:
    return await flags_service.list_flags()


@router.put("/flags/{key}", response_model=FlagInfo)
async def update_flag(
    key: str,
    body: FlagUpdate,
    ctx: Annotated[AdminContext, Depends(require_permission("flags.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> FlagInfo:
    return await flags_service.update_flag(
        actor=ctx,
        meta=meta,
        key=key,
        value=body.value,
        enabled=body.enabled,
        reason=body.reason,
    )
