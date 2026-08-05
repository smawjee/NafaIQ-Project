"""HTTP contract of app.api.deps.require_user (workbook TC-AUTH-10/11).

Every other API test overrides require_user, so until now nobody asserted the
dependency's own failure modes: a missing Authorization header must be a clean
401 "Missing Authorization header" (not a 422 from a header param), and a
garbage/expired Bearer token must be a 401 "Invalid token: ...".

The route under test is a minimal one guarded by the REAL dependency; only
resolve_supabase_user is monkeypatched, exactly at the seam where a real
deployment talks to Supabase.
"""

from __future__ import annotations

from typing import Annotated

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException

from app.api import deps as deps_module
from app.api.deps import require_user


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/protected")
    async def protected(user: Annotated[dict, Depends(require_user)]):
        return {"user_id": user["user_id"]}

    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_make_app()), base_url="http://t"
    )


async def test_missing_authorization_header_is_a_clean_401():
    async with _client() as client:
        res = await client.get("/api/protected")
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing Authorization header"


async def test_invalid_bearer_token_is_401_invalid_token(monkeypatch):
    async def _reject(token: str):
        raise jwt.PyJWTError("Signature verification failed")

    monkeypatch.setattr(deps_module, "resolve_supabase_user", _reject)
    async with _client() as client:
        res = await client.get(
            "/api/protected",
            headers={"Authorization": "Bearer invalid.expired.token"},
        )
    assert res.status_code == 401
    assert res.json()["detail"].startswith("Invalid token:")


async def test_expired_token_is_401_not_a_500(monkeypatch):
    async def _expired(token: str):
        raise jwt.ExpiredSignatureError("Signature has expired")

    monkeypatch.setattr(deps_module, "resolve_supabase_user", _expired)
    async with _client() as client:
        res = await client.get(
            "/api/protected", headers={"Authorization": "Bearer whatever"}
        )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


async def test_a_valid_token_reaches_the_route(monkeypatch):
    async def _accept(token: str):
        assert token == "good-token"
        return {"user_id": "u-1", "email": "t@t", "plan": "free", "features": []}

    monkeypatch.setattr(deps_module, "resolve_supabase_user", _accept)
    async with _client() as client:
        res = await client.get(
            "/api/protected", headers={"Authorization": "Bearer good-token"}
        )
    assert res.status_code == 200
    assert res.json() == {"user_id": "u-1"}


@pytest.mark.asyncio
async def test_asymmetric_supabase_token_does_not_require_legacy_secret(monkeypatch):
    from app.config import settings
    from app.services import auth

    class SigningKey:
        key = object()

    class JwksClient:
        def get_signing_key_from_jwt(self, token):
            return SigningKey()

    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"alg": "ES256"})
    monkeypatch.setattr(auth, "_get_jwks_client", lambda: JwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "user-1", "email": "studio@example.com"},
    )

    async def plan_features(user_id):
        return "Free", {}, "active"

    monkeypatch.setattr(auth, "get_user_plan_features", plan_features)
    result = await auth.resolve_supabase_user("asymmetric-token")
    assert result["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_legacy_token_still_requires_shared_secret(monkeypatch):
    from app.config import settings
    from app.services import auth

    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"alg": "HS256"})
    with pytest.raises(HTTPException) as error:
        await auth.resolve_supabase_user("legacy-token")
    assert error.value.status_code == 503
