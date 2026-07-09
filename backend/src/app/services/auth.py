from __future__ import annotations

from typing import Any

import logging

import jwt
from fastapi import HTTPException

from app.config import settings
from app.services.users import get_user_plan_features

log = logging.getLogger(__name__)


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
    if not settings.supabase_jwt_secret:
        raise HTTPException(503, "SUPABASE_JWT_SECRET not configured")
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
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}") from e
    user_id = payload["sub"]
    db_plan, features = await get_user_plan_features(user_id)
    plan: str = db_plan or payload.get("plan") or "Free"
    return {
        "user_id": user_id,
        "email": payload.get("email", ""),
        "plan": plan,
        "features": features,
    }
