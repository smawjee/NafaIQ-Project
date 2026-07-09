from __future__ import annotations

import jwt
from fastapi import Header, HTTPException

from app.config import settings


async def require_user(authorization: str = Header(...)) -> dict:
    """Validate Supabase JWT and return {user_id, email, plan}.

    Expects: Authorization: Bearer <supabase_jwt>
    """
    if not settings.supabase_jwt_secret:
        raise HTTPException(503, "SUPABASE_JWT_SECRET not configured")
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("not bearer")
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {
            "user_id": payload["sub"],
            "email": payload.get("email", ""),
            "plan": payload.get("plan") or "Free",
        }
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
