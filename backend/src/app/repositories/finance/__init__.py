"""Finance data-access package: transactions, goals, budgets, bills, settings,
and the summary/series aggregations. All finance-domain SQL lives here; the
service validates values and owns the transaction boundary.

Re-exports the public functions so callers keep using
`from app.repositories import finance as repo` and call `repo.<fn>`.
"""
from app.repositories.finance._common import (  # noqa: F401
    count_owned,
    delete_all_rows,
    table,
)
from app.repositories.finance.bills import (  # noqa: F401
    count_bills,
    delete_bill,
    find_duplicate_bill,
    insert_bill,
    insert_bill_dedup,
    list_bills,
    mark_bill_paid,
    update_bill,
)
from app.repositories.finance.budgets import (  # noqa: F401
    BUDGET_SPENT_SQL,
    count_budgets,
    delete_budget,
    get_budget,
    insert_budget,
    list_budgets,
    recompute_budget_spent,
    update_budget,
)
from app.repositories.finance.goals import (  # noqa: F401
    contribute_goal,
    count_goals,
    delete_goal,
    insert_goal,
    list_goals,
)
from app.repositories.finance.payment_methods import (  # noqa: F401
    list_payment_methods,
    upsert_payment_method,
)
from app.repositories.finance.settings import (  # noqa: F401
    get_settings_row,
    upsert_settings,
)
from app.repositories.finance.summary import (  # noqa: F401
    fetch_income_expense,
    fetch_month_totals,
    fetch_spending,
)
from app.repositories.finance.transactions import (  # noqa: F401
    delete_transaction,
    absorb_transaction,
    find_duplicate_transaction,
    fill_missing_correlation_fields,
    find_reversal_target,
    get_transactions_by_ids,
    insert_transaction,
    insert_transaction_dedup,
    list_transactions,
    update_transaction,
)
