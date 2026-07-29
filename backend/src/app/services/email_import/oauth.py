"""Google OAuth for Gmail read access.

Deliberately separate from Supabase's "Sign in with Google": identity and
mailbox access are different consents. Keeping them apart means the login screen
never asks for a scary gmail.readonly grant, users who don't want the importer
never see it, and the backend owns the refresh token from the start (Supabase
does not persist provider refresh tokens, so it cannot give us one).

Hand-rolled over httpx rather than google-auth/google-api-python-client — we
only need three endpoints, and this matches how services/ai/providers.py calls
its APIs.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Literal

import httpx

from app.config import settings
from app.services.crypto import decrypt_state, encrypt_state

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
# Requested alongside gmail.readonly so we can label the connection with the
# Google account that was actually linked (it may differ from the NafaIQ login).
SCOPES = f"{GMAIL_SCOPE} https://www.googleapis.com/auth/userinfo.email"

Platform = Literal["web", "mobile"]

STATE_TTL_S = 600
_TIMEOUT_S = 20.0


class OAuthError(Exception):
    """OAuth exchange/refresh failed."""


class ReconnectRequired(OAuthError):
    """The grant is dead — the user must re-consent.

    Google returns invalid_grant when the refresh token was revoked OR when it
    expired, which in a Testing-mode app happens automatically after 7 days.
    Callers should surface this as a "Reconnect Gmail" prompt, not a retry.
    """


def build_auth_url(user_id: str, platform: Platform, redirect: str | None = None) -> str:
    """Consent URL for this user. `state` carries the identity (the callback is
    public), the platform, and an optional client-supplied redirect URL (so an
    Expo Go `exp://` session or a native `nafaiqmobile://` build both get sent
    back to the exact URL they are listening on). The redirect lives inside the
    encrypted, TTL-bound state so the public callback cannot be pointed elsewhere."""
    payload: dict[str, Any] = {
        "user_id": str(user_id),
        "platform": platform,
        "nonce": secrets.token_urlsafe(8),
    }
    if redirect:
        payload["redirect"] = redirect
    state = encrypt_state(payload)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        # offline + consent are what actually yield a refresh token; without
        # prompt=consent Google omits it on repeat authorisations.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{httpx.QueryParams(params)}"


def parse_state(state: str) -> dict[str, Any]:
    """Verify the state from the callback. Raises CryptoError if forged/expired."""
    return decrypt_state(state, ttl=STATE_TTL_S)


async def _token_request(data: dict[str, str]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            res = await client.post(TOKEN_URL, data=data)
    except httpx.HTTPError as e:
        raise OAuthError(f"token request failed: {e}") from e

    if res.status_code != 200:
        body = res.text[:300]
        if "invalid_grant" in body:
            raise ReconnectRequired("Google access expired or was revoked")
        raise OAuthError(f"token request failed: HTTP {res.status_code}: {body}")
    return res.json()


async def exchange_code(code: str) -> dict[str, Any]:
    """Swap an authorization code for tokens. Returns {access_token,
    refresh_token, scope, ...}."""
    payload = await _token_request(
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
    )
    if not payload.get("refresh_token"):
        # Only happens if prompt=consent/access_type=offline were lost.
        raise OAuthError("Google did not return a refresh token")
    return payload


async def refresh_access_token(refresh_token: str) -> str:
    """Mint a short-lived access token. Raises ReconnectRequired if the grant
    is dead (the 7-day Testing-mode expiry, or user revocation)."""
    payload = await _token_request(
        {
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
        }
    )
    token = payload.get("access_token")
    if not token:
        raise OAuthError("no access_token in refresh response")
    return token


async def fetch_google_email(access_token: str) -> str | None:
    """The connected Google account's address, for display in Settings."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            res = await client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
        if res.status_code != 200:
            return None
        return res.json().get("email")
    except httpx.HTTPError:
        return None


async def revoke(token: str) -> None:
    """Best-effort revoke at Google on disconnect, so access ends immediately
    rather than when the token lapses. Never raises — the local row is deleted
    regardless."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            await client.post(REVOKE_URL, data={"token": token})
    except httpx.HTTPError:
        log.info("google token revoke failed (ignored)", exc_info=True)
