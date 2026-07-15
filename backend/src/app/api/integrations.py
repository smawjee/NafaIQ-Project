"""Gmail-integration routes: thin HTTP layer over services.email_integrations.

All routes are user-scoped (Supabase JWT via require_user) EXCEPT the OAuth
callback, which Google calls directly with no auth header — it is authenticated
instead by the signed, short-lived `state` it carries. No route ever returns the
stored refresh token.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.api.deps import require_user
from app.services import email_integrations as service

router = APIRouter(tags=["integrations"])


@router.get("/integrations/gmail/connect")
async def connect_gmail(
    user: Annotated[dict, Depends(require_user)],
    platform: str = Query("web", description="web | mobile — where to return after consent"),
):
    """Start the Gmail OAuth flow: returns the Google consent URL to open."""
    return service.start_connect(user["user_id"], platform)


@router.get("/integrations/gmail/callback")
async def gmail_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Google's redirect target (public — authenticated by the signed state).

    Redirects the browser back into the app; for mobile that deep link is what
    closes the auth session.
    """
    target = await service.complete_connect(code, state, error)
    return RedirectResponse(target, status_code=302)


@router.get("/integrations/email")
async def email_status(user: Annotated[dict, Depends(require_user)]):
    """Connection status, or {"connected": false} when no account is linked."""
    status = await service.get_status(user["user_id"])
    if status is None:
        return {"connected": False}
    return {"connected": True, **status}


@router.delete("/integrations/email")
async def disconnect_email(user: Annotated[dict, Depends(require_user)]):
    """Disconnect Gmail, revoke the grant at Google, and purge the token."""
    return await service.disconnect(user["user_id"])


@router.post("/integrations/email/sync")
async def sync_email(user: Annotated[dict, Depends(require_user)]):
    """Poll this account now instead of waiting for the scheduled job."""
    return await service.sync_now(user["user_id"])
