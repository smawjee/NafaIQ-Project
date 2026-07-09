"""User-scoped finance extensions: zakat settings, history, calculation."""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_user
from app.services import zakat as zakat_service

router = APIRouter(tags=["finance-extended"])


# ---------- Settings ----------


class ZakatSettingsUpdate(BaseModel):
    method: Optional[str] = Field(None, max_length=40)
    custom_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    nisab_source: Optional[str] = Field(None, max_length=20)
    nisab_value_pkr: Optional[float] = Field(None, ge=0)
    include_cash: Optional[bool] = None
    include_investments: Optional[bool] = None
    include_receivables: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)


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


class ZakatCalculateRequest(BaseModel):
    islamic_year: str = Field(..., min_length=1, max_length=10)
    total_assets_pkr: float = Field(..., ge=0)
    total_deductions_pkr: float = Field(0, ge=0)
    nisab_value_pkr: float = Field(..., ge=0)
    rate_pct: float = Field(2.5, ge=0, le=100)
    method: Optional[str] = None
    breakdown: Optional[dict[str, Any]] = None
    save: bool = False


@router.post("/finance/zakat/calculate")
async def calculate(
    body: ZakatCalculateRequest,
    user: Annotated[dict, Depends(require_user)],
):
    """Estimate Zakat. Optionally save the record if save=True."""
    settings = await zakat_service.get_or_create_settings(user["user_id"])
    method = body.method or settings["method"]
    if method == "standard_2_5":
        rate = 2.5
    elif method == "custom_rate":
        rate = settings.get("custom_rate_pct") or body.rate_pct
    else:
        rate = 0.0
    from app.services import calculations as calc

    estimate = calc.zakat_estimate(
        total_assets=body.total_assets_pkr,
        total_deductions=body.total_deductions_pkr,
        nisab_value=body.nisab_value_pkr,
        rate_pct=rate,
    )
    if body.save and rate > 0:
        return await zakat_service.save_record(
            user["user_id"],
            islamic_year=body.islamic_year,
            method=method,
            nisab_value_pkr=body.nisab_value_pkr,
            total_assets_pkr=body.total_assets_pkr,
            total_deductions_pkr=body.total_deductions_pkr,
            rate_pct=rate,
            breakdown=body.breakdown or {},
        )
    return {
        "method": method,
        "rate_pct": rate,
        "islamic_year": body.islamic_year,
        **estimate,
    }
