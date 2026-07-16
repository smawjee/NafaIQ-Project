"""Seed a test user with realistic data so the AI reports + analysis surface
can be exercised against the PNGs.

Idempotent: re-running on a user that already has data purges the seeded
content (transactions/holdings/goals/budgets in the expected scope) and
re-inserts. It never touches other users.

Phase 0 invariants are preserved: every holding goes through
`record_trade_atomic`, so `psx_holdings` is rebuildable from
`stock_transactions`; the `detect_holding_drift` audit stays clean.

Usage:
    cd backend
    python scripts/seed_dummy_user.py [--user-id <UUID>] [--purge]

Default user: f758e59b-fa84-465b-a761-932e09ff1748 (usman isgamer, Free plan).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv(".env")

from app.db.supabase import get_supabase
from app.repositories.base import begin, connect
from app.schemas.finance import BudgetCreate, GoalCreate, TransactionCreate
from app.schemas.portfolio import HoldingCreate, PortfolioCreate, StockTransactionCreate
from app.services import portfolio as portfolio_svc
from app.services.finance import budgets as budget_svc
from app.services.finance import goals as goal_svc
from app.services.finance import transactions as txn_svc
from app.services.portfolio import trades as trades_svc

DEFAULT_USER_ID = "f758e59b-fa84-465b-a761-932e09ff1748"

# Real PSX tickers the live data layer already knows. Keep the seeded symbols
# in this set so subsequent stock analysis / fundamentals / announcements
# lookups return real data.
HOLDINGS = [
    {"symbol": "HBL", "shares": 200, "avg_cost": 135.5},
    {"symbol": "OGDC", "shares": 100, "avg_cost": 145.8},
    {"symbol": "ENGRO", "shares": 150, "avg_cost": 320.0},
    {"symbol": "MEBL", "shares": 250, "avg_cost": 220.0},
]

# Goals chosen so the numbers and percentages match the PNG copy closely:
# 35% / 60% / 12%.
GOALS = [
    {
        "name": "Hajj Fund",
        "target": 1_200_000.0,
        "saved": 425_000.0,
        "emoji": "\U0001F3AF",
        "color": "bull",
    },
    {
        "name": "Emergency Fund",
        "target": 300_000.0,
        "saved": 180_000.0,
        "emoji": "\U0001F6E1",
        "color": "warning",
    },
    {
        "name": "Honda City",
        "target": 800_000.0,
        "saved": 95_000.0,
        "emoji": "\U0001F697",
        "color": "bull",
    },
]

BUDGETS = [
    {"category": "Dining", "limit_amount": 25_000.0, "tip": "Track every restaurant order."},
    {"category": "Groceries", "limit_amount": 60_000.0, "tip": "Compare prices weekly."},
    {"category": "Transport", "limit_amount": 15_000.0, "tip": "Combine errands into one trip."},
    {"category": "Bills", "limit_amount": 20_000.0, "tip": "Review subscriptions quarterly."},
]


def _user_dict(user_id: str) -> dict[str, Any]:
    """Minimal user payload the service functions need (uid + plan features)."""
    return {
        "user_id": user_id,
        "email": "seed@nafaiq.local",
        "plan": "Free",
        "features": {
            "max_portfolios": 1,
            "max_holdings_per_portfolio": 20,
            "max_budgets": 5,
            "max_bills": 5,
            "max_goals": 3,
            "ai_tutor_daily_limit": 10,
            "ai_reports_per_period": 3,
            "ai_reports_period": "month",
        },
    }


async def purge_seeded(user_id: str) -> None:
    """Delete the seeded content for `user_id`. Idempotent.

    Order matters: drop the stock transactions that back the holdings first
    so the on-delete cascade leaves a clean `psx_holdings` row to delete.
    We do NOT call `delete_holding` (which would also book a closing sell);
    we delete rows directly so a re-seed stays clean and drift-free.
    """
    sb = get_supabase()
    print("purging previous seed for user ...")
    sb.table("user_transactions").delete().eq("user_id", user_id).execute()
    sb.table("user_budgets").delete().eq("user_id", user_id).execute()
    sb.table("user_goals").delete().eq("user_id", user_id).execute()
    sb.table("stock_transactions").delete().eq("user_id", user_id).execute()

    # Find the user's portfolio_id, then drop holdings + portfolio.
    portfolios = (
        sb.table("psx_portfolios")
        .select("id")
        .eq("user_id", user_id)
        .execute()
    )
    for p in portfolios.data or []:
        sb.table("psx_holdings").delete().eq("portfolio_id", p["id"]).execute()
        sb.table("psx_portfolios").delete().eq("id", p["id"]).execute()


async def seed_portfolio(user: dict, name: str) -> int:
    pf = await portfolio_svc.create_portfolio(user, name)
    print(f"  portfolio: {pf['name']} (id={pf['id']})")
    return pf["id"]


async def seed_holdings(user: dict, portfolio_id: int) -> int:
    n = 0
    for h in HOLDINGS:
        body = HoldingCreate(
            symbol=h["symbol"],
            shares=h["shares"],
            avg_cost=h["avg_cost"],
            purchased_at=None,
        )
        await portfolio_svc.add_holding(user, portfolio_id, body)
        n += 1
    print(f"  holdings: {n} ({', '.join(h['symbol'] for h in HOLDINGS)})")
    return n


async def seed_goals(user: dict) -> int:
    n = 0
    for g in GOALS:
        body = GoalCreate(
            emoji=g["emoji"],
            name=g["name"],
            target=g["target"],
            saved=g["saved"],
            color=g["color"],
            ai_tip=None,
            target_date=None,
        )
        await goal_svc.create_goal(user["user_id"], body, user)
        n += 1
    print(f"  goals: {n} ({', '.join(g['name'] for g in GOALS)})")
    return n


async def seed_budgets(user: dict) -> int:
    n = 0
    for b in BUDGETS:
        body = BudgetCreate(
            category=b["category"],
            spent=0.0,
            limit_amount=b["limit_amount"],
            period="monthly",
            tip=b["tip"],
        )
        await budget_svc.create_budget(user["user_id"], body, user)
        n += 1
    print(f"  budgets: {n} ({', '.join(b['category'] for b in BUDGETS)})")
    return n


async def seed_transactions(user_id: str, *, deliberate_overspend: bool = True) -> int:
    """Spread ~32 transactions across 6 months. The current month includes a
    deliberate Dining overspend so the dashboard recommendation can detect a
    meaningful deviation. Categories are aligned with the seeded budgets.
    """
    rng = random.Random(20260715)  # deterministic so re-runs match
    now = datetime.now(timezone.utc)
    today = now.date()
    income_dates = [today.replace(day=1) - timedelta(days=30 * m) for m in range(6)]

    n = 0

    # 6 monthly salary income rows.
    for d in income_dates:
        d = d.replace(day=min(d.day, 28))
        body = TransactionCreate(
            merchant="Acme Corp Payroll",
            amount=150_000.0,
            transaction_type="income",
            category="Salary",
            transaction_date=d.isoformat(),
            source="seed",
            note="Monthly salary",
        )
        await txn_svc.create_transaction(user_id, body)
        n += 1

    # Current-month DELIBERATE overspend on Dining (~1.5x the budget cap).
    if deliberate_overspend:
        start = today.replace(day=1)
        for i in range(8):
            d = start + timedelta(days=i * 3 + 1)
            if d > today:
                d = today
            amount = rng.uniform(3_500.0, 6_500.0)
            body = TransactionCreate(
                merchant=rng.choice(["Chaayos", "Burning Brownie", "Savour Foods", "KFC"]),
                amount=round(amount, 2),
                transaction_type="expense",
                category="Dining",
                transaction_date=d.isoformat(),
                source="seed",
                note="Lunch/dinner",
            )
            await txn_svc.create_transaction(user_id, body)
            n += 1

    # Other categories, distributed across the last 6 months.
    other_categories = ["Groceries", "Transport", "Bills", "Utilities", "Shopping"]
    merchants = {
        "Groceries": ["Metro", "Imtiaz", "Al-Fatah"],
        "Transport": ["Careem", "Uber", "PSO Fuel"],
        "Bills": ["K-Electric", "SSGC", "PTCL"],
        "Utilities": ["Internet", "Mobile"],
        "Shopping": ["Daraz", "Outfitters"],
    }
    for m in range(6):
        month_start = today.replace(day=1) - timedelta(days=30 * m)
        for cat in other_categories:
            occurrences = rng.randint(1, 3)
            for _ in range(occurrences):
                d = month_start + timedelta(days=rng.randint(0, 27))
                if d > today:
                    continue
                d = d.replace(day=min(d.day, 28))
                base = {
                    "Groceries": 8_000.0,
                    "Transport": 2_500.0,
                    "Bills": 4_500.0,
                    "Utilities": 1_500.0,
                    "Shopping": 5_000.0,
                }[cat]
                amount = round(rng.uniform(base * 0.6, base * 1.4), 2)
                body = TransactionCreate(
                    merchant=rng.choice(merchants[cat]),
                    amount=amount,
                    transaction_type="expense",
                    category=cat,
                    transaction_date=d.isoformat(),
                    source="seed",
                    note=None,
                )
                await txn_svc.create_transaction(user_id, body)
                n += 1

    print(f"  transactions: {n} (1.5x dining overspend in current month)")
    return n


async def sync_budgets(user_id: str) -> int:
    """Recompute user_budgets.spent from the actual transactions so the
    budget-health metric in the finance report is real."""
    res = await budget_svc.sync_budget_spent(user_id)
    print(f"  budget spent synced: {res.get('updated', 0)} budgets recomputed")
    return res.get("updated", 0)


async def main(user_id: str, purge: bool) -> int:
    print(f"seeding user {user_id} (Free plan)")
    if purge:
        await purge_seeded(user_id)

    user = _user_dict(user_id)
    portfolio_id = await seed_portfolio(user, "Main")
    await seed_holdings(user, portfolio_id)
    await seed_goals(user)
    await seed_budgets(user)
    await seed_transactions(user_id)
    await sync_budgets(user_id)

    print()
    print(f"seeded: portfolio=1 holdings={len(HOLDINGS)} "
          f"goals={len(GOALS)} budgets={len(BUDGETS)} transactions=many")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--purge", action="store_true",
                        help="Delete previously-seeded content for this user first")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.user_id, args.purge)))
