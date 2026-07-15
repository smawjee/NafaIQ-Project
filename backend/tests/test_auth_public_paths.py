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

from app.middleware.auth import PROTECTED_PATHS, _is_public_path, _is_user_path


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


@pytest.mark.parametrize("path", sorted(PROTECTED_PATHS))
def test_protected_paths_are_not_public(path: str) -> None:
    """Write/admin endpoints under a public prefix fall through to the token check."""
    assert _is_public_path(path) is False


def test_funds_import_is_protected() -> None:
    # Explicit: this is the endpoint that was anonymously writable.
    assert "/api/funds/import" in PROTECTED_PATHS
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
