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

import ast
import pathlib

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


def _sql_literals(path: pathlib.Path) -> list[str]:
    """Every string literal in a module except docstrings, f-strings flattened.

    SQL in this codebase lives in string literals, so this is where a query that
    reads the stored column would have to appear. Docstrings are excluded
    because several of them discuss `b.spent` in prose (including the one right
    above this test).
    """
    # utf-8-sig, not utf-8: at least one module in this tree carries a BOM, and
    # ast.parse rejects U+FEFF as a non-printable character.
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            # An f-string: keep the literal parts, drop the {placeholders}.
            out.append(
                "".join(
                    v.value
                    for v in node.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str)
                )
            )
    return out


def test_no_read_path_sources_spent_from_the_stored_column() -> None:
    """`spent` must always be computed, never read back from `user_budgets`.

    This replaces an earlier assertion that the stored column EQUALS the live
    computation. That invariant cannot hold and never could: BUDGET_SPENT_SQL is
    anchored on the current period (`date_trunc(... CURRENT_DATE)`), while the
    stored column is only rewritten when its owner next saves a transaction. The
    moment the clock crosses a month boundary every live value resets to 0 and
    every untouched stored value is a month stale — 13 budgets were in exactly
    that state on 2026-08-05, purely because July had ended. No batch job can
    close that gap, because it reopens at the next rollover.

    What actually caused the 2026-07-22 incident was not drift in the column; it
    was a query READING that column as though it were authoritative. That is a
    property of the source, it is achievable, and it is what this pins.

    Note the stored column is now write-only: `recompute_budget_spent` maintains
    it and nothing in the backend or either frontend reads it back. It is kept
    because `user_budgets` is exposed through PostgREST, where an outside
    consumer could still select it.
    """
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "app"
    offenders: list[str] = []

    for path in src.rglob("*.py"):
        for sql in _sql_literals(path):
            if "b.spent" not in sql:
                continue
            # A RETURNING clause echoes back the row the writer just wrote, which
            # is the one legitimate way the column leaves the database.
            if "RETURNING" in sql.upper():
                continue
            offenders.append(f"{path.relative_to(src.parent.parent)}: {' '.join(sql.split())[:120]}")

    assert not offenders, (
        "a query reads the stored `user_budgets.spent` column instead of "
        "computing it with BUDGET_SPENT_SQL — this is the exact defect that let "
        "two users sit ~50k over budget with no alert firing:\n  "
        + "\n  ".join(offenders)
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
