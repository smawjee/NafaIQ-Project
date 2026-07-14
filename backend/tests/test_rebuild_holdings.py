"""Phase 0: rebuild_holdings_from_transactions is the reconciliation safety net.

It must recompute each holding's shares/avg_cost purely from that portfolio's
stock_transactions (the source of truth), overwriting any drifted psx_holdings
aggregate.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
    email = f"rbld_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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


async def _holding(pid: int) -> dict:
    async with connect() as conn:
        return (await conn.execute(
            text("SELECT shares, avg_cost FROM psx_holdings "
                 "WHERE portfolio_id = :pid AND symbol = :s"),
            {"pid": pid, "s": SYMBOL},
        )).mappings().first()


async def test_rebuild_recomputes_shares_and_avg_cost_from_lots() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Rebuild PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        # Opening buy via the service (10 @ 100), plus a second buy lot recorded
        # directly (10 @ 200) WITHOUT updating the aggregate -> deliberate drift.
        await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0),
        )
        async with begin() as conn:
            await portfolio.insert_stock_transaction(
                conn, user_id=uid, portfolio_id=pid, symbol=SYMBOL, side="buy",
                quantity=10, price=200.0, fees=0.0,
                executed_at=datetime.now(timezone.utc), notes="second lot", source="manual",
            )
            # also corrupt the stored aggregate outright
            await conn.execute(
                text("UPDATE psx_holdings SET shares = 999, avg_cost = 1 "
                     "WHERE portfolio_id = :pid AND symbol = :s"),
                {"pid": pid, "s": SYMBOL},
            )

        # rebuild: 10@100 + 10@200 -> 20 shares @ weighted-avg 150
        result = await portfolio_service.rebuild_holdings_from_transactions(pid)
        assert result["portfolio_id"] == pid

        h = await _holding(pid)
        assert int(h["shares"]) == 20
        assert abs(float(h["avg_cost"]) - 150.0) < 0.01

        # and drift is gone afterwards
        assert await portfolio_service.detect_holding_drift(pid) == []
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
