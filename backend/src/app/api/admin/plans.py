"""Plan entitlement routes.

`plan_features` is read on the request path and enforces real quotas, so writes
here are gated on `subscriptions.write` and audited with a before/after diff.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.schemas.admin import PlanUpdate
from app.services.admin import plans as plans_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)

router = APIRouter()


@router.get("/plans")
async def list_plans(
    _: Annotated[AdminContext, Depends(require_permission("subscriptions.read"))],
) -> list[dict[str, Any]]:
    """Every plan and its entitlements, cheapest first."""
    return await plans_service.list_plans()


@router.put("/plans/{plan}")
async def update_plan(
    plan: str,
    body: PlanUpdate,
    ctx: Annotated[AdminContext, Depends(require_permission("subscriptions.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict[str, Any]:
    """Partial update. Only fields present in the body are touched.

    `exclude_unset` is what makes this a true PATCH-style merge: a field the
    client never sent is left alone, while a field explicitly sent as null is
    applied (which is meaningful for the "unlimited" quota columns).
    """
    changes = body.model_dump(exclude_unset=True)
    changes.pop("reason", None)
    return await plans_service.update_plan(
        actor=ctx,
        meta=meta,
        plan=plan,
        changes=changes,
        reason=body.reason,
    )
