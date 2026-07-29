"""Admin user management routes (thin)."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.services.admin import user_ops, users as users_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)
from app.schemas.admin import (
    AnonymiseRequest,
    AdminNote,
    NoteCreate,
    Page,
    RoleAssignmentInfo,
    StatusChangeRequest,
    TierChangeRequest,
    UserDetail,
    UserListItem,
)

router = APIRouter()

_SORT_KEYS = {"created_at", "last_sign_in_at", "email", "display_name", "plan", "account_status"}


@router.get("/users", response_model=Page[UserListItem])
async def list_users(
    _: Annotated[AdminContext, Depends(require_permission("users.read"))],
    query: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, pattern="^(active|suspended|restricted)$"),
    plan: Optional[str] = Query(None, pattern="^(Free|Pro|Premium)$"),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[UserListItem]:
    sort_key = sort if sort in _SORT_KEYS else "created_at"
    return await users_service.list_users(
        query=query,
        status=status,
        plan=plan,
        sort=sort_key,
        descending=(order == "desc"),
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: str,
    _: Annotated[AdminContext, Depends(require_permission("users.read"))],
) -> UserDetail:
    return await users_service.get_user_detail(user_id)


@router.get("/users/{user_id}/roles", response_model=list[RoleAssignmentInfo])
async def user_role_history(
    user_id: str,
    _: Annotated[AdminContext, Depends(require_permission("roles.read"))],
) -> list[RoleAssignmentInfo]:
    return await users_service.role_history(user_id)


@router.post("/users/{user_id}/status")
async def change_status(
    user_id: str,
    body: StatusChangeRequest,
    ctx: Annotated[AdminContext, Depends(require_permission("users.suspend"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    return await users_service.change_status(
        actor=ctx, meta=meta, user_id=user_id, status=body.status, reason=body.reason
    )


@router.post("/users/{user_id}/tier")
async def change_tier(
    user_id: str,
    body: TierChangeRequest,
    ctx: Annotated[AdminContext, Depends(require_permission("users.tier.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    return await users_service.change_tier(
        actor=ctx, meta=meta, user_id=user_id, plan=body.plan, reason=body.reason
    )


@router.post("/users/{user_id}/notes", response_model=AdminNote)
async def add_note(
    user_id: str,
    body: NoteCreate,
    ctx: Annotated[AdminContext, Depends(require_permission("users.note"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> AdminNote:
    return await users_service.add_note(
        actor=ctx, meta=meta, user_id=user_id, note=body.note
    )


# ---------------------------------------------------------------------------
# Lifecycle actions (Supabase Auth admin API). See services/admin/user_ops.py —
# recovery links are generated and mailed there, never returned or logged.
# ---------------------------------------------------------------------------


@router.post("/users/{user_id}/sign-out")
async def force_sign_out(
    user_id: str,
    ctx: Annotated[AdminContext, Depends(require_permission("users.suspend"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    """Revoke every active session. Suspension blocks the next request; this
    invalidates the refresh tokens so no new access token can be minted."""
    return await user_ops.force_sign_out(actor=ctx, meta=meta, user_id=user_id)


@router.post("/users/{user_id}/password-reset")
async def send_password_reset(
    user_id: str,
    ctx: Annotated[AdminContext, Depends(require_permission("users.suspend"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    """Send the account holder their own recovery email.

    Returns a status only. The recovery URL is never returned to the caller —
    doing so would make this an account-takeover primitive.
    """
    return await user_ops.send_password_reset(actor=ctx, meta=meta, user_id=user_id)


@router.post("/users/{user_id}/resend-verification")
async def resend_verification(
    user_id: str,
    ctx: Annotated[AdminContext, Depends(require_permission("users.suspend"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    """Re-send the sign-up confirmation mail. 409s if already confirmed."""
    return await user_ops.resend_verification(actor=ctx, meta=meta, user_id=user_id)


@router.post("/users/{user_id}/anonymise")
async def anonymise_user(
    user_id: str,
    body: AnonymiseRequest,
    ctx: Annotated[AdminContext, Depends(require_permission("users.anonymise"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict:
    """Irreversibly scrub personal data, keeping portfolio/finance records.

    Gated on `users.anonymise`, which the migration grants to super_admin only.
    """
    return await user_ops.anonymise(
        actor=ctx, meta=meta, user_id=user_id, reason=body.reason
    )

