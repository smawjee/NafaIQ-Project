"""Deleting a holding removes its stock_transactions lots AND their finance
reflections, scoped to that (portfolio, symbol) only.

Product rule: a holding exists because a transaction happened, so removing the
holding removes the transaction. Other symbols in the same portfolio must be
untouched.
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
    email = f"dellots_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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


async def _lot_symbols(pid: int) -> list[str]:
    async with connect() as conn:
        rows = (await conn.execute(
            text("SELECT symbol FROM stock_transactions WHERE portfolio_id = :pid "
                 "ORDER BY symbol"),
            {"pid": pid},
        )).mappings().all()
    return [r["symbol"] for r in rows]


async def _reflection_merchants(uid: str) -> list[str]:
    async with connect() as conn:
        rows = (await conn.execute(
            text("SELECT merchant FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade' ORDER BY merchant"),
            {"u": uid},
        )).mappings().all()
    return [r["merchant"] for r in rows]


async def _orphan_reflections(uid: str) -> int:
    """Reflections whose backing lot is gone — these must never exist."""
    async with connect() as conn:
        return int((await conn.execute(
            text("SELECT COUNT(*) FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade' "
                 "  AND stock_transaction_id IS NULL"),
            {"u": uid},
        )).scalar() or 0)


async def _reflections_by_type(uid: str) -> dict[str, list[str]]:
    async with connect() as conn:
        rows = (await conn.execute(
            text("SELECT transaction_type, merchant FROM user_transactions "
                 "WHERE user_id = :u AND source = 'stock_trade' "
                 "ORDER BY transaction_type, merchant"),
            {"u": uid},
        )).mappings().all()
    out: dict[str, list[str]] = {"income": [], "expense": []}
    for r in rows:
        out.setdefault(r["transaction_type"], []).append(r["merchant"])
    return out


async def test_delete_holding_removes_lots_and_reflections() -> None:
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "DelLots PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        kept = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="HBL", shares=10, avg_cost=100.0),
        )
        doomed = await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="PACE", shares=5, avg_cost=200.0),
        )
        assert await _lot_symbols(pid) == ["HBL", "PACE"]
        assert len(await _reflection_merchants(uid)) == 2

        res = await portfolio_service.delete_holding(uid, pid, doomed["id"])
        assert res["deleted"] == doomed["id"]

        # PACE lots and its reflection are gone; HBL is untouched.
        assert await _lot_symbols(pid) == ["HBL"]
        assert await _reflection_merchants(uid) == ["Buy 10 HBL"]

        # No dangling mirror rows left behind by ON DELETE SET NULL.
        assert await _orphan_reflections(uid) == 0

        # The surviving holding still reconstructs cleanly.
        assert await portfolio_service.detect_holding_drift(pid) == []
        assert kept["id"] is not None
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)


async def test_delete_holding_preserves_income_from_real_prior_sales() -> None:
    """The HIGH data-loss regression (audit 2026-07-22).

    Sequence: buy 100 -> sell 50 for real cash (books INCOME) -> the remaining
    50-share holding is deleted as "a mistake". Deleting must undo the buy's
    EXPENSE but keep the realised income — that cash was actually received, and
    erasing it would falsify the user's finance history.
    """
    uid = await _create_user()
    try:
        async with begin() as conn:
            pf = await portfolio.insert_portfolio(conn, uid, "Income PF")
        pid = pf["id"]
        user = {"user_id": uid, "plan": "Premium",
                "features": {"max_holdings_per_portfolio": 20}}

        # Buy 100 (expense reflection), then sell 50 for real (income reflection).
        await portfolio_service.add_holding(
            user, pid, HoldingCreate(symbol="CNERGY", shares=100, avg_cost=50.0),
        )
        await portfolio_service.create_stock_transaction(
            user,
            StockTransactionCreate(
                portfolio_id=pid, symbol="CNERGY", side="sell",
                quantity=50, price=80.0,
            ),
        )
        before = await _reflections_by_type(uid)
        assert before["expense"] == ["Buy 100 CNERGY"]
        assert before["income"] == ["Sell 50 CNERGY"]

        # Delete the remaining 50-share holding.
        holdings = await portfolio_service.list_holdings(pid)
        cnergy = next(h for h in holdings if h["symbol"] == "CNERGY")
        res = await portfolio_service.delete_holding(uid, pid, cnergy["id"])

        # The realised income SURVIVES; only the buy expense is undone.
        after = await _reflections_by_type(uid)
        assert after["income"] == ["Sell 50 CNERGY"], "realised income was erased"
        assert after["expense"] == [], "the mistaken buy expense should be gone"
        assert res["income_preserved"] == 1

        # Lots are cleared, so no orphan sell lot can reconstruct a bad position.
        assert await _lot_symbols(pid) == []
    finally:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM psx_portfolios WHERE user_id = :u"), {"u": uid}
            )
        await _delete_user(uid)
