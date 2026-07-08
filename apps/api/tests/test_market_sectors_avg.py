"""Tests for the /api/market/sectors/avg SQLAlchemy Core example endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_sector_averages_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/market/sectors/avg",
            headers={"Authorization": "Bearer 5-wkjehgDPMSaQ8hI7SnFdIpzuLUx_zTxi21LT8GCpQ"},
        )
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
