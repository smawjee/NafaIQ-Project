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
        # Per-month nets BEFORE the requested month, feeding the carried-forward
        # balance. Empty by default so these tests keep describing one month.
        "prior_month_nets": [],
    }

    async def fetch_month_totals(_conn, _uid, month):
        return state["month_totals"].get(month, {})

    async def get_settings_row(_conn, _uid):
        return state["settings"]

    async def fetch_income_expense(_conn, _uid, _months):
        return state["income_expense_rows"]

    async def fetch_month_nets_before(_conn, _uid, _month, since=None):
        return state["prior_month_nets"]

    monkeypatch.setattr(summary_svc.repo, "fetch_month_totals", fetch_month_totals)
    monkeypatch.setattr(summary_svc.repo, "get_settings_row", get_settings_row)
    monkeypatch.setattr(summary_svc.repo, "fetch_income_expense", fetch_income_expense)
    monkeypatch.setattr(summary_svc.repo, "fetch_month_nets_before", fetch_month_nets_before)
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
        "opening_balance",
        "carried_over",
        "available_balance",
    }


# --------------------------- fixed-income maths ----------------------------


async def test_an_unrecorded_salary_is_added_to_incidental_income(repo):
    """Recorded income BELOW the salary means the salary never landed as a
    transaction, so it is added on top rather than replaced.

    Treating the salary as a pure fallback here let one small credit suppress
    it outright — a user with PKR 32,887 of incidental income against a 215,000
    salary was reported at a -22% savings rate.
    """
    repo["month_totals"] = {"2026-07": {"income": 45_000.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["income"] == 45_000.0         # variable, from transactions
    assert body["fixed_income"] == 250_000.0  # still reported, for display
    assert body["total_income"] == 295_000.0


async def test_a_recorded_salary_is_not_counted_twice(repo):
    """Recorded income at or above the salary already contains it."""
    repo["month_totals"] = {"2026-07": {"income": 260_000.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["total_income"] == 260_000.0  # NOT 510_000


async def test_the_salary_stands_in_when_nothing_was_recorded(repo):
    repo["month_totals"] = {"2026-07": {"income": 0.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["total_income"] == 250_000.0


async def test_savings_and_rate_are_derived_from_total_income(repo):
    repo["month_totals"] = {"2026-07": {"income": 0.0, "expense": 120_000.0}}
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["savings"] == 130_000.0  # 250_000 - 120_000
    assert body["savings_rate"] == pytest.approx(52.0, abs=0.05)


async def test_last_month_resolves_by_the_same_rule(repo):
    """Both months must use the same income rule, or every month-on-month delta
    compares like with unlike."""
    repo["month_totals"] = {
        "2026-07": {"income": 45_000.0, "expense": 120_000.0},
        "2026-06": {"income": 30_000.0, "expense": 10_000.0},
    }
    repo["settings"] = {"monthly_income": 250_000.0}

    body = await _summary()

    assert body["last_month_income"] == 280_000.0  # 30_000 + the 250_000 salary
    assert body["last_month_expense"] == 10_000.0
    assert body["last_month_savings"] == 270_000.0


async def test_carried_forward_balance_rolls_prior_months_into_this_one(repo):
    """Without this the app resets to zero every month and can only ever
    describe the current one — July's unspent balance vanished on 1 August."""
    repo["month_totals"] = {"2026-07": {"income": 50_000.0, "expense": 20_000.0}}
    repo["settings"] = {"monthly_income": 0.0, "opening_balance": 10_000.0}
    repo["prior_month_nets"] = [
        {"month": "2026-05", "income": 40_000.0, "expense": 15_000.0},
        {"month": "2026-06", "income": 60_000.0, "expense": 25_000.0},
    ]

    body = await _summary()

    assert body["opening_balance"] == 10_000.0
    assert body["carried_over"] == pytest.approx(70_000.0, abs=0.01)  # 10k + 25k + 35k
    assert body["savings"] == 30_000.0                                # this month alone
    assert body["available_balance"] == pytest.approx(100_000.0, abs=0.01)


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


async def test_series_reconciles_the_salary_per_month(repo):
    """Each month reconciles independently, so the bars vary.

    This used to assert every point was >= the salary because the salary was
    added to all of them unconditionally — which is why six months of the chart
    rendered as six identical bars no matter what happened in each.
    """
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
    by_month = {p["month"]: p for p in series}
    # Recorded income below the salary means the salary never landed as a
    # transaction, so it is added on top.
    assert by_month[_month_ago(1)]["income"] == 105_000.0
    assert by_month[_month_ago(0)]["income"] == 107_000.0
    # The month with nothing recorded is the salary alone.
    assert by_month[_month_ago(2)]["income"] == 100_000.0
    # The bars must not all be identical — that was the visible symptom of the
    # old unconditional-add rule.
    assert len({p["income"] for p in series}) > 1


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
