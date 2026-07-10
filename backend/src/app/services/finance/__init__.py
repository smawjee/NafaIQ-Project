"""Finance service package: business logic for transactions, goals, budgets,
bills, settings, summary and series. All DB access is delegated to
app.repositories.finance; these modules hold no SQL.

Sub-features live in their own modules; this package re-exports the public
functions so callers can use `from app.services import finance as finance_service`
and call `finance_service.<fn>`.
"""
from app.services.finance.bills import (  # noqa: F401
    create_bill,
    delete_bill,
    list_bills,
    mark_bill_paid,
    update_bill,
)
from app.services.finance.budgets import (  # noqa: F401
    create_budget,
    delete_budget,
    list_budgets,
    sync_budget_spent,
    update_budget,
)
from app.services.finance.goals import (  # noqa: F401
    contribute_goal,
    create_goal,
    delete_goal,
    list_goals,
)
from app.services.finance.summary import (  # noqa: F401
    get_settings,
    income_expense_series,
    spending_by_category,
    summary,
    update_settings,
)
from app.services.finance.transactions import (  # noqa: F401
    create_transaction,
    delete_transaction,
    list_transactions,
    update_transaction,
)
