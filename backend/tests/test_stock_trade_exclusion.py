"""Regression: stock-trade (investment) transactions must be counted as
investment activity — visible in the Transactions feed and in portfolio cost
basis — but excluded from every personal-finance expense aggregation
(monthly summary, 6-month income/expense chart, spending-by-category, and
budget spent recompute).

Uses a disposable real Supabase auth user (user_transactions.user_id FKs to
auth.users) and drives the repository/service layers directly. Skips when
Supabase credentials are not configured.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.config import settings
from app.repositories import finance_repo, portfolio_repo
from app.repositories.base import begin
from app.services import finance as finance_service
from app.services import portfolio as portfolio_service

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)

_ADMIN = f"{settings.supabase_url}/auth/v1/admin/users"
_SK = settings.supabase_service_key

NORMAL_EXPENSE = 1000.0   # Food
STOCK_BUY = 56000.0       # PACE investment buy


async def _create_user() -> str:
    email = f"regr_{uuid.uuid4().hex[:12]}@nafaiq-test.local"
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


async def test_stock_trade_excluded_from_expense_aggregations() -> None:
    uid = await _create_user()
    now = datetime.now(timezone.utc)
    try:
        # ---- setup: one normal expense + one stock-trade investment buy ----
        async with begin() as conn:
            # normal Food expense (PKR 1,000)
            await finance_repo.insert_transaction(
                conn,
                {
                    "user_id": uid,
                    "merchant": "Food Mart",
                    "amount": NORMAL_EXPENSE,
                    "currency": "PKR",
                    "transaction_type": "expense",
                    "category": "Food",
                    "source": "manual",
                    "note": None,
                    "transaction_date": now,
                },
            )
            # portfolio + holding -> cost basis includes the stock buy
            pf = await portfolio_repo.insert_portfolio(conn, uid, "Regr PF")
            await portfolio_repo.insert_holding(
                conn, pf["id"], "PACE", 1, STOCK_BUY, now.date()
            )
            stx = await portfolio_repo.insert_stock_transaction(
                conn,
                user_id=uid,
                portfolio_id=pf["id"],
                symbol="PACE",
                side="buy",
                quantity=1,
                price=STOCK_BUY,
                fees=0.0,
                executed_at=now,
                notes=None,
                source="manual",
            )
            # finance reflection of the buy: source='stock_trade', category='Investment'
            await portfolio_repo.insert_finance_reflection(
                conn,
                user_id=uid,
                merchant="Buy 1 PACE",
                amount=STOCK_BUY,
                transaction_type="expense",
                transaction_date=now,
                note="1 @ 56000",
                stock_transaction_id=stx["id"],
            )
            # budgets for both categories
            await finance_repo.insert_budget(
                conn,
                {"user_id": uid, "category": "Food", "spent": 0, "limit_amount": 5000.0,
                 "period": "monthly", "tip": None},
            )
            await finance_repo.insert_budget(
                conn,
                {"user_id": uid, "category": "Investment", "spent": 0, "limit_amount": 100000.0,
                 "period": "monthly", "tip": None},
            )

        # ---- 1. both transactions appear in the feed; stock is investment activity ----
        txns = await finance_service.list_transactions(uid)
        assert any(t["category"] == "Food" and t["source"] == "manual" for t in txns)
        stock_txn = [t for t in txns if t["source"] == "stock_trade"]
        assert len(stock_txn) == 1
        assert stock_txn[0]["category"] == "Investment"
        assert abs(stock_txn[0]["amount"] - STOCK_BUY) < 0.01

        # ---- 2. monthly summary expenses exclude the stock buy ----
        summary = await finance_service.summary(uid, month=now.strftime("%Y-%m"))
        assert abs(summary.expenses - NORMAL_EXPENSE) < 0.01

        # ---- 3. 6-month income/expense chart excludes the stock buy ----
        series = await finance_service.income_expense_series(uid, months=1)
        chart_expense = sum(p.expense for p in series.series)
        assert abs(chart_expense - NORMAL_EXPENSE) < 0.01

        # ---- 4. spending-by-category shows Food only, not Investment ----
        spending = await finance_service.spending_by_category(uid, days=60)
        cats = {c.category for c in spending.categories}
        assert "Investment" not in cats
        assert cats == {"Food"}
        assert abs(spending.total - NORMAL_EXPENSE) < 0.01

        # ---- 5. budget recompute excludes stock trades ----
        result = await finance_service.sync_budget_spent(uid)
        by_cat = {b["category"]: b["spent"] for b in result["budgets"]}
        assert abs(by_cat["Food"] - NORMAL_EXPENSE) < 0.01
        assert abs(by_cat["Investment"] - 0.0) < 0.01

        # ---- 6. portfolio cost basis still includes the stock buy ----
        networth = await portfolio_service.networth(uid)
        assert abs(networth["total_cost_basis"] - STOCK_BUY) < 0.01
    finally:
        await _delete_user(uid)
