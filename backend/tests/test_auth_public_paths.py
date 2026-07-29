"""Auth middleware path classification.

Guards two things that are easy to break silently:

1. ``POST /api/funds/import`` writes to psx_mutual_funds / psx_fund_nav_history
   using the service-role key, so RLS is NOT a backstop. It lives under the
   otherwise-public ``/api/funds`` prefix and must never classify as public.
2. The public ``/api/financials`` prefix must not collapse into the
   user-scoped ``/api/finance`` prefix (or vice versa).
"""
from __future__ import annotations

import pytest

from app.middleware.auth import ADMIN_PATHS, _is_public_path, _is_user_path


@pytest.mark.parametrize(
    "path",
    [
        "/api/funds",
        "/api/funds/ABC123",
        "/api/funds/ABC123/nav",
        "/api/macro/rates",
        "/api/news",
        "/api/filings/HBL",
        "/api/filings/HBL/search",
        "/api/financials/HBL/annual",
        "/api/health/sources",
        "/api/market/unusual",
        "/api/dividends",
    ],
)
def test_public_market_paths_are_public(path: str) -> None:
    assert _is_public_path(path) is True


@pytest.mark.parametrize("path", sorted(ADMIN_PATHS))
def test_protected_paths_are_not_public(path: str) -> None:
    """Write/admin endpoints under a public prefix fall through to the token check."""
    assert _is_public_path(path) is False


def test_funds_import_is_protected() -> None:
    # Explicit: this is the endpoint that was anonymously writable.
    assert "/api/funds/import" in ADMIN_PATHS
    assert _is_public_path("/api/funds/import") is False
    # ...while the sibling read endpoints stay public.
    assert _is_public_path("/api/funds") is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/finance",
        "/api/finance/zakat",
        "/api/portfolio",
        "/api/ai/report/market-brief",
    ],
)
def test_user_paths_are_user_scoped(path: str) -> None:
    assert _is_user_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/financials/HBL/annual",
        "/api/financials",
    ],
)
def test_financials_does_not_collapse_into_finance(path: str) -> None:
    """`/api/financials` must not be swallowed by the `/api/finance` user prefix."""
    assert _is_user_path(path) is False
    assert _is_public_path(path) is True


def test_prefix_matching_respects_boundaries() -> None:
    """`/api/index` must not match `/api/indexed-something`."""
    assert _is_public_path("/api/index") is True
    assert _is_public_path("/api/index/KSE100") is True
    assert _is_public_path("/api/indexed-something") is False


# The classification tests above prove /api/funds/import is not public. They do
# NOT prove which credential it accepts. It used to accept PSX_API_TOKEN, which
# the web app ships as VITE_PSX_API_TOKEN — inlined into the public browser
# bundle and readable in DevTools, so the guard authenticated nobody. These
# drive the middleware and pin the credential itself.


def _client(api_token: str = "public-bundle-token", admin_token: str = "backend-only-token"):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.middleware.auth import BearerTokenMiddleware

    settings.psx_api_token = api_token
    settings.psx_admin_token = admin_token

    app = FastAPI()
    app.add_middleware(BearerTokenMiddleware)

    @app.post("/api/funds/import")
    async def _import():
        return {"ok": True}

    return TestClient(app)


def test_admin_path_rejects_the_browser_readable_api_token() -> None:
    """The token Vite inlines into the public bundle must NOT open an admin write."""
    r = _client().post(
        "/api/funds/import", headers={"Authorization": "Bearer public-bundle-token"}
    )
    assert r.status_code == 401, "the public VITE_PSX_API_TOKEN was accepted as admin"


def test_admin_path_accepts_the_admin_token() -> None:
    r = _client().post(
        "/api/funds/import", headers={"Authorization": "Bearer backend-only-token"}
    )
    assert r.status_code == 200


def test_admin_path_rejects_anonymous() -> None:
    assert _client().post("/api/funds/import").status_code == 401


def test_admin_path_fails_closed_when_admin_token_unset() -> None:
    """An unconfigured server must refuse, not fall back to the shared token."""
    r = _client(admin_token="").post(
        "/api/funds/import", headers={"Authorization": "Bearer public-bundle-token"}
    )
    assert r.status_code == 503
