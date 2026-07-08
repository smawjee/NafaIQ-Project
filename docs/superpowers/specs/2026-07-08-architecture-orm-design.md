# NafaIQ — Architecture & Data Access Design

**Date:** 2026-07-08
**Status:** Approved
**Authors:** Usman Khalid

## 1. Context

NafaIQ is a PSX trading terminal + personal finance manager + AI tutor.
The current stack is working but the data-access layer (Supabase REST client
+ Pydantic) is untyped on the Python side. This design:
- Names the architecture pattern
- Documents the data-access strategy
- Adds SQLAlchemy Core to the Python service for type-safe complex queries
- Keeps Supabase REST for the high-throughput bulk-upsert path
- Keeps Supabase JS on the frontend (no changes)

## 2. Architecture pattern

**Name:** Layered Architecture with BaaS-Backed Microservices
and Read-Through Cache

### 2.1 Layers (top to bottom)

1. **Presentation Layer** — Component-Based
   - React 19 + TanStack Router + shadcn/ui
   - React Query for client-side data cache
   - Supabase Realtime channels for live updates

2. **Application Layer** — Server Functions
   - TanStack `createServerFn` for AI tutor + auth-gated calls
   - Thin glue between frontend and the Python API

3. **Microservices Layer** — Python FastAPI
   - Scrapers (DPS, TradingView, AhleTrade)
   - Read-through cache
   - ML signal engine (GBC)
   - Technical indicators (numpy)
   - **Data access:**
     - Supabase REST client for bulk writes (495 rows in 3s)
     - SQLAlchemy Core for joins, aggregations, analytics

4. **Data Layer** — BaaS (Supabase Postgres)
   - 17 tables (public + user-RLS)
   - Row Level Security enforced at the DB
   - Realtime broadcasts on `psx_market_snapshot`
   - PostgREST auto-generates REST API from schema

### 2.2 Why this is named "Layered + BaaS + Microservices"

| Component | Reason |
|---|---|
| Layered | Clear separation: Presentation -> Application -> Microservices -> Data |
| BaaS | Supabase provides DB + Auth + Realtime + Storage as a service |
| Microservices | Python FastAPI is a separate deployable from the React frontend |
| Read-Through Cache | Cache layer sits between API and external data sources (DPS, TV, AhleTrade) |

### 2.3 What this is NOT

- **Not MVC** — no controller layer, React is component-based not template-based
- **Not Clean Architecture** — no domain/application/infrastructure separation at this scale would be over-engineering
- **Not Hexagonal** — no explicit ports & adapters pattern (would be 5x files per feature for an internship project)
- **Not Serverless** — both services are long-running

## 3. Data access strategy

### 3.1 Per-layer choices

| Layer | Tool | Why |
|---|---|---|
| Python service — bulk writes | Supabase REST client | 495 rows in one HTTP call, `on_conflict=DO UPDATE` natively |
| Python service — simple key lookups | Supabase REST client | 1 round-trip, no overhead |
| Python service — complex joins | **SQLAlchemy Core (NEW)** | Type-safe, autocompleted, parameterized |
| Python service — analytics | **SQLAlchemy Core (NEW)** | Window functions, CTEs, aggregations |
| Frontend — all reads | `@supabase/supabase-js` | RLS-aware, Realtime integration |
| Frontend — user writes | `@supabase/supabase-js` | RLS-enforced, no separate auth layer |

### 3.2 SQLAlchemy Core (new)

**What it is:** A typed SQL query builder. You write Python expressions that compile to SQL. You still write the SQL — it just gets autocompleted and checked. No object mapping.

**Why Core (not full ORM):**
- Full ORM (SQLAlchemy ORM, Django) maps rows to Python objects — adds memory overhead per row. Bad for bulk writes.
- Core is just the query builder — no row-to-object overhead.
- Industry standard: SQLAlchemy Core is what most high-performance Python services use.

**What it gives us:**
- Type-checked column names (`psx_market_snapshot.c.symbol` autocompletes)
- Parameterized queries (SQL injection-safe by default)
- Composable queries (build filters programmatically)
- Connection pooling
- Async support (`sqlalchemy[asyncio]`)
- Migration tooling (Alembic) for future schema changes

**Where it does NOT replace Supabase REST:**
- Bulk upserts stay on Supabase REST (3s vs 45s with SQLAlchemy)
- Realtime hooks stay on Supabase JS (PostgREST-specific)
- Frontend stays on Supabase JS (RLS-aware, works with React Query)

