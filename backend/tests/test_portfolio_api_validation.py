"""HTTP validation contract of the portfolio holdings routes (TC-PORT-02/06).

The sell/lot BEHAVIOUR is covered by the live-DB tests in
test_sell_holding.py; what had no coverage at all was the request-validation
layer of app.api.portfolio — a 0/negative shares or avg_cost must be a 422
before any service call (a 0-cost holding fakes an infinite gain), while a
sale PRICE of exactly 0 is legal by design (worthless/delisted exit,
HoldingSell.price ge=0).

Same recipe as test_alerts_api.py: router-only app, require_user overridden,
the service module monkeypatched with recording stubs.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api import portfolio as portfolio_api
from app.api.deps import require_user

FAKE_USER = {"user_id": "u-1", "email": "t@t", "plan": "free", "features": []}


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_make_app()), base_url="http://t"
    )


@pytest.fixture
def svc(monkeypatch):
    """Record every service call; validation failures must record nothing."""

    class Recorder:
        def __init__(self):
            self.calls: list[tuple[str, tuple, dict]] = []

        def __getattr__(self, name):
            async def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return {"ok": True, "op": name}

            return _record

    rec = Recorder()
    monkeypatch.setattr(portfolio_api, "portfolio_service", rec)
    return rec


@pytest.mark.parametrize(
    "body",
    [
        {"symbol": "HBL", "shares": 0, "avg_cost": 95},
        {"symbol": "HBL", "shares": -10, "avg_cost": 95},
        {"symbol": "HBL", "shares": 100, "avg_cost": 0},
        {"symbol": "HBL", "shares": 100, "avg_cost": -50},
        {"symbol": "", "shares": 100, "avg_cost": 95},
    ],
)
async def test_add_holding_rejects_invalid_bodies(svc, body):
    async with _client() as client:
        res = await client.post("/api/portfolio/1/holdings", json=body)
    assert res.status_code == 422
    assert svc.calls == []


async def test_add_holding_accepts_a_valid_body(svc):
    async with _client() as client:
        res = await client.post(
            "/api/portfolio/1/holdings",
            json={"symbol": "OGDC", "shares": 100, "avg_cost": 95.0},
        )
    assert res.status_code == 200
    assert [name for name, *_ in svc.calls] == ["add_holding"]


@pytest.mark.parametrize(
    "body",
    [
        {"shares": 0},
        {"shares": -1},
        {"avg_cost": 0},
        {"avg_cost": -0.01},
    ],
)
async def test_update_holding_enforces_positive_values_when_present(svc, body):
    async with _client() as client:
        res = await client.patch("/api/portfolio/1/holdings/2", json=body)
    assert res.status_code == 422
    assert svc.calls == []


async def test_sell_rejects_a_negative_price(svc):
    async with _client() as client:
        res = await client.post(
            "/api/portfolio/1/holdings/2/sell", json={"price": -1}
        )
    assert res.status_code == 422
    assert svc.calls == []


async def test_sell_at_price_zero_is_accepted_for_a_worthless_exit(svc):
    async with _client() as client:
        res = await client.post(
            "/api/portfolio/1/holdings/2/sell", json={"price": 0, "fees": 0}
        )
    assert res.status_code == 200
    assert [name for name, *_ in svc.calls] == ["sell_holding"]
