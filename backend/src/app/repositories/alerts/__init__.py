"""Alerts data-access package: price alerts, app alerts, alert events + in-app
notifications, and the source reads the evaluators run over. All alerts-domain
SQL lives here; evaluator business logic stays in app.services.alerts.

Re-exports the public functions so callers keep using
`from app.repositories import alerts as repo` and call `repo.<fn>`.
"""
from app.repositories.alerts.app_alerts import (  # noqa: F401
    delete_user_alert,
    insert_user_alert,
    list_user_alerts,
    toggle_user_alert,
)
from app.repositories.alerts.evaluator import (  # noqa: F401
    fetch_all_budgets,
    fetch_all_goals,
    fetch_due_bills,
    fetch_enabled_user_alerts,
    fetch_watchlist_with_snapshot,
    get_bill_by_name,
    get_budget_by_category,
    get_goal_by_name,
    recent_event_for_alert,
    recent_watchlist_event,
)
from app.repositories.alerts.events import (  # noqa: F401
    insert_alert_event,
    insert_in_app_notification,
    list_alert_events,
    mark_event_read,
    recent_event_exists,
)
from app.repositories.alerts.price_alerts import (  # noqa: F401
    count_price_alerts,
    delete_price_alert,
    fetch_enabled_price_alerts,
    find_active_price_alert,
    insert_price_alert,
    list_price_alerts,
    mark_price_alert_triggered,
)
