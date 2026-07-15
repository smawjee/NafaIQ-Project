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

# User-authenticated paths — validated by require_user dependency, not the API token
USER_PATHS_PREFIXES = (
    "/api/ai",
    "/api/portfolio",
    "/api/profile",
    "/api/watchlist",
    "/api/notifications",
    "/api/alerts",
    "/api/finance",
    "/api/finance-extended",
)

# Public market-data paths — no authentication required.
PUBLIC_PATH_PREFIXES = (
    "/api/market",
    "/api/quote",
    "/api/symbols",
    "/api/index",
    "/api/sectors",
    "/api/signal",
    "/api/signals",
    "/api/fundamentals",
    "/api/announcements",
    "/api/dividends",
    "/api/indicators",
    "/api/screener",
    "/api/backtest",
    "/api/macro",
    "/api/news",
    "/api/filings",
    "/api/financials",
    "/api/funds",
    "/api/health",
)


def _matches_prefix(path: str, prefix: str) -> bool:
    """Safe prefix match — exact or followed by "/".

    Avoids accidental matches like `/api/indexed-something` matching
    the `/api/index` prefix.
    """
    return path == prefix or path.startswith(prefix + "/")


def _is_user_path(path: str) -> bool:
    return any(_matches_prefix(path, prefix) for prefix in USER_PATHS_PREFIXES)


def _is_public_path(path: str) -> bool:
    return any(_matches_prefix(path, prefix) for prefix in PUBLIC_PATH_PREFIXES)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        # User paths: pass through; require_user dependency validates JWT
        if _is_user_path(request.url.path):
            return await call_next(request)
        # Public market-data paths: no auth required
        if _is_public_path(request.url.path):
            return await call_next(request)
        # Remaining /api/ paths require the shared API token
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
