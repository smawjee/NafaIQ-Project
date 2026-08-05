from __future__ import annotations

from typing import Any

import logging

import jwt
from fastapi import HTTPException

from app.config import settings
from app.services.users import get_user_plan_features

log = logging.getLogger(__name__)

# Fixed client-facing messages. The raw decoder exception is never echoed back:
# it can carry library internals (codec errors, key material, header bytes).
#
# Expiry is the one distinction worth keeping. It is not sensitive - the client
# already knows when its own token expires - and the frontend needs it to tell a
# refreshable session apart from a genuinely bad credential.
INVALID_TOKEN_DETAIL = "Invalid token: verification failed"
EXPIRED_TOKEN_DETAIL = "Invalid token: expired"


def token_error_detail(exc: BaseException) -> str:
    """Map a decode failure onto a safe, fixed client message."""
    return (
        EXPIRED_TOKEN_DETAIL
        if isinstance(exc, jwt.ExpiredSignatureError)
        else INVALID_TOKEN_DETAIL
    )


_jwks_client: "jwt.PyJWKClient | None" = None


def _get_jwks_client() -> "jwt.PyJWKClient":
    """Cached JWKS client. Supabase now signs tokens with asymmetric keys
    (ES256/RS256); PyJWKClient caches the public keys, so we keep one instance
    instead of refetching JWKS on every authenticated request."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        )
    return _jwks_client


async def resolve_supabase_user(token: str) -> dict[str, Any]:
    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")
        if alg in ("RS256", "ES256"):
            # Asymmetric (current Supabase default): verify against JWKS public keys.
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
        else:
            # Legacy HS256 shared secret.
            if not settings.supabase_jwt_secret:
                raise HTTPException(503, "SUPABASE_JWT_SECRET not configured")
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
    except HTTPException:
        raise
    except Exception as e:
        # The decoder's own message can carry implementation detail (codec
        # errors, key material, library internals). Log it for operators and
        # return a fixed string to the caller.
        log.warning("JWT verification failed: %s", e)
        raise HTTPException(401, token_error_detail(e)) from e
    user_id = payload["sub"]
    db_plan, features, account_status = await get_user_plan_features(user_id)
    # Suspended accounts are rejected at the identity boundary, so every
    # authenticated route (portfolio, finance, assistant, admin, …) is blocked
    # at once. 'restricted' is intentionally NOT blocked here — it is a softer
    # state reserved for future partial limits; only 'suspended' locks out.
    if account_status == "suspended":
        raise HTTPException(403, "Account suspended")
    plan: str = db_plan or payload.get("plan") or "Free"
    return {
        "user_id": user_id,
        "email": payload.get("email", ""),
        "plan": plan,
        "features": features,
        "account_status": account_status,
    }
