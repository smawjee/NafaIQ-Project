"""Gmail-integration business logic (connect / callback / status / sync).

The OAuth dance is owned by the backend end-to-end: the client only ever sees an
auth URL and, later, a status row. The refresh token never leaves this layer.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException

from app.config import settings
from app.repositories import email_import_messages as ledger_repo
from app.repositories import email_integrations as repo
from app.repositories.base import begin, connect
from app.services.crypto import CryptoError, decrypt, encrypt
from app.services import broker_imports
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
# Schemes an Expo client may legitimately ask us to redirect back to: the app's
# own custom scheme (dev-client / standalone) and Expo Go's proxy schemes.
_MOBILE_REDIRECT_SCHEMES = ("nafaiqmobile", "exp", "exps")


def _validate_mobile_redirect(redirect: Optional[str]) -> Optional[str]:
    """Return the redirect if its scheme is allowlisted, else raise 400.

    Guards the public callback against open-redirect: a caller can only steer the
    post-consent bounce to an app/Expo deep link, never to an arbitrary origin.
    None is allowed — the caller falls back to the default deep link.
    """
    if not redirect:
        return None
    scheme = urlsplit(redirect).scheme.lower()
    if scheme not in _MOBILE_REDIRECT_SCHEMES:
        raise HTTPException(400, f"redirect scheme must be one of {_MOBILE_REDIRECT_SCHEMES}")
    return redirect


def _with_gmail_status(url: str, status: str) -> str:
    """Append `gmail=<status>` to a redirect URL, preserving any existing query
    and path (Expo Go `exp://…/--/settings` URLs may already carry both)."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("gmail", status))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _require_enabled() -> None:
    if not settings.email_import_configured:
        raise HTTPException(
            503,
            "Gmail import is not configured on this server (needs "
            "EMAIL_IMPORT_ENABLED, EMAIL_CRED_ENC_KEY, GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET).",
        )


def start_connect(user_id: str, platform: str, redirect: Optional[str] = None) -> dict[str, str]:
    """Return the Google consent URL for this user.

    `redirect` (mobile only) is the client's own deep link — an Expo Go `exp://`
    session URL or a native `nafaiqmobile://` URL — so the post-consent bounce
    lands wherever the client is actually listening. It is scheme-validated here
    and carried inside the signed state (see build_auth_url).
    """
    _require_enabled()
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(400, f"platform must be one of {_VALID_PLATFORMS}")
    validated = _validate_mobile_redirect(redirect) if platform == "mobile" else None
    return {"auth_url": build_auth_url(user_id, platform, validated)}  # type: ignore[arg-type]


def _redirect_target(platform: str, status: str, redirect: Optional[str] = None) -> str:
    """Where to send the browser after the callback.

    Mobile gets a deep link, which is what closes the in-app auth session and
    returns control to the app (same mechanism as Google sign-in). A validated
    client-supplied `redirect` (from the signed state) wins so Expo Go works;
    otherwise fall back to the app's custom scheme (native builds).
    """
    if platform == "mobile":
        return _with_gmail_status(redirect or "nafaiqmobile://settings", status)
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

    # The redirect was validated at connect time and signed into the state; the
    # state is Fernet-encrypted + TTL-bound, so it is safe to trust here.
    redirect = payload.get("redirect")

    if error or not code:
        # User hit "Cancel" on the consent screen.
        log.info("gmail consent aborted for %s: %s", user_id, error or "no code")
        return _redirect_target(platform, "cancelled", redirect)

    try:
        tokens = await exchange_code(code)
    except OAuthError as e:
        log.warning("gmail code exchange failed for %s: %s", user_id, e)
        return _redirect_target(platform, "error", redirect)

    access_token = tokens.get("access_token", "")
    google_email = await fetch_google_email(access_token) or "Gmail account"

    try:
        token_enc = encrypt(tokens["refresh_token"])
    except CryptoError as e:
        log.error("failed to encrypt refresh token: %s", e)
        return _redirect_target(platform, "error", redirect)

    async with begin() as conn:
        await repo.upsert_integration(
            conn,
            user_id,
            google_email=google_email,
            refresh_token_enc=token_enc,
            scope=tokens.get("scope"),
        )
    log.info("gmail connected for %s (%s)", user_id, google_email)
    return _redirect_target(platform, "connected", redirect)


async def get_status(user_id: str) -> Optional[dict[str, Any]]:
    """Connection status, or None when not connected. Never the token."""
    async with connect() as conn:
        status = await repo.get_status(conn, user_id)
        if status is None:
            return None
        # How many emails could not be read. Surfaced so an incomplete picture
        # is VISIBLE to the user rather than silently incomplete — they would
        # otherwise have no way to know a receipt never made it in.
        try:
            status["unparsed_count"] = await ledger_repo.unparsed_count(conn, user_id)
            status["broker_confirmations"] = await broker_imports.counts(user_id)
        except Exception:
            # The ledger is diagnostics; never let it break the status endpoint.
            log.warning("could not read unparsed count for %s", user_id, exc_info=True)
            status["unparsed_count"] = 0
            status["broker_confirmations"] = {
                "pending": 0,
                "imported": 0,
                "unsupported": 0,
                "failed": 0,
            }
        return status


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
        # Surfaced so "Sync now" reports the whole picture rather than only the
        # happy path: legs collapsed into an existing row, declined payments
        # deliberately not imported, and emails still owed a retry.
        "merged": result.merged,
        "failed_txn": result.failed_txn,
        "parse_errors": result.parse_errors,
        "broker_pending": result.broker_pending,
        "broker_imported": result.broker_imported,
        "broker_unsupported": result.broker_unsupported,
        "broker_failed": result.broker_failed,
    }
