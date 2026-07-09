"""User-scoped finance extensions: zakat settings, history, calculation.

Thin HTTP layer over services.zakat.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_user
from app.schemas.zakat import ZakatCalculateRequest, ZakatSettingsUpdate
from app.services import zakat as zakat_service

router = APIRouter(tags=["finance-extended"])


# ---------- Settings ----------


@router.get("/finance/zakat/settings")
async def get_settings(user: Annotated[dict, Depends(require_user)]):
    return await zakat_service.get_or_create_settings(user["user_id"])


@router.patch("/finance/zakat/settings")
async def update_settings(
    body: ZakatSettingsUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    updates = body.model_dump(exclude_unset=True)
    if updates.get("method") and updates["method"] not in (
        "standard_2_5",
        "custom_rate",
        "manual_only",
    ):
        raise HTTPException(400, "invalid method")
    if updates.get("nisab_source") and updates["nisab_source"] not in (
        "gold",
        "silver",
        "cash",
        "manual",
    ):
        raise HTTPException(400, "invalid nisab_source")
    return await zakat_service.update_settings(user["user_id"], updates)


# ---------- History ----------


@router.get("/finance/zakat/history")
async def history(
    user: Annotated[dict, Depends(require_user)],
    limit: int = 20,
):
    return await zakat_service.list_records(user["user_id"], limit=limit)


# ---------- Calculate ----------


@router.post("/finance/zakat/calculate")
async def calculate(
    body: ZakatCalculateRequest,
    user: Annotated[dict, Depends(require_user)],
):
    """Estimate Zakat. Optionally save the record if save=True."""
    return await zakat_service.estimate(
        user["user_id"],
        islamic_year=body.islamic_year,
        total_assets_pkr=body.total_assets_pkr,
        total_deductions_pkr=body.total_deductions_pkr,
        nisab_value_pkr=body.nisab_value_pkr,
        rate_pct=body.rate_pct,
        method=body.method,
        breakdown=body.breakdown,
        save=body.save,
    )