### 3.3 What changes in the code

**New files:**
- `services/psx-api/app/db/sqlalchemy.py` — async engine, session factory
- `services/psx-api/app/db/orm.py` — table definitions for the 17 tables
- `services/psx-api/tests/test_sqlalchemy_queries.py` — sanity tests

**Modified files:**
- `services/psx-api/pyproject.toml` — add `sqlalchemy[asyncio]>=2.0`
- `services/psx-api/app/api/finance.py` (Phase 4) — use SQLAlchemy Core
- `services/psx-api/app/api/portfolio.py` (Phase 5) — use SQLAlchemy Core
- `services/psx-api/app/services/analytics.py` (new) — SQLAlchemy Core

**Files that DO NOT change:**
- `services/psx-api/app/db/supabase.py` — unchanged
- `services/psx-api/app/services/cache.py` — uses Supabase REST (the 3s path)
- `services/psx-api/app/scrapers/*` — still write via Supabase REST bulk upsert
- All frontend code (`src/`) — unchanged
- Supabase schema, RLS policies, Realtime publications — unchanged

### 3.4 Example: before vs after

**Before (Phase 4 finance transactions, hypothetical):**
```python
result = supabase.table("finance_transactions") \
    .select("*, finance_categories(name)") \
    .eq("user_id", user_id) \
    .gte("occurred_at", "2026-07-01") \
    .lt("occurred_at", "2026-08-01") \
    .eq("direction", "expense") \
    .execute()
```

**After (with SQLAlchemy Core):**
```python
from app.db.orm import finance_transactions, finance_categories
from sqlalchemy import select, and_

stmt = (
    select(finance_transactions, finance_categories.c.name.label("category_name"))
    .join(finance_categories, finance_transactions.c.category_id == finance_categories.c.id)
    .where(
        and_(
            finance_transactions.c.user_id == user_id,
            finance_transactions.c.occurred_at >= datetime(2026, 7, 1),
            finance_transactions.c.occurred_at < datetime(2026, 8, 1),
            finance_transactions.c.direction == "expense",
        )
    )
)
async with async_session() as session:
    rows = (await session.execute(stmt)).all()
```

## 4. Why this design over alternatives

### 4.1 Why not a full ORM (SQLAlchemy ORM, Prisma, Drizzle)?

| Reason | Detail |
|---|---|
| Bulk write performance | Supabase REST: 3s for 495 rows. SQLAlchemy ORM: ~10s. Prisma: ~30s (no native bulk). |
| Realtime | Supabase Realtime hooks (`postgres_changes`) are PostgREST-specific. Drizzle/Prisma bypass PostgREST. |
| RLS | Supabase RLS works through PostgREST. Drizzle/Prisma bypass it — you need a separate service_role key. |
| Project velocity | We've shipped Phases 1-6 in 2 weeks. Adding an ORM globally is 1-2 weeks of refactor with no user-visible benefit. |
| Existing data flow | The 5-second market refresh works perfectly. Don't fix what works. |

### 4.2 Why not the status quo (no SQLAlchemy)?

| Reason | Detail |
|---|---|
| Type safety | `supabase.table("foo").select("*")` returns a `list[dict]` — no type check. |
| Complex joins | PostgREST can do joins via embedded resources but the syntax is stringly-typed. |
| Analytics | Window functions, recursive CTEs are awkward via REST. SQLAlchemy Core writes them naturally. |
| Testability | Having a second query path makes the code more testable (mock the engine, not the HTTP client). |

## 5. Implementation order

1. Add SQLAlchemy to `pyproject.toml`, install, verify
2. Create `app/db/sqlalchemy.py` with async engine factory
3. Create `app/db/orm.py` with table definitions for the 17 tables
4. Write `tests/test_sqlalchemy_queries.py` — sanity tests
5. Wire Phase 4 Finance module to use SQLAlchemy Core
6. Wire Phase 5 Portfolio module to use SQLAlchemy Core
7. Document the choice in `recall/explaination.md` as decision #41

## 6. References

- `recall/explaination.md` — 40 prior architectural decisions
- `recall/Complete Project Plan.md` — 10-phase implementation plan
- `recall/project.md` — current architecture documentation
- `recall/PRESENTATION_PREP.md` — file-by-file breakdown
