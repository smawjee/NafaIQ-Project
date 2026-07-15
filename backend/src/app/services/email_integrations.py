"""Gmail-integration business logic (connect / callback / status / sync).

The OAuth dance is owned by the backend end-to-end: the client only ever sees an
auth URL and, later, a status row. The refresh token never leaves this layer.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import HTTPException

from app.config import settings
from app.repositories import email_integrations as repo
from app.repositories.base import begin, connect
from app.services.crypto import CryptoError, decrypt, encrypt
from app.services.email_import import (
    OAuthError,
    build_auth_url,
    exchange_code,
    fetch_google_email,
    parse_state,
    revoke,
    sync_user,
)

log = logging.getLogger(__name__)

_VALID_PLATFORMS = ("web", "mobile")


def _require_enabled() -> None:
    if not settings.email_import_configured:
        raise HTTPException(
            503,
            "Gmail import is not configured on this server (needs "
            "EMAIL_IMPORT_ENABLED, EMAIL_CRED_ENC_KEY, GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET).",
        )


def start_connect(user_id: str, platform: str) -> dict[str, str]:
    """Return the Google consent URL for this user."""
    _require_enabled()
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(400, f"platform must be one of {_VALID_PLATFORMS}")
    return {"auth_url": build_auth_url(user_id, platform)}  # type: ignore[arg-type]


def _redirect_target(platform: str, status: str) -> str:
    """Where to send the browser after the callback.

    Mobile gets a deep link, which is what closes the in-app auth session and
    returns control to the app (same mechanism as Google sign-in).
    """
    if platform == "mobile":
        return f"nafaiqmobile://settings?gmail={status}"
    return f"{settings.web_app_origin.rstrip('/')}/settings?gmail={status}"


async def complete_connect(code: Optional[str], state: Optional[str], error: Optional[str]) -> str:
    """Handle Google's redirect. Returns the URL to redirect the browser to.

    Never raises for user-facing failures — the user is in a browser, so we send
    them back to the app with ?gmail=error rather than showing a JSON 500.
    """
    if not state:
        raise HTTPException(400, "Missing state")
    try:
        payload = parse_state(state)
    except CryptoError as e:
        # Forged/expired state — do not trust anything else in this request.
        raise HTTPException(400, f"Invalid state: {e}")

    platform = payload.get("platform", "web")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(400, "Invalid state payload")

    if error or not code:
        # User hit "Cancel" on the consent screen.
        log.info("gmail consent aborted for %s: %s", user_id, error or "no code")
        return _redirect_target(platform, "cancelled")

    try:
        tokens = await exchange_code(code)
    except OAuthError as e:
        log.warning("gmail code exchange failed for %s: %s", user_id, e)
        return _redirect_target(platform, "error")

    access_token = tokens.get("access_token", "")
    google_email = await fetch_google_email(access_token) or "Gmail account"

    try:
        token_enc = encrypt(tokens["refresh_token"])
    except CryptoError as e:
        log.error("failed to encrypt refresh token: %s", e)
        return _redirect_target(platform, "error")

    async with begin() as conn:
        await repo.upsert_integration(
            conn,
            user_id,
            google_email=google_email,
            refresh_token_enc=token_enc,
            scope=tokens.get("scope"),
        )
    log.info("gmail connected for %s (%s)", user_id, google_email)
    return _redirect_target(platform, "connected")


async def get_status(user_id: str) -> Optional[dict[str, Any]]:
    """Connection status, or None when not connected. Never the token."""
    async with connect() as conn:
        return await repo.get_status(conn, user_id)


async def disconnect(user_id: str) -> dict[str, Any]:
    """Purge the stored grant and revoke it at Google (best effort)."""
    async with connect() as conn:
        integration = await repo.get_with_token(conn, user_id)
    if not integration:
        raise HTTPException(404, "No Gmail account connected")

    # Revoke first so access ends now rather than when the token lapses; a
    # failure here must not block the user from disconnecting locally.
    try:
        await revoke(decrypt(integration["refresh_token_enc"]))
    except CryptoError:
        pass

    async with begin() as conn:
        await repo.delete_integration(conn, user_id)
    return {"disconnected": True}


async def sync_now(user_id: str) -> dict[str, Any]:
    """Poll this user's Gmail immediately, rather than waiting for the job."""
    _require_enabled()
    async with connect() as conn:
        integration = await repo.get_with_token(conn, user_id)
    if not integration:
        raise HTTPException(404, "No Gmail account connected")
    if not integration["enabled"]:
        raise HTTPException(
            400, "Gmail access has expired — please reconnect your account."
        )

    result = await sync_user(integration)
    if result.reconnect_required:
        raise HTTPException(
            400, "Gmail access has expired — please reconnect your account."
        )
    return {
        "scanned": result.scanned,
        "candidates": result.candidates,
        "imported": result.imported,
        "duplicates": result.duplicates,
        "skipped": result.skipped,
    }
