"""Phase 0: PATCH/DELETE holdings must record adjusting stock_transactions.

Semantics under test:
  - PATCH  -> `adjust` lot (absolute snapshot of corrected shares/avg_cost),
              NO finance reflection.
  - DELETE -> removes the symbol's lots and their reflections entirely.
Through the PATCH steps the reflection count must stay at 1 (only the opening buy
from add_holding), proving corrections never book phantom cash; DELETE then takes
it to 0. A real sale goes through sell_holding instead — see test_sell_holding.py.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import portfolio
from app.repositories.base import begin, connect
from app.schemas.portfolio import HoldingCreate, HoldingUpdate
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key
SYMBOL = "PACE"


async def _create_user() -> str:
    email = f"upd_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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
            text("SELECT side, quantity, price FROM stock_transactions "
                 "WHERE portfolio_id = :pid ORDER BY executed_at ASC, id ASC"),
            {"pid": pid},
        )).mappings().all()


async def _reflection_count(uid: str) -> int:
    async with connect() as conn:
        return int((await conn.execute(
            text("SELECT COUNT(*) FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade'"),
            {"u": uid},
        )).scalar() or 0)


async def test_patch_and_delete_record_adjusting_lots_without_reflection() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "UpdDel PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        holding = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0),
        )
        hid = holding["id"]
        assert await _reflection_count(uid) == 1  # only the opening buy reflects

        # ---- PATCH shares 10 -> 6: records an adjust snapshot, no reflection ----
        upd = await portfolio_service.update_holding(
            uid, pid, hid, HoldingUpdate(shares=6),
        )
        assert upd["shares"] == 6
        lots = await _lots(pid)
        assert [r["side"] for r in lots] == ["buy", "adjust"]
        assert int(lots[1]["quantity"]) == 6
        assert abs(float(lots[1]["price"]) - 100.0) < 0.01
        assert await _reflection_count(uid) == 1

        # ---- PATCH avg_cost only 100 -> 120: adjust snapshot at current shares ----
        upd = await portfolio_service.update_holding(
            uid, pid, hid, HoldingUpdate(avg_cost=120.0),
        )
        assert abs(upd["avg_cost"] - 120.0) < 0.01
        lots = await _lots(pid)
        assert [r["side"] for r in lots] == ["buy", "adjust", "adjust"]
        assert int(lots[2]["quantity"]) == 6
        assert abs(float(lots[2]["price"]) - 120.0) < 0.01
        assert await _reflection_count(uid) == 1

        # holding still reconstructs cleanly from its lots
        assert await portfolio_service.detect_holding_drift(pid) == []

        # ---- DELETE: lots and reflection are removed, not appended to ----
        res = await portfolio_service.delete_holding(uid, pid, hid)
        assert res["deleted"] == hid
        assert res["lots_deleted"] == 3          # buy + 2 adjusts
        assert res["reflections_deleted"] == 1   # the opening buy's reflection
        assert await _lots(pid) == []
        assert await _reflection_count(uid) == 0

        # position is gone entirely: no holding row, no lots -> no drift
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
