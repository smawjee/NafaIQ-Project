"""Admin dashboard data-access layer.

All SQL for the admin surface lives here (roles, audit, users, flags, metrics),
executed against the SQLAlchemy transaction-pooler connection — the privileged
role that can reach the RLS-denied admin_* tables. Services own the unit of
work via app.repositories.base.connect()/begin().
"""
