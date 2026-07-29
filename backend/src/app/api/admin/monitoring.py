"""Monitoring routes: market-data, signals, AI, alerts, system health.

All reads except `POST /market-data/refresh`, which is the one operational
action the console can take against the ingestion pipeline.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.services.admin import alerts as alerts_service
from app.services.admin import market_ops, monitoring as monitoring_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)

router = APIRouter()


@router.get("/market-data")
async def market_data(
    _: Annotated[AdminContext, Depends(require_permission("market_data.read"))],
) -> dict[str, Any]:
    return await monitoring_service.market_data()


@router.post("/market-data/refresh")
async def refresh_market_data(
    ctx: Annotated[AdminContext, Depends(require_permission("market_data.refresh"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict[str, Any]:
    """Run the market-watch ingest immediately. Idempotent; audited."""
    return await market_ops.refresh_market_snapshot(actor=ctx, meta=meta)


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


@router.get("/alerts")
async def alerts(
    _: Annotated[AdminContext, Depends(require_permission("alerts.read"))],
) -> dict[str, Any]:
    """Platform-wide alert volume and delivery health (aggregates only)."""
    return await alerts_service.overview()


@router.get("/system")
async def system(
    _: Annotated[AdminContext, Depends(require_permission("system.read"))],
) -> dict[str, Any]:
    return await monitoring_service.system()
