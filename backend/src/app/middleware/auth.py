from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

PUBLIC_PATHS = {
    "/api/health",
    "/api/health/db",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if not settings.psx_api_token:
            return JSONResponse(
                {"detail": "API token not configured on server"}, status_code=503
            )
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.psx_api_token}":
            return JSONResponse(
                {"detail": "Invalid or missing API token"}, status_code=401
            )
        return await call_next(request)
