"""Finance endpoint tests (/api/finance/*, 26 routes).

The whole HTTP layer was untested. Auth is DI-overridden and services.finance is
monkeypatched, so no DB is required. We assert the HTTP contract: schema
validation, defaults, path-parameter typing, the route-ordering rule that keeps
the bulk-delete from swallowing per-item deletes, and that every write is scoped
to the caller's own user_id.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {"max_goals": 3, "max_budgets": 5, "max_bills": 5},
}
ATTACKER_ID = "00000000-0000-0000-0000-0000000000ff"


def _make_app() -> FastAPI:
    from app.api import finance as finance_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(finance_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_make_app()), base_url="http://t")


@pytest.fixture
def svc(monkeypatch):
    """Stub every finance service function and record its arguments."""
    from app.api import finance as finance_api

    calls: dict[str, list] = {}

    def stub(name, result):
        async def _fn(*args, **kwargs):
            calls.setdefault(name, []).append((args, kwargs))
            return result

        monkeypatch.setattr(finance_api.finance_service, name, _fn)

    stub("list_payment_method_labels", ["Meezan Card", "Cash"])
    stub("list_user_payment_methods", [{"id": 1, "label": "Meezan Card"}])
    stub("create_payment_method", {"id": 2, "label": "HBL Card"})
    stub("list_transactions", [{"id": 1, "merchant": "Imtiaz"}])
    stub("create_transaction", {"id": 5, "merchant": "Imtiaz"})
    stub("update_transaction", {"id": 5, "amount": 900.0})
    stub("delete_transaction", {"deleted": 5})
    stub("delete_all", {"deleted": 12})
    stub("list_goals", [{"id": 1, "name": "Hajj"}])
    stub("create_goal", {"id": 3, "name": "Hajj"})
    stub("contribute_goal", {"id": 3, "saved": 5000.0})
    stub("delete_goal", {"deleted": 3})
    stub("list_budgets", [{"id": 1, "category": "Groceries"}])
    stub("create_budget", {"id": 4, "category": "Groceries"})
    stub("update_budget", {"id": 4, "limit_amount": 20000.0})
    stub("delete_budget", {"deleted": 4})
    stub("list_bills", [{"id": 1, "name": "K-Electric"}])
    stub("create_bill", {"id": 6, "name": "K-Electric"})
    stub("update_bill", {"id": 6, "amount": 5000.0})
    stub("mark_bill_paid", {"id": 6, "status": "PAID"})
    stub("delete_bill", {"deleted": 6})
    stub("get_settings", {"monthly_income": 250000.0, "currency": "PKR"})
    stub("update_settings", {"monthly_income": 300000.0})
    stub("summary", {"month": "2026-07", "total_income": 295000.0})
    stub("income_expense_series", {"months": 6, "series": []})
    stub("spending_by_category", {"days": 30, "total": 0.0, "categories": []})
    return calls


# -------------------------------- vocabulary -------------------------------


async def test_vocabulary_serves_the_canonical_category_list(svc):
    from app.services.finance.categories import CANONICAL_CATEGORIES

    async with _client() as c:
        r = await c.get("/api/finance/vocabulary")

    assert r.status_code == 200
    body = r.json()
    # Budgets join transactions on the exact category string, so this list is
    # the contract the pickers, the email importer and the assistant share.
    assert body["categories"] == list(CANONICAL_CATEGORIES)
    assert body["transaction_types"] == ["expense", "income"]


async def test_vocabulary_includes_the_users_own_payment_methods(svc):
    async with _client() as c:
        r = await c.get("/api/finance/vocabulary")

    assert r.json()["payment_methods"] == ["Meezan Card", "Cash"]
    assert svc["list_payment_method_labels"][0][0][0] == FAKE_USER["user_id"]


# ----------------------------- payment methods -----------------------------


async def test_create_payment_method_validates_the_label(svc):
    async with _client() as c:
        ok = await c.post("/api/finance/payment-methods", json={"label": "HBL Card"})
        empty = await c.post("/api/finance/payment-methods", json={"label": ""})
        too_long = await c.post("/api/finance/payment-methods", json={"label": "x" * 81})

    assert ok.status_code == 200
    assert empty.status_code == 422
    assert too_long.status_code == 422
    assert len(svc["create_payment_method"]) == 1


# ------------------------------- transactions ------------------------------


TXN = {
    "merchant": "Imtiaz",
    "amount": 1200.0,
    "transaction_type": "expense",
    "category": "Groceries",
}


async def test_list_transactions_defaults_to_100(svc):
    async with _client() as c:
        r = await c.get("/api/finance/transactions")

    assert r.status_code == 200
    assert svc["list_transactions"][0][1]["limit"] == 100


async def test_list_transactions_honours_an_explicit_limit(svc):
    async with _client() as c:
        await c.get("/api/finance/transactions?limit=10")

    assert svc["list_transactions"][0][1]["limit"] == 10


async def test_create_transaction_scopes_to_the_caller(svc):
    async with _client() as c:
        r = await c.post("/api/finance/transactions", json=TXN)

    assert r.status_code == 200
    user_id, body = svc["create_transaction"][0][0]
    assert user_id == FAKE_USER["user_id"]
    assert body.merchant == "Imtiaz"
    assert body.source == "manual"  # documented default


@pytest.mark.parametrize(
    "body",
    [
        {**TXN, "amount": 0},          # gt=0, so zero is not a transaction
        {**TXN, "amount": -1},
        {**TXN, "merchant": ""},
        {**TXN, "merchant": "m" * 121},
        {**TXN, "category": ""},
        {**TXN, "category": "c" * 81},
        {**TXN, "transaction_type": ""},
        {**TXN, "transaction_type": "t" * 21},
        {"amount": 1, "transaction_type": "expense", "category": "Groceries"},
        {"merchant": "m", "transaction_type": "expense", "category": "Groceries"},
    ],
)
async def test_create_transaction_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/finance/transactions", json=body)

    assert r.status_code == 422
    assert "create_transaction" not in svc


async def test_update_transaction_allows_a_partial_body(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/transactions/5", json={"amount": 900})

    assert r.status_code == 200
    user_id, txn_id, body = svc["update_transaction"][0][0]
    assert (user_id, txn_id) == (FAKE_USER["user_id"], 5)
    assert body.amount == 900
    assert body.merchant is None


async def test_update_transaction_still_enforces_the_positive_amount(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/transactions/5", json={"amount": 0})

    assert r.status_code == 422


async def test_delete_transaction_scopes_to_the_caller(svc):
    async with _client() as c:
        r = await c.delete("/api/finance/transactions/5")

    assert r.status_code == 200
    assert svc["delete_transaction"][0][0] == (FAKE_USER["user_id"], 5)


# ------------------------------- bulk delete -------------------------------


@pytest.mark.parametrize("entity", ["transactions", "bills", "goals", "budgets"])
async def test_bulk_delete_forwards_the_entity(svc, entity):
    async with _client() as c:
        r = await c.delete(f"/api/finance/{entity}")

    assert r.status_code == 200
    assert svc["delete_all"][0][0] == (FAKE_USER["user_id"], entity)


async def test_per_item_delete_is_not_swallowed_by_the_bulk_route(svc):
    """DELETE /finance/{entity} must not capture /finance/transactions/5.

    `{entity}` matches a single path segment, and the per-item routes are
    declared first — if either changed, a single-row delete would silently wipe
    the whole collection.
    """
    async with _client() as c:
        await c.delete("/api/finance/transactions/5")

    assert "delete_transaction" in svc
    assert "delete_all" not in svc


async def test_per_item_goal_delete_is_not_swallowed_by_the_bulk_route(svc):
    # delete_goal is declared AFTER the bulk route, so this only works because
    # {entity} cannot span the extra "/5" segment.
    async with _client() as c:
        await c.delete("/api/finance/goals/3")

    assert "delete_goal" in svc
    assert "delete_all" not in svc


# ---------------------------------- goals ----------------------------------


GOAL = {"name": "Hajj", "target": 1_000_000}


async def test_create_goal_receives_the_whole_user_for_plan_capping(svc):
    # create_goal takes (user_id, body, user): the third argument carries
    # features.max_goals, which is how the Free-tier cap is enforced.
    async with _client() as c:
        r = await c.post("/api/finance/goals", json=GOAL)

    assert r.status_code == 200
    user_id, body, user = svc["create_goal"][0][0]
    assert user_id == FAKE_USER["user_id"]
    assert user is FAKE_USER
    assert body.emoji == "\U0001F3AF"  # documented default
    assert body.color == "bull"
    assert body.saved == 0


@pytest.mark.parametrize(
    "body",
    [
        {**GOAL, "target": 0},
        {**GOAL, "target": -1},
        {**GOAL, "saved": -1},
        {**GOAL, "name": ""},
        {**GOAL, "name": "n" * 121},
        {"target": 1000},
    ],
)
async def test_create_goal_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/finance/goals", json=body)

    assert r.status_code == 422
    assert "create_goal" not in svc


async def test_contribute_goal_coerces_the_amount_to_a_float(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/goals/3/contribute", json={"amount": "5000"})

    assert r.status_code == 200
    assert svc["contribute_goal"][0][0] == (FAKE_USER["user_id"], 3, 5000.0)


async def test_contribute_goal_defaults_a_missing_amount_to_zero(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/goals/3/contribute", json={})

    assert r.status_code == 200
    assert svc["contribute_goal"][0][0][2] == 0.0


async def test_contribute_goal_500s_on_a_non_numeric_amount(svc):
    """Documents a real rough edge, it is not an endorsement.

    The body is typed `dict`, not a pydantic model, so the route does
    `float(body.get("amount", 0))` itself. A non-numeric string raises
    ValueError inside the handler and surfaces as a 500 instead of the 422 every
    other finance write returns. Tracked for the same sweep as the other schema
    hardening; change this test to expect 422 when the body gets a model.
    """
    transport = httpx.ASGITransport(app=_make_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.patch("/api/finance/goals/3/contribute", json={"amount": "lots"})

    assert r.status_code == 500
    assert "contribute_goal" not in svc


# --------------------------------- budgets ---------------------------------


BUDGET = {"category": "Groceries", "limit_amount": 15_000}


async def test_create_budget_applies_documented_defaults(svc):
    async with _client() as c:
        r = await c.post("/api/finance/budgets", json=BUDGET)

    assert r.status_code == 200
    # Like create_goal, this receives the whole user dict so the service can
    # enforce the plan cap in features.max_budgets.
    _user_id, body, user = svc["create_budget"][0][0]
    assert user is FAKE_USER
    assert body.period == "monthly"
    assert body.spent == 0


async def test_create_budget_allows_a_zero_limit(svc):
    # ge=0 not gt=0: a zero limit is a legitimate "track but do not allow" budget.
    async with _client() as c:
        r = await c.post("/api/finance/budgets", json={**BUDGET, "limit_amount": 0})

    assert r.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {**BUDGET, "limit_amount": -1},
        {**BUDGET, "spent": -1},
        {**BUDGET, "category": ""},
        {**BUDGET, "category": "c" * 81},
        {"category": "Groceries"},
    ],
)
async def test_create_budget_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/finance/budgets", json=body)

    assert r.status_code == 422


async def test_update_budget_is_partial(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/budgets/4", json={"limit_amount": 20000})

    assert r.status_code == 200
    user_id, budget_id, body = svc["update_budget"][0][0]
    assert (user_id, budget_id) == (FAKE_USER["user_id"], 4)
    assert body.spent is None


# ---------------------------------- bills ----------------------------------


BILL = {"name": "K-Electric", "amount": 5_000}


async def test_create_bill_applies_documented_defaults(svc):
    async with _client() as c:
        r = await c.post("/api/finance/bills", json=BILL)

    assert r.status_code == 200
    _user_id, body, user = svc["create_bill"][0][0]
    assert user is FAKE_USER
    assert body.status == "UPCOMING"
    assert body.recurring is False


@pytest.mark.parametrize(
    "body",
    [
        {**BILL, "amount": 0},
        {**BILL, "amount": -1},
        {**BILL, "name": ""},
        {**BILL, "name": "n" * 121},
        {"amount": 100},
    ],
)
async def test_create_bill_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/finance/bills", json=body)

    assert r.status_code == 422


async def test_mark_bill_paid_scopes_to_the_caller(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/bills/6/paid")

    assert r.status_code == 200
    assert svc["mark_bill_paid"][0][0] == (FAKE_USER["user_id"], 6)


async def test_marking_paid_is_not_confused_with_a_generic_bill_update(svc):
    async with _client() as c:
        await c.patch("/api/finance/bills/6/paid")

    assert "update_bill" not in svc


# --------------------------------- settings --------------------------------


async def test_update_settings_is_partial(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/settings", json={"monthly_income": 300000})

    assert r.status_code == 200
    _user_id, body = svc["update_settings"][0][0]
    assert body.monthly_income == 300000
    assert body.currency is None


async def test_update_settings_rejects_a_non_numeric_income(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/settings", json={"monthly_income": "lots"})

    assert r.status_code == 422


async def test_monthly_income_of_zero_is_accepted(svc):
    # Zero is how a user clears a previously set salary; it must not be treated
    # as "unset", which would leave the old fixed income folded into the summary.
    async with _client() as c:
        r = await c.patch("/api/finance/settings", json={"monthly_income": 0})

    assert r.status_code == 200
    assert svc["update_settings"][0][0][1].monthly_income == 0


# ------------------------------- analytics ---------------------------------


async def test_summary_passes_no_month_by_default(svc):
    async with _client() as c:
        r = await c.get("/api/finance/summary")

    assert r.status_code == 200
    assert svc["summary"][0][0][0] == FAKE_USER["user_id"]
    assert svc["summary"][0][1]["month"] is None


async def test_summary_forwards_an_explicit_month(svc):
    async with _client() as c:
        await c.get("/api/finance/summary?month=2026-06")

    assert svc["summary"][0][1]["month"] == "2026-06"


async def test_income_expense_defaults_to_six_months(svc):
    async with _client() as c:
        r = await c.get("/api/finance/income-expense")

    assert r.status_code == 200
    assert svc["income_expense_series"][0][0][0] == FAKE_USER["user_id"]
    assert svc["income_expense_series"][0][1]["months"] == 6


async def test_spending_by_category_defaults_to_thirty_days(svc):
    async with _client() as c:
        r = await c.get("/api/finance/spending-by-category")

    assert r.status_code == 200
    assert svc["spending_by_category"][0][0][0] == FAKE_USER["user_id"]
    assert svc["spending_by_category"][0][1]["days"] == 30


@pytest.mark.parametrize(
    "path",
    [
        "/api/finance/income-expense?months=not-a-number",
        "/api/finance/spending-by-category?days=not-a-number",
        "/api/finance/transactions?limit=not-a-number",
    ],
)
async def test_non_integer_query_params_are_rejected(svc, path):
    async with _client() as c:
        r = await c.get(path)

    assert r.status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("patch", "/api/finance/transactions/abc"),
        ("delete", "/api/finance/transactions/abc"),
        ("delete", "/api/finance/goals/abc"),
        ("patch", "/api/finance/budgets/abc"),
        ("delete", "/api/finance/budgets/abc"),
        ("patch", "/api/finance/bills/abc"),
        ("delete", "/api/finance/bills/abc"),
        ("patch", "/api/finance/bills/abc/paid"),
    ],
)
async def test_non_integer_path_ids_are_rejected(svc, method, path):
    async with _client() as c:
        r = await getattr(c, method)(path, **({"json": {}} if method == "patch" else {}))

    assert r.status_code == 422
