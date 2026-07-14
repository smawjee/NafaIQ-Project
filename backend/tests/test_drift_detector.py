"""Phase 0: detect_holding_drift must catch a psx_holdings aggregate that no
longer matches the sum of its stock_transactions lots — including holdings that
have no backing lots at all (the un-reconciled rows the backfill repairs).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import portfolio
from app.repositories.base import begin
from app.schemas.portfolio import HoldingCreate
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key
SYMBOL = "PACE"
UNBACKED = "HBL"


async def _create_user() -> str:
    email = f"drift_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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


async def test_drift_detector_flags_injected_mismatch_and_unbacked_holding() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Drift PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        # A consistent holding (backed by a buy lot) -> no drift initially.
        await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0),
        )
        assert await portfolio_service.detect_holding_drift(pid) == []

        # Inject a deliberate share mismatch into the stored aggregate.
        async with begin() as conn:
            await conn.execute(
                text("UPDATE psx_holdings SET shares = 50 "
                     "WHERE portfolio_id = :pid AND symbol = :s"),
                {"pid": pid, "s": SYMBOL},
            )
            # And an un-backed holding (no stock_transactions at all).
            await portfolio.insert_holding(
                conn, pid, UNBACKED, 5, 300.0, datetime.now(timezone.utc).date()
            )

        drift = await portfolio_service.detect_holding_drift(pid)
        by_symbol = {d["symbol"]: d for d in drift}

        assert SYMBOL in by_symbol
        assert by_symbol[SYMBOL]["holding_shares"] == 50
        assert by_symbol[SYMBOL]["expected_shares"] == 10
        assert by_symbol[SYMBOL]["has_lots"] is True

        assert UNBACKED in by_symbol
        assert by_symbol[UNBACKED]["holding_shares"] == 5
        assert by_symbol[UNBACKED]["expected_shares"] == 0
        assert by_symbol[UNBACKED]["has_lots"] is False
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
