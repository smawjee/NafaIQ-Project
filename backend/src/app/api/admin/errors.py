"""Admin views over captured errors and user bug reports."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.repositories import telemetry_repo
from app.repositories.base import begin, connect
from app.services import telemetry
from app.services.admin.audit import write_audit
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Captured errors
# ---------------------------------------------------------------------------


@router.get("/errors")
async def list_errors(
    _: Annotated[AdminContext, Depends(require_permission("errors.read"))],
    status: Optional[str] = Query(None, pattern="^(open|investigating|resolved|ignored)$"),
    source: Optional[str] = Query(None, pattern="^(client|server)$"),
    since: Optional[datetime] = Query(None),
    query: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Error groups, most recently active first."""
    async with connect() as conn:
        items, total = await telemetry_repo.list_error_groups(
            conn,
            status=status,
            source=source,
            since=since,
            query=query,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    return {"items": items, "meta": {"page": page, "page_size": page_size, "total": total}}


@router.get("/errors/summary")
async def errors_summary(
    _: Annotated[AdminContext, Depends(require_permission("errors.read"))],
) -> dict[str, Any]:
    return await telemetry.summary()


@router.get("/errors/{fingerprint}")
async def get_error(
    fingerprint: str,
    _: Annotated[AdminContext, Depends(require_permission("errors.read"))],
) -> dict[str, Any]:
    """One group plus its recent occurrences and who they hit."""
    async with connect() as conn:
        group = await telemetry_repo.get_error_group(conn, fingerprint)
        if not group:
            raise HTTPException(404, "Unknown error group")
        events = await telemetry_repo.list_error_events(conn, fingerprint=fingerprint)
    return {"group": group, "events": events}


class ErrorTriage(BaseModel):
    status: str = Field(..., pattern="^(open|investigating|resolved|ignored)$")
    admin_note: Optional[str] = Field(None, max_length=2000)


@router.patch("/errors/{fingerprint}")
async def triage_error(
    fingerprint: str,
    body: ErrorTriage,
    ctx: Annotated[AdminContext, Depends(require_permission("errors.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict[str, Any]:
    """Set triage state.

    Marking `resolved` is not final: if the same fingerprint is captured again,
    ingest re-opens the group, because an error that recurs was not fixed.
    """
    async with begin() as conn:
        before = await telemetry_repo.get_error_group(conn, fingerprint)
        if not before:
            raise HTTPException(404, "Unknown error group")
        updated = await telemetry_repo.set_error_status(
            conn,
            fingerprint=fingerprint,
            status=body.status,
            admin_note=body.admin_note,
            resolved_by=ctx.user_id,
        )
        await write_audit(
            conn,
            actor=ctx,
            action="admin.error.triage",
            resource_type="app_error_groups",
            resource_id=fingerprint,
            before={"status": before["status"]},
            after={"status": body.status},
            meta=meta,
        )
    return updated or {}


@router.get("/users/{user_id}/errors")
async def user_errors(
    user_id: str,
    _: Annotated[AdminContext, Depends(require_permission("errors.read"))],
) -> list[dict[str, Any]]:
    """Errors a specific user actually hit — answers a support ticket directly."""
    async with connect() as conn:
        return await telemetry_repo.recent_events_for_user(conn, user_id=user_id)


# ---------------------------------------------------------------------------
# Bug reports
# ---------------------------------------------------------------------------


@router.get("/bug-reports")
async def list_bug_reports(
    _: Annotated[AdminContext, Depends(require_permission("support.read"))],
    status: Optional[str] = Query(None, pattern="^(open|investigating|resolved|wont_fix)$"),
    category: Optional[str] = Query(None, pattern="^(bug|data|billing|feature|other)$"),
    query: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    async with connect() as conn:
        items, total = await telemetry_repo.list_bug_reports(
            conn,
            status=status,
            category=category,
            query=query,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    return {"items": items, "meta": {"page": page, "page_size": page_size, "total": total}}


class BugReportTriage(BaseModel):
    status: str = Field(..., pattern="^(open|investigating|resolved|wont_fix)$")
    admin_note: Optional[str] = Field(None, max_length=2000)


@router.patch("/bug-reports/{report_id}")
async def triage_bug_report(
    report_id: int,
    body: BugReportTriage,
    ctx: Annotated[AdminContext, Depends(require_permission("support.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> dict[str, Any]:
    """Update status and/or the note the reporter sees."""
    async with begin() as conn:
        updated = await telemetry_repo.set_bug_report_status(
            conn,
            report_id=report_id,
            status=body.status,
            admin_note=body.admin_note,
            resolved_by=ctx.user_id,
        )
        if not updated:
            raise HTTPException(404, "Unknown bug report")
        await write_audit(
            conn,
            actor=ctx,
            action="admin.bug_report.triage",
            resource_type="bug_reports",
            resource_id=str(report_id),
            after={"status": body.status},
            meta=meta,
        )
    return updated
