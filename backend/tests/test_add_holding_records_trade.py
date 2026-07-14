"""Phase 0: a manual holding add must go through the unified trade core.

Regression for the holdings<->transactions drift finding: `add_holding` used to
write `psx_holdings` ONLY. It must now record a backing `stock_transactions`
buy lot AND a `user_transactions` finance reflection, so the aggregate is
reconcilable and consistent with `create_stock_transaction`.

Uses a disposable real Supabase auth user (stock_transactions.user_id FKs to
auth.users). Skips when Supabase credentials are not configured.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import portfolio
from app.repositories.base import begin, connect
from app.schemas.portfolio import HoldingCreate
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key
SYMBOL = "PACE"


async def _create_user() -> str:
    email = f"addh_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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
        await c.delete(
            f"{_ADMIN}/{uid}",
            headers={"apikey": _SK, "Authorization": f"Bearer {_SK}"},
        )


async def test_add_holding_records_buy_lot_and_reflection() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "AddH PF")
        pid = pf["id"]

        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}
        holding = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0,
                                     purchased_at="2026-01-05"),
        )

        # 1. holding written as before
        assert holding["shares"] == 10
        assert abs(holding["avg_cost"] - 100.0) < 0.01
        assert holding["symbol"] == SYMBOL

        # 2. a backing stock_transactions buy lot exists
        async with connect() as conn:
            rows = (await conn.execute(
                text("SELECT side, quantity, price FROM stock_transactions "
                     "WHERE portfolio_id = :pid AND symbol = :s"),
                {"pid": pid, "s": SYMBOL},
            )).mappings().all()
        assert len(rows) == 1
        assert rows[0]["side"] == "buy"
        assert int(rows[0]["quantity"]) == 10
        assert abs(float(rows[0]["price"]) - 100.0) < 0.01

        # 3. a finance reflection (expense, source stock_trade) exists
        async with connect() as conn:
            refl = (await conn.execute(
                text("SELECT transaction_type, amount, category, source "
                     "FROM user_transactions WHERE user_id = :u AND source = 'stock_trade'"),
                {"u": uid},
            )).mappings().all()
        assert len(refl) == 1
        assert refl[0]["transaction_type"] == "expense"
        assert refl[0]["category"] == "Investment"
        assert abs(float(refl[0]["amount"]) - 1000.0) < 0.01

        # 4. no drift: the aggregate matches its lots
        assert await portfolio_service.detect_holding_drift(pid) == []
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
