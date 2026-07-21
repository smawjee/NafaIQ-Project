"""Every path that answers "how much has been spent against this budget?" must
give the same answer.

Audit 2026-07-22 §2.2 found four implementations with three behaviours:
  - the budgets screen recomputed live, case-insensitively
  - the alert engine's per-category lookup recomputed live, case-SENSITIVELY
  - the alert engine's bulk fetch read a stale stored column
  - none of them honoured b.period

The live cost: two users ~50k over budget with no alert firing, and one budget
("bills" vs transactions filed as "Bills") where the screen said 5,622.96 and the
alert engine said 0.

These tests pin the invariant rather than any one query, because the divergence
was the defect.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import settings
from app.repositories import finance as finance_repo
from app.repositories.alerts import evaluator as alerts_repo
from app.repositories.base import connect

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)


async def test_ui_and_alert_paths_agree_on_spent() -> None:
    """list_budgets (UI) and get_budget_by_category (alerts) must match."""
    async with connect() as conn:
        users = (await conn.execute(
            text("SELECT DISTINCT user_id FROM user_budgets")
        )).mappings().all()

        mismatches = []
        for u in users:
            uid = str(u["user_id"])
            for b in await finance_repo.list_budgets(conn, uid):
                alert_view = await alerts_repo.get_budget_by_category(conn, uid, b["category"])
                assert alert_view is not None, (
                    f"alert path cannot find budget {b['category']!r} for {uid} — "
                    "category lookup is case-sensitive"
                )
                if abs(alert_view["spent"] - b["spent"]) > 0.01:
                    mismatches.append(
                        f"{uid} {b['category']!r}: ui={b['spent']} alerts={alert_view['spent']}"
                    )

    assert not mismatches, (
        f"{len(mismatches)} budget(s) where the screen and the alert engine "
        f"disagree:\n  " + "\n  ".join(mismatches)
    )


async def test_stored_spent_matches_live_spent() -> None:
    """The stored column must equal the live computation for every budget."""
    async with connect() as conn:
        rows = (await conn.execute(
            text(f"""
                SELECT b.id, b.user_id, b.category, b.period,
                       b.spent AS stored,
                       {finance_repo.BUDGET_SPENT_SQL} AS live
                FROM user_budgets b
            """)
        )).mappings().all()

    drift = [
        f"budget {r['id']} ({r['category']!r}, {r['period']}): "
        f"stored={float(r['stored'])} live={float(r['live'])}"
        for r in rows
        if abs(float(r["stored"]) - float(r["live"])) > 0.01
    ]
    assert not drift, (
        f"{len(drift)} budget(s) have a stale stored `spent` — the alert engine "
        f"reads this column:\n  " + "\n  ".join(drift)
    )


async def test_bulk_alert_fetch_reports_live_spent() -> None:
    """fetch_all_budgets feeds the alert evaluator; it must not serve stale data."""
    async with connect() as conn:
        bulk = await alerts_repo.fetch_all_budgets(conn)
        live = {
            r["id"]: float(r["live"])
            for r in (await conn.execute(
                text(f"SELECT b.id, {finance_repo.BUDGET_SPENT_SQL} AS live FROM user_budgets b")
            )).mappings().all()
        }

    drift = [
        f"budget {b['id']} ({b['category']!r}): bulk={float(b['spent'])} live={live[b['id']]}"
        for b in bulk
        if abs(float(b["spent"]) - live[b["id"]]) > 0.01
    ]
    assert not drift, (
        f"{len(drift)} budget(s) where the alert engine's bulk fetch is stale:\n  "
        + "\n  ".join(drift)
    )


async def test_no_future_dated_transactions() -> None:
    async with connect() as conn:
        rows = (await conn.execute(
            text("SELECT id, merchant, transaction_date FROM user_transactions "
                 "WHERE transaction_date > now() ORDER BY transaction_date")
        )).mappings().all()
    assert not rows, (
        f"{len(rows)} transaction(s) dated in the future, which inflate the "
        f"current period: {[dict(r) for r in rows]}"
    )
