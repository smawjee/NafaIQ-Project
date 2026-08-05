"""Finance summary: route -> service -> repository, with a fake repo layer.

Phase 3 integration coverage. The API tests in test_finance_api.py stub the
whole service; these exercise the real business logic in
services/finance/summary.py against a fake repository, so the fixed-income
arithmetic that ships in the current release is actually asserted.

Offline by design: repo functions and the connect() context manager are
monkeypatched, so no database is required.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {"max_finance_history_days": 30},
}


@contextlib.asynccontextmanager
async def _fake_conn():
    yield object()


@pytest.fixture
def repo(monkeypatch):
    """Fake repository. Tests set `repo.month_totals` / `repo.settings`."""
    # app/services/finance/__init__.py re-exports the summary() FUNCTION under
    # the name `summary`, shadowing the submodule of the same name. That makes
    # both `from app.services.finance import summary` and
    # `import app.services.finance.summary as x` bind the function, because both
    # go through attribute lookup on the package. import_module bypasses that.
    import importlib

    summary_svc = importlib.import_module("app.services.finance.summary")

    state = {
        "month_totals": {},          # month -> {"income": x, "expense": y}
        "settings": None,            # settings row or None
        "income_expense_rows": [],
    }

    async def fetch_month_totals(_conn, _uid, month):
        return state["month_totals"].get(month, {})

    async def get_settings_row(_conn, _uid):
        return state["settings"]

    async def fetch_income_expense(_conn, _uid, _months):
        return state["income_expense_rows"]

    monkeypatch.setattr(summary_svc.repo, "fetch_month_totals", fetch_month_totals)
    monkeypatch.setattr(summary_svc.repo, "get_settings_row", get_settings_row)
    monkeypatch.setattr(summary_svc.repo, "fetch_income_expense", fetch_income_expense)
    monkeypatch.setattr(summary_svc, "connect", _fake_conn)
    return state


def _make_app() -> FastAPI:
    from app.api import finance as finance_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(finance_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_make_app()), base_url="http://t")


async def _summary(month: str = "2026-07") -> dict:
    async with _client() as c:
        r = await c.get(f"/api/finance/summary?month={month}")
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------- response contract -----------------------------


async def test_response_carries_every_field_the_clients_read(repo):
    """Guards the contract both frontends depend on.

    Web reads `total_income` (Overview.tsx) and mobile's FinanceSummary type
    declares income/fixed_income/total_income. Dropping or renaming any of these
    breaks a released client silently.
    """
    repo["month_totals"] = {"2026-07": {"income": 45_000.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert set(body) == {
        "month",
        "income",
        "fixed_income",
        "total_income",
        "expenses",
        "savings",
        "savings_rate",
        "last_month_income",
        "last_month_expense",
        "last_month_savings",
    }


# --------------------------- fixed-income maths ----------------------------


async def test_fixed_income_is_added_on_top_of_earned_income(repo):
    repo["month_totals"] = {"2026-07": {"income": 45_000.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["income"] == 45_000.0        # variable, from transactions
    assert body["fixed_income"] == 250_000.0  # standing salary
    assert body["total_income"] == 295_000.0


async def test_savings_and_rate_are_derived_from_total_not_variable_income(repo):
    repo["month_totals"] = {"2026-07": {"income": 45_000.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["savings"] == 175_000.0  # 295_000 - 120_000
    assert body["savings_rate"] == pytest.approx(59.3, abs=0.05)


async def test_the_salary_also_applies_to_last_month(repo):
    """Otherwise the salary "appears out of nowhere" and every month-on-month
    delta is wrong by exactly one salary."""
    repo["month_totals"] = {
        "2026-07": {"income": 45_000.0, "expense": 120_000.0},
        "2026-06": {"income": 30_000.0, "expense": 130_000.0},
    }
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["last_month_income"] == 280_000.0  # 30_000 + 250_000
    assert body["last_month_expense"] == 130_000.0
    assert body["last_month_savings"] == 150_000.0


async def test_nothing_changes_for_a_user_with_no_salary_set(repo):
    repo["month_totals"] = {"2026-07": {"income": 45_000.0, "expense": 20_000.0}}
    repo["settings"] = None

    body = await _summary()

    assert body["fixed_income"] == 0.0
    assert body["total_income"] == body["income"] == 45_000.0
    assert body["savings"] == 25_000.0


@pytest.mark.parametrize(
    "stored,expected",
    [
        (None, 0.0),
        (0, 0.0),
        ("250000", 250_000.0),   # numeric string from the DB driver
        (-5_000, 0.0),           # negative salary clamped, never negative income
        ("not a number", 0.0),   # malformed value must not 500 the endpoint
        (250_000.5, 250_000.5),
    ],
)
async def test_monthly_income_is_coerced_defensively(repo, stored, expected):
    repo["month_totals"] = {"2026-07": {"income": 0.0, "expense": 0.0}}
    repo["settings"] = {"monthly_income": stored}

    body = await _summary()

    assert body["fixed_income"] == expected


async def test_savings_rate_is_zero_rather_than_a_division_by_zero(repo):
    repo["month_totals"] = {"2026-07": {"income": 0.0, "expense": 5_000.0}}
    repo["settings"] = None

    body = await _summary()

    assert body["savings_rate"] == 0.0
    assert body["savings"] == -5_000.0  # overspending is reported, not clamped


async def test_a_month_with_no_activity_returns_zeroes_not_an_error(repo):
    repo["month_totals"] = {}
    repo["settings"] = None

    body = await _summary()

    assert body["income"] == 0.0
    assert body["expenses"] == 0.0
    assert body["total_income"] == 0.0


# ------------------------------ month handling ------------------------------


async def test_january_rolls_back_to_december_of_the_previous_year(repo):
    repo["month_totals"] = {
        "2026-01": {"income": 10_000.0, "expense": 1_000.0},
        "2025-12": {"income": 7_000.0, "expense": 2_000.0},
    }
    repo["settings"] = None

    body = await _summary("2026-01")

    assert body["month"] == "2026-01"
    assert body["last_month_income"] == 7_000.0
    assert body["last_month_expense"] == 2_000.0


async def test_the_requested_month_is_echoed_back(repo):
    repo["month_totals"] = {}
    repo["settings"] = None

    assert (await _summary("2026-03"))["month"] == "2026-03"


# --------------------------- income/expense series --------------------------
#
# The series builds its month grid from the wall clock (summary.py anchors on
# datetime.now(timezone.utc)), so a row keyed to a hard-coded month falls off
# the grid the moment the calendar moves past it. These tests derive their
# months from the same clock instead — a literal here is a test that passes in
# the month it was written and fails silently ever after.


def _month_ago(n: int) -> str:
    """The 'YYYY-MM' key n months before the current UTC month (0 = this month)."""
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month - n
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


async def test_series_folds_the_salary_into_every_point(repo):
    """The trend chart must not show a salary spike only in the current month."""
    repo["settings"] = {"monthly_income": 100_000.0}
    repo["income_expense_rows"] = [
        {"month": _month_ago(1), "transaction_type": "income", "total": 5_000.0},
        {"month": _month_ago(1), "transaction_type": "expense", "total": 20_000.0},
        {"month": _month_ago(0), "transaction_type": "income", "total": 7_000.0},
    ]

    async with _client() as c:
        r = await c.get("/api/finance/income-expense?months=3")

    assert r.status_code == 200
    series = r.json()["series"]
    assert len(series) == 3
    for point in series:
        assert point["income"] >= 100_000.0, point


async def test_series_length_is_capped_at_twelve_months(repo):
    repo["settings"] = None
    repo["income_expense_rows"] = []

    async with _client() as c:
        r = await c.get("/api/finance/income-expense?months=99")

    assert r.status_code == 200
    assert r.json()["months"] == 12
    assert len(r.json()["series"]) == 12


async def test_series_floors_at_one_month(repo):
    repo["settings"] = None
    repo["income_expense_rows"] = []

    async with _client() as c:
        r = await c.get("/api/finance/income-expense?months=0")

    assert r.status_code == 200
    assert r.json()["months"] == 1


async def test_series_zero_fills_months_with_no_activity(repo):
    repo["settings"] = None
    repo["income_expense_rows"] = []

    async with _client() as c:
        r = await c.get("/api/finance/income-expense?months=4")

    series = r.json()["series"]
    assert len(series) == 4
    assert all(p["income"] == 0.0 and p["expense"] == 0.0 for p in series)
    # Ordered oldest-first so the chart reads left to right.
    assert [p["month"] for p in series] == sorted(p["month"] for p in series)


async def test_series_is_case_insensitive_about_the_transaction_type(repo):
    # The email importer and the assistant have both written "Income"/"INCOME";
    # the service lower-cases before bucketing.
    repo["settings"] = None
    repo["income_expense_rows"] = [
        {"month": _month_ago(0), "transaction_type": "INCOME", "total": 9_000.0},
    ]

    async with _client() as c:
        r = await c.get("/api/finance/income-expense?months=1")

    assert r.json()["series"][-1]["income"] == 9_000.0
