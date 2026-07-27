"""Admin overview dashboard."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.services.admin import overview as overview_service
from app.services.admin.authz import AdminContext, require_permission
from app.schemas.admin import OverviewResponse

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    _: Annotated[AdminContext, Depends(require_permission("overview.read"))],
) -> OverviewResponse:
    return await overview_service.build_overview()
