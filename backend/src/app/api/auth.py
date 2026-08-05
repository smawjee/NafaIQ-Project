"""Unauthenticated account-recovery endpoints.

`/api/auth/forgot-password` is deliberately open — a user who has forgotten their
password has, by definition, no credential to present. It is constrained instead:
a per-IP rate limit, a per-mailbox cap in the service, and a fixed 202 that says
nothing about whether the address is registered.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.middleware.rate_limit import limiter
from app.services import auth_recovery
from app.services.notifier import fire_and_forget

router = APIRouter(tags=["auth"])


class ForgotPasswordRequest(BaseModel):
    # Pydantic's EmailStr would pull in email-validator, which is not a
    # dependency of this service. The shape check below is all this endpoint
    # needs — the address is only ever handed to Supabase and the mail provider.
    email: str = Field(..., max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    lang: Literal["en", "ur"] = "en"


@router.post("/auth/forgot-password", status_code=202)
@limiter.limit("5/hour")
async def forgot_password(body: ForgotPasswordRequest, request: Request) -> dict:
    """Mail a recovery code, if the address belongs to an account.

    Always 202, and always immediately: the send runs detached so the response
    time cannot be used to tell a registered address from an unregistered one.
    """
    fire_and_forget(auth_recovery.send_recovery_code(body.email, body.lang))
    return {"status": "sent"}
