"""User administration: listing, detail, status, tier, notes.

Every mutation validates, authorizes (caller already gated by require_permission
at the route), runs in one transaction, and writes an audit row in that same
transaction so a committed change always has its trail.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.repositories.admin import roles_repo, users_repo
from app.repositories.base import begin, connect
from app.services.admin.audit import write_audit
from app.services.admin.authz import AdminContext, RequestMeta
from app.schemas.admin import (
    AdminNote,
    Page,
    PageMeta,
    RoleAssignmentInfo,
    UserActivity,
    UserDetail,
    UserListItem,
)

log = logging.getLogger(__name__)


async def list_users(
    *,
    query: Optional[str],
    status: Optional[str],
    plan: Optional[str],
    sort: str,
    descending: bool,
    page: int,
    page_size: int,
) -> Page[UserListItem]:
    offset = (page - 1) * page_size
    async with connect() as conn:
        rows, total = await users_repo.list_users(
            conn,
            query=query,
            status=status,
            plan=plan,
            sort=sort,
            descending=descending,
            limit=page_size,
            offset=offset,
        )
    items = [UserListItem(**{**r, "id": str(r["id"])}) for r in rows]
    return Page[UserListItem](
        items=items, meta=PageMeta(page=page, page_size=page_size, total=total)
    )


async def _activity(conn, user_id: str) -> UserActivity:
    """Best-effort counts. Any failure → unavailable, never a fake zero."""
    try:
        counts = await users_repo.activity_counts(conn, user_id)
        return UserActivity(available=True, counts=counts)
    except Exception:
        log.warning("activity_counts failed for %s", user_id, exc_info=True)
        return UserActivity(available=False, counts={})


async def get_user_detail(user_id: str) -> UserDetail:
    async with connect() as conn:
        row = await users_repo.get_user(conn, user_id)
        if not row:
            raise HTTPException(404, "User not found")
        activity = await _activity(conn, user_id)
        roles = await roles_repo.get_active_roles(conn, user_id)
        notes = await users_repo.list_notes(conn, user_id)
    return UserDetail(
        id=str(row["id"]),
        email=row.get("email"),
        display_name=row.get("display_name"),
        plan=row.get("plan") or "Free",
        account_status=row.get("account_status") or "active",
        status_reason=row.get("status_reason"),
        status_changed_at=row.get("status_changed_at"),
        plan_selected_at=row.get("plan_selected_at"),
        created_at=row.get("created_at"),
        last_sign_in_at=row.get("last_sign_in_at"),
        email_confirmed_at=row.get("email_confirmed_at"),
        activity=activity,
        roles=roles,
        notes=[AdminNote(**n) for n in notes],
    )


async def role_history(user_id: str) -> list[RoleAssignmentInfo]:
    async with connect() as conn:
        rows = await roles_repo.assignment_history(conn, user_id)
    return [RoleAssignmentInfo(**r) for r in rows]


async def change_status(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    user_id: str,
    status: str,
    reason: Optional[str],
) -> dict:
    if user_id == actor.user_id and status != "active":
        raise HTTPException(400, "You cannot suspend or restrict your own account")
    async with begin() as conn:
        current = await users_repo.get_user(conn, user_id)
        if not current:
            raise HTTPException(404, "User not found")
        # Protect other admins: only a super_admin may change an admin's status.
        target_roles = await roles_repo.get_active_roles(conn, user_id)
        if target_roles and not actor.is_super_admin:
            raise HTTPException(403, "Only a super admin can change an admin's status")
        before_status = current.get("account_status") or "active"
        updated = await users_repo.set_status(
            conn, user_id=user_id, status=status, reason=reason, changed_by=actor.user_id
        )
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.status",
            resource_type="user",
            resource_id=user_id,
            target_user_id=user_id,
            before={"account_status": before_status},
            after={"account_status": status},
            reason=reason,
            meta=meta,
        )
    return updated or {}


async def change_tier(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    user_id: str,
    plan: str,
    reason: Optional[str],
) -> dict:
    async with begin() as conn:
        current = await users_repo.get_user(conn, user_id)
        if not current:
            raise HTTPException(404, "User not found")
        before_plan = current.get("plan") or "Free"
        updated = await users_repo.set_plan(conn, user_id=user_id, plan=plan)
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.tier",
            resource_type="user",
            resource_id=user_id,
            target_user_id=user_id,
            before={"plan": before_plan},
            after={"plan": plan},
            reason=reason,
            meta=meta,
        )
    return updated or {}


async def add_note(
    *, actor: AdminContext, meta: RequestMeta, user_id: str, note: str
) -> AdminNote:
    async with begin() as conn:
        current = await users_repo.get_user(conn, user_id)
        if not current:
            raise HTTPException(404, "User not found")
        created = await users_repo.add_note(
            conn, user_id=user_id, author_id=actor.user_id, note=note
        )
        await write_audit(
            conn,
            actor=actor,
            action="admin.user.note",
            resource_type="user",
            resource_id=user_id,
            target_user_id=user_id,
            after={"note_id": created["id"]},
            meta=meta,
        )
    return AdminNote(
        id=created["id"], author_id=actor.user_id, note=note, created_at=created["created_at"]
    )
