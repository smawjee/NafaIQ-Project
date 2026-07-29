from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

PUBLIC_PATHS = {
    "/api/health",
    "/api/health/db",
    # Client-safe platform flags (registration_enabled, maintenance_mode).
    # Must be anonymous: the app reads maintenance_mode before it can sign
    # anyone in, and the sign-up screen reads registration_enabled before a
    # session exists. The endpoint only returns an allow-listed subset.
    "/api/platform/flags",
    # Client error capture. Anonymous by design: a crash on the sign-in screen
    # is exactly the failure nobody hears about today. The endpoint stores
    # nothing the caller controls unredacted, is rate-limited per caller, and
    # returns a bare acknowledgement — see api/telemetry.py.
    "/api/telemetry/errors",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# User-authenticated paths — validated by require_user dependency, not the API token
USER_PATHS_PREFIXES = (
    "/api/ai",
    # LearnHub LLM-backed features (quiz explanations, summaries). MUST stay
    # ahead of the public "/api/learn" prefix below — dispatch checks user
    # paths first, which is what keeps these authenticated while plain
    # /api/learn search stays open.
    "/api/learn/ai",
    # NafaIQ Assistant: every route reads or writes the caller's own finance
    # data, so the shared PSX API token must never satisfy it — JWT only.
    "/api/assistant",
    # Admin dashboard: JWT flows through here; per-route dependencies
    # (require_admin / require_permission) do the actual authorization. The
    # shared PSX token must never satisfy an admin route.
    "/api/admin",
    "/api/portfolio",
    "/api/profile",
    "/api/watchlist",
    "/api/notifications",
    "/api/alerts",
    "/api/finance",
    "/api/finance-extended",
    "/api/integrations",
    # Bug reports are scoped to the caller's own account, so JWT only — the
    # shared PSX token must never satisfy them.
    "/api/support",
)

# Write/admin endpoints that live under an otherwise-public prefix. Checked
# BEFORE PUBLIC_PATH_PREFIXES so they are not exposed anonymously.
#
# These validate PSX_ADMIN_TOKEN, NOT the shared PSX_API_TOKEN. The shared
# token is not a secret: frontend/packages/web/.env.example ships it as
# VITE_PSX_API_TOKEN, and Vite inlines every VITE_-prefixed var into the public
# browser bundle, so anyone can read it in DevTools. Gating a service-role
# write on it would only look like authentication. PSX_ADMIN_TOKEN is
# backend-only and must never be given a VITE_ alias.
ADMIN_PATHS = {
    "/api/funds/import",
}

# Public market-data paths — no authentication required.
PUBLIC_PATH_PREFIXES = (
    # LearnHub search/glossary/related. Published course material — the web
    # bundle already ships this content, so there is nothing to gate.
    # /api/learn/ai is NOT covered: it is matched earlier as a user path.
    "/api/learn",
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
    if path in ADMIN_PATHS:
        return False
    return any(_matches_prefix(path, prefix) for prefix in PUBLIC_PATH_PREFIXES)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        # Admin writes: backend-only token, checked before anything else can
        # let the path through. Fails closed when unset — an unconfigured
        # server must not fall back to the browser-readable shared token.
        if request.url.path in ADMIN_PATHS:
            if not settings.psx_admin_token:
                return JSONResponse(
                    {"detail": "Admin token not configured on server"}, status_code=503
                )
            if request.headers.get("Authorization", "") != f"Bearer {settings.psx_admin_token}":
                return JSONResponse(
                    {"detail": "Invalid or missing admin token"}, status_code=401
                )
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
