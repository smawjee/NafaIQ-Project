"""Read-only monitoring routes: market-data, signals, AI, system health."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.services.admin import monitoring as monitoring_service
from app.services.admin.authz import AdminContext, require_permission

router = APIRouter()


@router.get("/market-data")
async def market_data(
    _: Annotated[AdminContext, Depends(require_permission("market_data.read"))],
) -> dict[str, Any]:
    return await monitoring_service.market_data()


@router.get("/signals")
async def signals(
    _: Annotated[AdminContext, Depends(require_permission("signals.read"))],
) -> dict[str, Any]:
    return await monitoring_service.signals()


@router.get("/ai")
async def ai_ops(
    _: Annotated[AdminContext, Depends(require_permission("ai.read"))],
) -> dict[str, Any]:
    return await monitoring_service.ai_ops()


@router.get("/system")
async def system(
    _: Annotated[AdminContext, Depends(require_permission("system.read"))],
) -> dict[str, Any]:
    return await monitoring_service.system()
