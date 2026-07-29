"""Alerts service package: app-alert & price-alert CRUD, event history, and the
price/bill/budget/goal evaluators. Business logic only — all SQL is delegated
to app.repositories.alerts.

Re-exports the public functions so callers keep using
`from app.services import alerts as alerts_service` (and
`from app.services.alerts import evaluate_all` from the scheduler).
"""
from app.services.alerts.app_alerts import (  # noqa: F401
    create_user_alert,
    delete_alert,
    list_alerts,
    toggle_alert,
)
from app.services.alerts.evaluator import (  # noqa: F401
    evaluate_all,
    evaluate_price_alerts,
    evaluate_user_alerts,
    evaluate_watchlist_moves,
)
from app.services.alerts.events import (  # noqa: F401
    list_alert_events,
    mark_event_read,
    record_event,
)
from app.services.alerts.price_alerts import (  # noqa: F401
    create_price_alert,
    delete_price_alert,
)
