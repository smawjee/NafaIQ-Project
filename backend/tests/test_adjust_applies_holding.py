"""A bare `adjust` posted to the trades endpoint must apply the holding change.

`_apply_holding_change` treats `adjust` as an absolute snapshot, and `_fold_lots`
does the same — so if the lot is recorded without applying it, psx_holdings and
its reconstruction disagree immediately. No finance reflection: a correction is
not a cash movement.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import portfolio
from app.repositories.base import begin, connect
from app.schemas.portfolio import HoldingCreate, StockTransactionCreate
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key


async def _create_user() -> str:
    email = f"adj_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            _ADMIN,
            headers={"apikey": _SK, "Authorization": f"Bearer {_SK}"},
            json={"email": email, "password": "RegrPass!2026x", "email_confirm": True},
        )
        r.raise_for_status()
        return r.json()["id"]


async def _delete_user(uid: str) -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        await c.delete(f"{_ADMIN}/{uid}",
                       headers={"apikey": _SK, "Authorization": f"Bearer {_SK}"})


async def _reflection_count(uid: str) -> int:
    async with connect() as conn:
        return int((await conn.execute(
            text("SELECT COUNT(*) FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade'"),
            {"u": uid},
        )).scalar() or 0)


async def test_adjust_lot_applies_holding_without_reflection() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Adjust PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="HBL", shares=10, avg_cost=100.0),
        )
        assert await _reflection_count(uid) == 1

        await portfolio_service.create_stock_transaction(
            user,
            StockTransactionCreate(
                portfolio_id=pid, symbol="HBL", side="adjust",
                quantity=25, price=88.0, fees=0.0, notes="Correction",
                source="manual",
            ),
        )

        holdings = await portfolio_service.list_holdings(pid)
        hbl = next(h for h in holdings if h["symbol"] == "HBL")
        assert int(hbl["shares"]) == 25
        assert abs(float(hbl["avg_cost"]) - 88.0) < 0.01

        # a correction books no cash
        assert await _reflection_count(uid) == 1
        # and the aggregate still matches its lots
        assert await portfolio_service.detect_holding_drift(pid) == []
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
