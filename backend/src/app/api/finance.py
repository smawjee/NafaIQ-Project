from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.schemas.finance import (
    BillCreate,
    BillUpdate,
    BudgetCreate,
    BudgetUpdate,
    GoalCreate,
    PaymentMethodCreate,
    SettingsUpdate,
    TransactionCreate,
    TransactionUpdate,
)
from app.services import finance as finance_service
from app.services.finance.categories import CANONICAL_CATEGORIES

router = APIRouter(tags=["finance"])


@router.get("/finance/vocabulary")
async def finance_vocabulary(user: Annotated[dict, Depends(require_user)]):
    """The controlled vocabularies a transaction write must use.

    Serves the lists the frontend pickers previously hardcoded (CATEGORIES /
    ACCOUNTS in finance.data.ts, duplicated in dashboard.data.ts) so the
    frontend, the email importer and the assistant all read one source. The
    category list matters most: budgets join transactions on the exact category
    string, so a non-canonical spelling silently never moves a budget.
    """
    return {
        "categories": list(CANONICAL_CATEGORIES),
        "payment_methods": await finance_service.list_payment_method_labels(user["user_id"]),
        "transaction_types": ["expense", "income"],
    }


@router.get("/finance/payment-methods")
async def list_payment_methods(user: Annotated[dict, Depends(require_user)]):
    return await finance_service.list_user_payment_methods(user["user_id"])


@router.post("/finance/payment-methods")
async def create_payment_method(
    body: PaymentMethodCreate,
    user: Annotated[dict, Depends(require_user)],
):
    return await finance_service.create_payment_method(user["user_id"], body)

@router.get("/finance/transactions")
async def list_transactions(user: Annotated[dict, Depends(require_user)], limit: int = 100):
    return await finance_service.list_transactions(user["user_id"], limit=limit)


@router.post("/finance/transactions")
async def create_transaction(body: TransactionCreate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.create_transaction(user["user_id"], body)


@router.patch("/finance/transactions/{txn_id}")
async def update_transaction(
    txn_id: int,
    body: TransactionUpdate,
    user: Annotated[dict, Depends(require_user)],
):
    return await finance_service.update_transaction(user["user_id"], txn_id, body)


@router.delete("/finance/transactions/{txn_id}")
async def delete_transaction(txn_id: int, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.delete_transaction(user["user_id"], txn_id)


@router.get("/finance/goals")
async def list_goals(user: Annotated[dict, Depends(require_user)]):
    return await finance_service.list_goals(user["user_id"])


@router.post("/finance/goals")
async def create_goal(body: GoalCreate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.create_goal(user["user_id"], body, user)


@router.patch("/finance/goals/{goal_id}/contribute")
async def contribute_goal(goal_id: int, body: dict, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.contribute_goal(user["user_id"], goal_id, float(body.get("amount", 0)))


@router.delete("/finance/goals/{goal_id}")
async def delete_goal(goal_id: int, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.delete_goal(user["user_id"], goal_id)


@router.get("/finance/budgets")
async def list_budgets(user: Annotated[dict, Depends(require_user)]):
    return await finance_service.list_budgets(user["user_id"])


@router.post("/finance/budgets")
async def create_budget(body: BudgetCreate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.create_budget(user["user_id"], body, user)


@router.patch("/finance/budgets/{budget_id}")
async def update_budget(budget_id: int, body: BudgetUpdate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.update_budget(user["user_id"], budget_id, body)


@router.delete("/finance/budgets/{budget_id}")
async def delete_budget(budget_id: int, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.delete_budget(user["user_id"], budget_id)


@router.get("/finance/bills")
async def list_bills(user: Annotated[dict, Depends(require_user)]):
    return await finance_service.list_bills(user["user_id"])


@router.post("/finance/bills")
async def create_bill(body: BillCreate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.create_bill(user["user_id"], body, user)


@router.patch("/finance/bills/{bill_id}")
async def update_bill(bill_id: int, body: BillUpdate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.update_bill(user["user_id"], bill_id, body)


@router.patch("/finance/bills/{bill_id}/paid")
async def mark_bill_paid(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.mark_bill_paid(user["user_id"], bill_id)


@router.delete("/finance/bills/{bill_id}")
async def delete_bill(bill_id: int, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.delete_bill(user["user_id"], bill_id)


@router.get("/finance/settings")
async def get_settings(user: Annotated[dict, Depends(require_user)]):
    return await finance_service.get_settings(user["user_id"])


@router.patch("/finance/settings")
async def update_settings(body: SettingsUpdate, user: Annotated[dict, Depends(require_user)]):
    return await finance_service.update_settings(user["user_id"], body)


@router.get("/finance/summary")
async def finance_summary(month: str | None = None, user: Annotated[dict, Depends(require_user)] = ...):
    return await finance_service.summary(user["user_id"], month=month)


@router.get("/finance/income-expense")
async def finance_income_expense(months: int = 6, user: Annotated[dict, Depends(require_user)] = ...):
    return await finance_service.income_expense_series(user["user_id"], months=months, user=user)


@router.get("/finance/spending-by-category")
async def finance_spending_by_category(days: int = 30, user: Annotated[dict, Depends(require_user)] = ...):
    return await finance_service.spending_by_category(user["user_id"], days=days, user=user)
