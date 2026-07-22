"""Selling a holding is a real exit: it records a `sell` lot at the stated price,
books the proceeds as income, and returns realised P&L.

Contrast with test_delete_holding_removes_lots.py — DELETE means the position
should never have existed and removes its transactions. The two branches of the
"remove this holding" UI must not behave the same way.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import portfolio
from app.repositories.base import begin, connect
from app.schemas.portfolio import HoldingCreate, HoldingSell
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key


async def _create_user() -> str:
    email = f"sell_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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


async def _lots(pid: int) -> list[dict]:
    async with connect() as conn:
        return (await conn.execute(
            text("SELECT side, quantity, price, fees FROM stock_transactions "
                 "WHERE portfolio_id = :pid ORDER BY executed_at ASC, id ASC"),
            {"pid": pid},
        )).mappings().all()


async def _reflections(uid: str) -> list[dict]:
    async with connect() as conn:
        return (await conn.execute(
            text("SELECT transaction_type, amount, category, source FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade' ORDER BY id ASC"),
            {"u": uid},
        )).mappings().all()


async def test_sell_holding_records_lot_books_income_and_returns_pnl() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Sell PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        holding = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="HBL", shares=100, avg_cost=100.0),
        )

        res = await portfolio_service.sell_holding(
            uid, pid, holding["id"], HoldingSell(price=120.0, fees=50.0),
        )

        # proceeds = 100 * 120 - 50 = 11,950 ; cost = 100 * 100 = 10,000
        assert res["shares"] == 100
        assert res["proceeds"] == 11950.0
        assert res["cost_basis"] == 10000.0
        assert res["realized_pnl"] == 1950.0
        assert res["realized_pnl_pct"] == 19.5

        # history is preserved: the buy stays, the sell is appended
        lots = await _lots(pid)
        assert [r["side"] for r in lots] == ["buy", "sell"]
        assert int(lots[1]["quantity"]) == 100
        assert abs(float(lots[1]["price"]) - 120.0) < 0.01

        # the exit books income (the old delete path booked nothing)
        refl = await _reflections(uid)
        assert [r["transaction_type"] for r in refl] == ["expense", "income"]
        assert abs(float(refl[1]["amount"]) - 11950.0) < 0.01
        assert refl[1]["category"] == "Investment"

        # position is flat and reconstructs cleanly
        async with connect() as conn:
            remaining = (await conn.execute(
                text("SELECT COUNT(*) FROM psx_holdings WHERE portfolio_id = :pid"),
                {"pid": pid},
            )).scalar()
        assert int(remaining) == 0
        assert await portfolio_service.detect_holding_drift(pid) == []
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)


async def test_sell_at_a_loss_reports_negative_pnl() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Loss PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        holding = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="PACE", shares=10, avg_cost=500.0),
        )
        res = await portfolio_service.sell_holding(
            uid, pid, holding["id"], HoldingSell(price=450.0),
        )
        # 10 * 450 = 4,500 proceeds vs 5,000 cost
        assert res["proceeds"] == 4500.0
        assert res["realized_pnl"] == -500.0
        assert res["realized_pnl_pct"] == -10.0
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)


async def test_sell_rejects_future_executed_at() -> None:
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Future PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        holding = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="HBL", shares=5, avg_cost=100.0),
        )
        future = datetime.now(timezone.utc) + timedelta(days=2)
        with pytest.raises(HTTPException) as exc:
            await portfolio_service.sell_holding(
                uid, pid, holding["id"], HoldingSell(price=110.0, executed_at=future),
            )
        assert exc.value.status_code == 400

        # the holding survived the rejected sell
        holdings = await portfolio_service.list_holdings(pid)
        assert [h["symbol"] for h in holdings] == ["HBL"]
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
