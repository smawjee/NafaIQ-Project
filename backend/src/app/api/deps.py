from __future__ import annotations

import jwt
from fastapi import Header, HTTPException

from app.services.auth import resolve_supabase_user


async def require_user(authorization: str = Header(...)) -> dict:
    """Validate Supabase JWT and return {user_id, email, plan}.

    Expects: Authorization: Bearer <supabase_jwt>
    """
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("not bearer")
        return await resolve_supabase_user(token)
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise HTTPException(401, f"Invalid token: {e}")


async def optional_user(authorization: str | None = Header(None)) -> dict | None:
    """Same as require_user but returns None if no/invalid token (for optional auth)."""
    if not authorization:
        return None
    try:
        return await require_user(authorization)
    except HTTPException:
        return None
