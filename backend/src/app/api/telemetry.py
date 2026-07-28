"""User-facing telemetry: error capture and bug reports.

`/api/telemetry/errors` is deliberately open to unauthenticated callers — a
crash on the sign-in screen is exactly the kind of failure nobody currently
hears about. It is heavily constrained instead: bounded payload, per-caller rate
limit, redaction on the way in, and it never returns anything an attacker could
use to probe the system.

Bug reports require a session, because a report you can't reply to is not worth
storing.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import require_user
from app.repositories import telemetry_repo
from app.repositories.base import begin, connect
from app.services import telemetry

router = APIRouter(tags=["telemetry"])


class ErrorReport(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    stack: Optional[str] = Field(None, max_length=20000)
    route: Optional[str] = Field(None, max_length=500)
    app_version: Optional[str] = Field(None, max_length=60)


@router.post("/telemetry/errors", status_code=202)
async def report_error(body: ErrorReport, request: Request) -> dict:
    """Record a client-side error.

    202 with a bare acknowledgement whether or not the event was stored: the
    browser can do nothing useful with the difference, and a caller must not be
    able to distinguish "accepted" from "rate-limited" and tune around it.
    """
    user = getattr(request.state, "user", None)
    user_id = user.get("user_id") if isinstance(user, dict) else None

    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host

    await telemetry.capture_error(
        source="client",
        message=body.message,
        stack=body.stack,
        route=body.route,
        user_id=user_id,
        app_version=body.app_version,
        user_agent=request.headers.get("User-Agent"),
        client_key=user_id or client_ip or "anonymous",
    )
    return {"status": "accepted"}


class BugReportCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    category: str = Field("bug", pattern="^(bug|data|billing|feature|other)$")
    route: Optional[str] = Field(None, max_length=500)
    app_version: Optional[str] = Field(None, max_length=60)
    # Set when filing from an error screen, linking the human account of a
    # failure to its machine capture.
    error_fingerprint: Optional[str] = Field(None, max_length=64)


@router.post("/support/bug-reports", status_code=201)
async def create_bug_report(
    body: BugReportCreate,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
) -> dict:
    """File a bug report against the caller's own account."""
    async with begin() as conn:
        return await telemetry_repo.create_bug_report(
            conn,
            user_id=user["user_id"],
            title=body.title.strip(),
            description=body.description.strip(),
            category=body.category,
            route=body.route,
            app_version=body.app_version,
            user_agent=request.headers.get("User-Agent"),
            error_fingerprint=body.error_fingerprint,
        )


@router.get("/support/bug-reports")
async def list_my_bug_reports(user: Annotated[dict, Depends(require_user)]) -> list[dict]:
    """The caller's own reports, so they can see what happened to them."""
    async with connect() as conn:
        return await telemetry_repo.list_own_bug_reports(conn, user_id=user["user_id"])
