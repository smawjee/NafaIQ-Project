"""Audit log routes (read-only, thin)."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.services.admin import audit as audit_service
from app.services.admin.authz import AdminContext, require_permission
from app.schemas.admin import AuditEntry, Page

router = APIRouter()


@router.get("/audit", response_model=Page[AuditEntry])
async def list_audit(
    _: Annotated[AdminContext, Depends(require_permission("audit.read"))],
    action: Optional[str] = Query(None, max_length=100),
    actor_user_id: Optional[str] = Query(None, max_length=64),
    target_user_id: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None, pattern="^(success|failure)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[AuditEntry]:
    return await audit_service.list_audit(
        action=action,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        status=status,
        page=page,
        page_size=page_size,
    )
