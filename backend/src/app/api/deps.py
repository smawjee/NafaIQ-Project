from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import resolve_supabase_user

_bearer = HTTPBearer(auto_error=False)


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Supabase JWT and return {user_id, email, plan, features}.

    Expects: Authorization: Bearer <supabase_jwt>

    Returns a clean 401 (not 422) when the header is missing or malformed.
    Declared as an HTTPBearer security scheme (not a plain Header param)
    because the OpenAPI spec ignores header parameters named
    "Authorization" -- this way Swagger UI's Authorize button works.
    """
    if credentials is None:
        raise HTTPException(401, "Missing Authorization header")
    try:
        return await resolve_supabase_user(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise HTTPException(401, f"Invalid token: {e}")


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Same as require_user but returns None if no/invalid token (for optional auth)."""
    if credentials is None:
        return None
    try:
        return await require_user(credentials)
    except HTTPException:
        return None
