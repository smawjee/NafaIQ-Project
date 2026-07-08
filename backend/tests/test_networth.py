from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_networth_endpoint_requires_auth():
    """Unauthenticated request returns 401 or 422 (missing Authorization header)."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/portfolio/networth")
    assert r.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_history_coverage_endpoint_returns_list():
    """Public PSX-token endpoint returns list of {symbol, days_available, ...}."""
    from httpx import ASGITransport, AsyncClient
    from app.config import settings
    from app.main import app
    headers = {"Authorization": f"Bearer {settings.psx_api_token}"} if settings.psx_api_token else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/market/history-coverage", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
