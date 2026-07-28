"""Tests for the /api/market/sectors/avg SQLAlchemy Core example endpoint.

Requires a live database. Guarded so the suite stays green in CI without
credentials — same `pytestmark` as tests/test_sell_holding.py.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)


@pytest.mark.asyncio
async def test_sector_averages_endpoint():
    # The shared PSX token is read from settings, never from a literal: this
    # file previously carried a real bearer token in plain text.
    headers = (
        {"Authorization": f"Bearer {settings.psx_api_token}"} if settings.psx_api_token else {}
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/market/sectors/avg", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    if len(data) > 0:
        first = data[0]
        assert "sector" in first
        assert "avg_change_pct" in first
        assert "stock_count" in first
        assert "total_volume" in first
        assert isinstance(first["avg_change_pct"], (int, float))
        assert isinstance(first["stock_count"], int)
