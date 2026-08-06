"""Broker confirmation import API."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_user
from app.services import broker_imports as service

router = APIRouter(tags=["broker-imports"])


class BrokerImportApprove(BaseModel):
    portfolio_id: int = Field(..., gt=0)
    enable_auto: bool = False


class BrokerAccountPatch(BaseModel):
    mapped_portfolio_id: Optional[int] = Field(None, gt=0)
    mode: Optional[str] = Field(None, pattern="^(review|auto)$")


@router.get("/portfolio/broker-imports")
async def list_broker_imports(
    user: Annotated[dict, Depends(require_user)],
    status: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[int] = None,
):
    return await service.list_imports(
        user["user_id"], status=status, limit=limit, cursor=cursor
    )


@router.get("/portfolio/broker-imports/{import_id}")
async def get_broker_import(
    import_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    return await service.get_import(user["user_id"], import_id)


@router.post("/portfolio/broker-imports/{import_id}/approve")
async def approve_broker_import(
    import_id: int,
    body: BrokerImportApprove,
    user: Annotated[dict, Depends(require_user)],
):
    return await service.approve_import(
        user=user,
        import_id=import_id,
        portfolio_id=body.portfolio_id,
        enable_auto=body.enable_auto,
    )


@router.post("/portfolio/broker-imports/{import_id}/reject")
async def reject_broker_import(
    import_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    return await service.reject_import(user["user_id"], import_id)


@router.post("/portfolio/broker-imports/{import_id}/reprocess")
async def reprocess_broker_import(
    import_id: int,
    user: Annotated[dict, Depends(require_user)],
):
    # The raw PDF is intentionally not retained. Reprocessing is driven by the
    # next Gmail sync, which can refetch the attachment while the grant exists.
    return await service.get_import(user["user_id"], import_id)


@router.get("/portfolio/broker-accounts")
async def list_broker_accounts(user: Annotated[dict, Depends(require_user)]):
    return await service.list_accounts(user["user_id"])


@router.patch("/portfolio/broker-accounts/{account_id}")
async def patch_broker_account(
    account_id: int,
    body: BrokerAccountPatch,
    user: Annotated[dict, Depends(require_user)],
):
    return await service.update_account(
        user["user_id"], account_id, body.model_dump(exclude_unset=True)
    )
