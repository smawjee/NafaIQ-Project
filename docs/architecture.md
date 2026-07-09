# NafaIQ Backend Architecture

Layered architecture with a single source of truth for the database schema.

## Source of truth

- **`backend/database/migrations/` (SQL) is the canonical database schema source of truth.**
  All tables, columns, constraints, indexes, RLS policies, triggers, and views are
  defined there and applied via the Supabase CLI (rooted at `backend/database/`,
  see `backend/database/config.toml`).
- Backend code **matches** the migrations; it does not define schema.
- SQLAlchemy is used in **Core / reflection / raw-SQL** mode. `app/models/` (typed
  SQLAlchemy classes) are optional/aux — they are **not** the source of truth and are
  not wired into the data path.
- Frontend types are generated from Supabase (`frontend/.../integrations/supabase/types.ts`)
  plus the API response shapes.

> Do **not** let Pydantic schemas, route files, or ORM models manage the database
> schema. If the schema must change, write a new SQL migration.

## Layers (backend/src/app)

```
api/           FastAPI routes only — thin controllers.
               No SQL, no business logic, no Pydantic DTO definitions.
               Validate input → call a service → return / translate HTTP errors.

schemas/       Pydantic request/response DTOs only (market, finance, portfolio,
               alerts, notifications, profile, zakat). Routes import from here.

services/      Business logic only — permissions, calculations, workflows,
               portfolio/finance/alerts rules, transaction orchestration.
               No SQL. Owns the unit of work via repositories.base context managers.

repositories/  ALL database access (raw SQL / SQLAlchemy Core, and the Supabase
               client for the signals domain). Functions take an executor and
               return plain Python data. No business rules.

db/            Engine / session / Supabase client setup only.

core/          (config lives at app/config.py today.)

models/        Optional aux SQLAlchemy typed models — NOT the source of truth.
```

### Dependency direction

`api → services → repositories → db`
Schemas are imported by `api` and `services`. Nothing lower imports `api`.

### Transaction boundary

`repositories/base.py` exposes three context managers so **services** own the unit
of work without importing `db/` or writing SQL:

- `connect()` — read-only connection.
- `begin()` — read-write transaction (commits on exit, rolls back on error).
- `session()` — `AsyncSession` when explicit commit / rollback control is needed
  (e.g. the zakat record insert-then-update-on-conflict retry).

Repository functions accept the executor (`AsyncConnection` or `AsyncSession`) as
their first argument, so a service can compose several repo calls plus quota checks
(`services/permissions.enforce_count_limit`) inside one transaction.

## Domain map

| Domain | Route(s) | Service | Repository |
|---|---|---|---|
| Portfolio / holdings / trades | `api/portfolio.py`, `api/portfolio_extended.py` | `services/portfolio.py` | `repositories/portfolio_repo.py` |
| Finance (txns/goals/budgets/bills/settings/series/sync) | `api/finance.py`, `api/finance_sync.py` | `services/finance_routes.py` | `repositories/finance_repo.py` |
| Zakat | `api/finance_extended.py` | `services/zakat.py` | `repositories/zakat_repo.py` |
| Alerts / events / evaluators | `api/alerts.py` | `services/alerts.py` | `repositories/alerts_repo.py` |
| Market (aggregations) | `api/market.py`, `api/market_v2.py` | `services/market.py` | `repositories/market_repo.py` |
| Signals (Supabase-cached ML) | `api/signals.py` | `services/signals.py` | `repositories/signals_repo.py` |
| Users / plan+features / plan select | `api/deps.py`, `api/profile.py` | `services/users.py`, `services/profile.py` | `repositories/user_repo.py` |
| Notifications | `api/notifications.py` | `services/notifications.py` | `repositories/notifications_repo.py` |
| Health | `api/health.py` | `services/health.py` | `repositories/health_repo.py` |

### Shared / external (intentionally not repositories)

- `services/permissions.py`, `services/symbols.py` — small cross-cutting guards
  (quota counts, symbol validation) that run against the caller's transaction.
- `services/cache.py`, `services/notifier.py`, `services/psx/*`, `scrapers/*` —
  clients for **external / live** data sources (DPS, TradingView, Supabase REST,
  email/push). `services/psx/*` still holds some read SQL and is the natural next
  domain to route through a `psx_repo` if desired.

## Rules

- No raw SQL or SQLAlchemy query logic in `api/*`.
- No business logic in `api/*`.
- No Pydantic DTOs defined in `api/*` (they live in `schemas/`).
- All DB queries live in `repositories/*`.
- Keep endpoint behavior and response shapes unchanged unless a bug requires it.
- Do not convert the project to ORM; SQL migrations stay the source of truth.
- Split large service files into domain subfolders only when it helps that domain;
  avoid unrelated global import churn.
