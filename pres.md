# NafaIQ Backend — Presentation Prep Made Easy

> **Who this is for:** You, presenting the NafaIQ backend at Folio3 tomorrow.
> **This week's scope:** Deliverable 2 (Backend CRUD APIs) + Deliverable 3 (Project Integration).
> Everything below is grounded in the actual code as of the latest `dev` (commit `70410c4`, 2026-07-10) — every claim has a `file:line` you can open live if challenged.
> Backend root: `backend/src/app/` unless stated otherwise.

---

# 1. The 10-Minute Presentation Flow

## 1.1 Project Overview (1–2 min)

**The pitch (say this almost verbatim):**

> "NafaIQ is a Pakistan Stock Exchange trading terminal, personal finance manager, and AI financial tutor — delivered as a Progressive Web App. Tagline: *Smart Trading, Smarter Wealth.*
>
> It exists because Pakistani retail investors face three problems no existing tool solves: **there is no free public PSX API** — all market data must be scraped; **PKR devaluation makes nominal gains misleading** — a 12% PSX gain can be a −3.2% real USD return; and **there are no PKR-native, halal-aware finance tools**. NafaIQ answers all three: a live 495-stock PSX terminal fed by our own scraping pipeline, *Haqeeqi Daulat™* — devaluation-adjusted real wealth tracking, plus budgets, bills, goals, Zakat calculation, and Urdu-first financial education."

**Key numbers to drop naturally:**
- **~56 REST endpoints** across 12 routers, all under `/api`
- **~29 Postgres tables**, every one with Row-Level Security enabled
- **497 live PSX symbols** served from the real scraping pipeline (verified in the 2026-07-09 audit)
- **8 background jobs** keep market data fresh (fastest: every 5 seconds during market hours)
- **36 backend tests** (pytest), typecheck/lint/build all green end-to-end
- **4-layer backend**: routes → services → repositories → database
- Freemium model: **Free / Pro / Premium** plans, enforced server-side

**This week's deliverables, in one sentence each:**
- *Deliverable 2 — Backend CRUD APIs:* full Create/Read/Update/Delete REST APIs for portfolios, holdings, stock trades, finance transactions, budgets, bills, goals, Zakat, and alerts — with Pydantic validation, layered error handling, and plan-based authorization.
- *Deliverable 3 — Project Integration:* those APIs are wired to Supabase Postgres through a clean repository layer, the market-data pipeline writes into the same database the frontend reads in realtime, and one buy order atomically updates three tables across two product domains.

---

## 1.2 Backend Tech Stack & Architecture Rationale

| Technology | What it is | Why it was chosen (the rationale to speak to) |
|---|---|---|
| **Python 3.12+ / FastAPI** (`pyproject.toml:11`) | Async web framework | Async-first (scrapers long-poll external feeds), automatic OpenAPI docs at `/docs`, and Pydantic validation built into the request path. Python was non-negotiable anyway: BeautifulSoup + lxml is the gold standard for scraping DPS's malformed HTML, numpy powers the indicator math, and scikit-learn powers the ML signal engine — one language for API + scraping + ML. |
| **Uvicorn** | ASGI server | Standard production pairing for FastAPI; `[standard]` extras give uvloop event loop for throughput. |
| **Supabase (Postgres)** | Database + Auth + Realtime | Three services in one: managed Postgres, JWT-issuing auth, and websocket Realtime — and it's open-source/self-hostable, so no vendor lock-in. Crucially it means **the backend never built its own auth or websocket layer**: Supabase issues the JWTs we verify, and broadcasting live prices is just "write a row to Postgres." |
| **Hybrid data access: supabase-py + SQLAlchemy Core** | Two DB clients, deliberately | The flagship decision (see §1.6). Supabase's REST client for bulk upserts from scrapers (495 rows in one HTTP call — dropped refresh time **from ~45s to ~3s**); async SQLAlchemy Core over asyncpg for user CRUD, joins, and aggregations. Full declarative ORM was rejected: schema truth lives in SQL migrations, so tables are **auto-reflected at startup** (`db/orm.py`) — zero model-drift maintenance. |
| **Pooled asyncpg engine over the Supavisor transaction pooler** (`db/sqlalchemy.py:30-37`) | Connection management | An app-side pool (`pool_size=10, max_overflow=20, pool_pre_ping=True`) over Supabase's transaction pooler on port 6543, with `statement_cache_size=0` because transaction-mode pooling doesn't support prepared statements. `pool_pre_ping` validates connections before use, so a dropped pooler connection recovers transparently. Knowing *why* those settings exist is a detail seniors respect. |
| **APScheduler** (`jobs/scheduler.py`) | In-process job scheduler | Celery needs a broker (Redis/RabbitMQ) — overkill; external cron can't run 5-second loops. APScheduler runs inside the API process; Railway runs exactly **1 replica** so jobs never duplicate. |
| **Two-tier caching: in-process TTL cache + Postgres read-through** (`services/memcache.py`, `services/cache.py`) | Latency control | Hot market reads hit a tiny in-process stale-while-revalidate cache first (no network at all), backed by the Postgres read-through layer the scheduler keeps warm. No Redis needed — see §1.5. |
| **Pydantic v2 + pydantic-settings** | Validation + config | Request schemas live in a dedicated `schemas/` package with declarative constraints (`Field(gt=0, max_length=120)`); config loads from `.env` with typed fields (`config.py`). |
| **slowapi** | Rate limiting | 60 req/min default per client IP, 30/min on heavy market endpoints (`middleware/rate_limit.py`). |
| **PyJWT + JWKS** | Auth verification | Verifies Supabase user JWTs — supports both the current asymmetric keys (RS256/ES256 via a cached JWKS client) and legacy HS256 (`services/auth.py`). Exposed to OpenAPI as an `HTTPBearer` security scheme (`api/deps.py:9`), so Swagger UI's Authorize button works. |
| **structlog** | Logging | JSON logs in production, pretty console in debug — plus a timing middleware that logs latency for every hot market endpoint (`main.py:129-142`). |
| **httpx + BeautifulSoup4 + lxml** | Scraping | Async HTTP + battle-tested HTML parsing for DPS's broken markup. |
| **GZip middleware** (`main.py:106`) | Payload compression | The market snapshot is ~500 rows of JSON; gzip cuts it to a fraction on the wire. |
| **Docker + Railway** | Deployment | `backend/Dockerfile` → `railway.json` (1 replica, restart on failure). |

**Trade-offs you consciously accepted (saying these unprompted = seasoned engineer):**
- In-process scheduler couples API and jobs — fine at 1 replica, needs a worker split to scale horizontally.
- No Redis — hot data lives in process memory with short TTLs, persistent truth in Postgres. Two fewer services to operate.
- Raw SQL / Core over ORM trades some abstraction for explicit, reviewable queries — every one parameterized, and all of it now lives in one auditable place: the `repositories/` layer.

---

## 1.3 Backend Architecture & Folder Structure

**The one-diagram mental model (draw this on the whiteboard):**

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                    FastAPI process                        │
 Browser/Mobile  │  ┌────────┐  ┌──────────┐  ┌──────────────┐  ┌───────┐   │
 ──HTTP+JWT────► │  │ api/   │─►│ services/│─►│ repositories/│─►│ db/   │   │──► Supabase
                 │  │ (HTTP) │  │ (rules)  │  │ (all SQL)    │  │ (conn)│   │    Postgres
                 │  └────────┘  └──────────┘  └──────────────┘  └───────┘   │      │
                 │  ┌──────────────────────────────────────────────────┐    │      │ Realtime
 DPS / TradingView│ │ jobs/scheduler (8 jobs) ──► scrapers/            │    │      ▼
 / AhleTrade ◄────┼─┤ every 5s…weekly           bulk upsert ───────────┼────┘   Browser gets
                 │  └──────────────────────────────────────────────────┘       live prices
                 └──────────────────────────────────────────────────────────┘
```

**Folder-by-folder (intern-friendly):**

```
backend/
├── database/migrations/   # 21 SQL files — THE source of truth for schema
├── tests/                 # 36 pytest tests across 7 files
└── src/app/
    ├── main.py            # App assembly: middleware, 12 routers, lifespan (reflect DB + start jobs)
    ├── config.py           # pydantic-settings: typed env config, .env discovery
    ├── api/               # HTTP layer — thin routers + deps.py (HTTPBearer auth dependency)
    ├── middleware/        # auth.py (bearer-token gate), rate_limit.py (slowapi)
    ├── schemas/           # Pydantic request/response models (transport shapes, NOT DB models)
    ├── services/          # Business rules: finance/, portfolio/, market/, alerts/ packages + permissions, cache…
    ├── repositories/      # ALL SQL lives here: finance/, portfolio/, alerts/, market/ + base.py (txn helpers)
    ├── db/                # Connection primitives: supabase.py (REST client), sqlalchemy.py (pooled engine), orm.py (reflection)
    ├── scrapers/          # dps.py, tradingview.py, ahletrade.py — external data in
    ├── jobs/              # scheduler.py — APScheduler wiring
    └── ml/                # signal model features
```

**Why this structure (the reasoning):**
- **Layering is `api → services → repositories → db`** — the classic repository pattern. Routes handle HTTP concerns only (a budget route is 2 lines: parse, delegate — `api/finance.py:72-74`). Services hold business rules and decide status codes (`services/finance/budgets.py:36-46`). Repositories hold *every* SQL statement (`repositories/finance/budgets.py`) and return rows or `None` — they never raise HTTP errors. `db/` holds connection primitives.
- **Transaction boundaries are explicit and reusable**: `repositories/base.py:22-38` provides `connect()` (read-only), `begin()` (auto-commit/rollback transaction), and `session()` (multi-step unit of work, caller commits). A service opens one `begin()` and every repository call inside shares that transaction.
- **`schemas/` is Pydantic, not ORM** — a deliberate separation: what the API speaks (transport) vs. what the DB stores (owned by SQL migrations, reflected at runtime). The old `models/` package still exists as deprecated re-export shims for backwards compatibility (`models/finance.py:1-6`) — a nice example of a migration done without breaking imports.
- **`services/calculations.py` is pure functions** — no I/O, no DB. All P&L math is unit-testable without a database.
- **Startup flow** (`main.py:56-64`): lifespan hook reflects all table schemas from the live DB, starts the scheduler, then logs a data-quality warning for any symbol with under 20 days of price history. The app literally checks its own data health on boot.

---

## 1.4 CRUD APIs & Best Practices *(Deliverable 2)*

**Headline:** ~56 routes, 12 routers, all mounted under `/api` (`main.py:147-158`). Full CRUD exists for: portfolios, holdings, stock transactions, finance transactions, budgets, bills, goals, Zakat settings/records, alerts, price alerts, and notification preferences.

### The four CRUD verbs on one entity (Holdings)

| Verb | Route | The senior-engineer detail |
|---|---|---|
| **C** | `POST /api/portfolio/{id}/holdings` | Service orchestrates in one transaction (`services/portfolio/holdings.py:40-52`): ownership check → symbol validated against the real PSX universe → plan limit → **idempotent upsert with weighted-average cost computed in SQL**: `ON CONFLICT (portfolio_id, symbol) DO UPDATE SET shares = … + EXCLUDED.shares, avg_cost = (old_cost×old_shares + new_cost×new_shares) / NULLIF(total, 0)` (`repositories/portfolio/holdings.py:79-86`) |
| **R** | `GET /api/portfolio/{id}/holdings` | 404 if the portfolio isn't yours — checked *before* touching children |
| **U** | `PATCH /api/portfolio/{id}/holdings/{hid}` | Ownership via a JOIN to the parent (`repositories/portfolio/holdings.py:51-64`); only the fields you send change; empty patch → 400 (`services/portfolio/holdings.py:66-71`) |
| **D** | `DELETE .../holdings/{hid}` | Ownership enforced **inside the DELETE itself**: `DELETE … USING psx_portfolios WHERE … AND p.user_id = :uid RETURNING h.id` (`repositories/portfolio/holdings.py:131-137`) — one atomic statement detects "not found OR not yours" |

### Request validation — three layers

**Layer 1: Pydantic models with field constraints** (auto-422 on violation), all in `schemas/`:

```python
# schemas/finance.py:6-13
class TransactionCreate(BaseModel):
    merchant: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    transaction_type: str = Field(..., min_length=1, max_length=20)
    category: str = Field(..., min_length=1, max_length=80)
```

```python
# schemas/portfolio.py:71-80 — regex-pattern enum validation
class StockTransactionCreate(BaseModel):
    side: str = Field(..., pattern="^(buy|sell|adjust)$")
    quantity: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    fees: float = Field(0, ge=0)
```

Bonus detail: `HoldingCreate` requires `shares` and `avg_cost` **strictly positive** (`gt=0`), with a comment explaining why — a 0-cost holding produces a fake +∞% gain and pollutes portfolio aggregates (`schemas/portfolio.py:14-20`). Validation rules encode *business* reasoning, not just types.

**Layer 2: Semantic/domain validation in services** (400 with a helpful message):
- Unknown ticker rejection — `services/symbols.py:21-27`: `"Unknown PSX symbol 'FAKE'. Enter a valid listed ticker."` (existence SQL delegated to `repositories/market`)
- Sell-more-than-you-own → 400 with the actual owned quantity (`services/portfolio/trades.py:62-72`)
- Categories normalized server-side (`.strip().lower()`) so "Groceries" and "groceries" are one budget (`services/finance/budgets.py:40-41`)
- Plan-aware clamping: finance history queries are capped by the user's `max_finance_history_days`

**Layer 3: Database CHECK constraints as backstop** — the DB re-enforces what Pydantic checks: `CHECK (side IN ('buy','sell','adjust'))`, `CHECK (quantity > 0)`, `CHECK (saved <= target)` (migrations `stock_transactions.sql`, hardening migration). *Defense in depth: bad data can't get in even if a code path misses validation.*

### Error handling & status codes actually used

| Code | Meaning here | Live example |
|---|---|---|
| 200 | Success (creates return the full row via SQL `RETURNING`; deletes return `{"deleted": id}`) | everywhere |
| 400 | Semantic errors: empty PATCH, invalid enum, unknown ticker, overselling | `services/finance/budgets.py:39`, `services/symbols.py:24` |
| 401 | Missing/invalid JWT — **deliberately clean 401, not 422** | `api/deps.py:25,29` |
| 403 | Plan limits & tier gates: `"Budgets limit reached for Free plan"` | `services/permissions.py:120-124` |
| 404 | Missing **or not-owned** resource — same response, so the API never leaks whether a resource exists | `services/finance/budgets.py:45,53`; `services/portfolio/holdings.py:70,78` |
| 422 | Pydantic auto-validation (negative shares, bad types, oversized strings) | automatic |
| 429 | Rate limit exceeded (slowapi handler registered at `main.py:144-145`) | market routes |
| 503 | Server misconfiguration (missing JWT secret / API token) | `services/auth.py`, `middleware/auth.py` |

**The pattern to name out loud — "repositories return rows, services decide status codes":** every mutation ends with SQL `RETURNING`; the repository returns the row or `None`; the service maps `None` to 404. One round-trip checks existence + ownership + performs the write:

```python
# repositories/finance/budgets.py:66-77 — the data layer
result = await conn.execute(
    update(budgets)
    .where(budgets.c.id == budget_id, budgets.c.user_id == uid)
    .values(**values)
    .returning(budgets)
)
row = result.mappings().first()
return _budget(row) if row else None

# services/finance/budgets.py:42-46 — the decision layer
async with begin() as conn:
    row = await repo.update_budget(conn, uid, budget_id, values)
if not row:
    raise HTTPException(404, "Budget not found")
```

**Graceful degradation around external systems:** scraper and signal-cache failures are caught and logged, never bubbled to users; the auth plan-lookup falls back to Free-tier defaults if the DB hiccups. *External flakiness degrades quality of service, never availability.*

### Authorization (beyond authentication)

Every user query is scoped three ways depending on shape: `WHERE user_id = :uid` filters, pre-flight parent-ownership checks, or ownership folded into the mutation itself. Plan quotas are enforced *before* every create via `check_count_limit` (`services/permissions.py:107-124`) — its docstring is a talking point in itself: *"Pure business rule — the caller passes the current count (obtained from a repository), keeping SQL out of the permission layer."* Portfolios, holdings, budgets, bills, goals, price alerts all have per-plan caps (Free: 1 portfolio, 20 holdings, 5 budgets…). This is **real server-side enforcement, not hidden-button theater**.

---

## 1.5 Database Integration & Data Flow *(Deliverable 3)*

### The two-path data access story (lead with this)

> "The backend talks to the same Supabase Postgres over two deliberate paths, chosen per workload."

**Path A — pooled async SQLAlchemy via the transaction pooler** (`db/sqlalchemy.py:30-37`): all user-facing CRUD, through the repositories layer. Direct Postgres, parameterized SQL, real transactions.

**Path B — supabase-py REST client with the service key** (`db/supabase.py`): background jobs and the read-through cache. One HTTP call bulk-upserts 495 market rows with `on_conflict="symbol"`.

**Path C — the frontend itself** talks to Supabase directly with the anon key for some tables (watchlist, realtime subscriptions) — and *that's* where RLS + database triggers are the enforcement layer. Because paths A/B use privileged credentials, **application SQL enforces user scoping** (`WHERE user_id = :uid` from the verified JWT), while RLS `WITH CHECK` policies protect the frontend-direct path and act as defense in depth.

### One write, traced end-to-end: `POST /api/portfolio/transactions` (buy a stock)

This is the richest flow in the system — **one HTTP request atomically updates three tables across two product domains**, and after the refactor each hop lives in exactly the layer you'd expect:

1. **Route** — a 3-line controller (`api/portfolio_extended.py:56-63`) that parses `StockTransactionCreate` and delegates. Auth via `require_user` (`api/deps.py`): Supabase JWT verified against JWKS, `user_id` from the `sub` claim, plan + limits hydrated with one `profiles LEFT JOIN plan_features` query.
2. **Validation** — Pydantic rejects `side: "hold"` or `quantity: -5` with a 422 before Postgres ever sees it (`schemas/portfolio.py:71-80`). The same rules exist as DB CHECK constraints.
3. **Service orchestration, one unit of work** — `services/portfolio/trades.py:48-116` opens a single session and runs: portfolio ownership (404) → ticker is a real PSX symbol (400) → plan limit on buys (403) → sell-side "insufficient shares" check (400).
4. **Write 1** — insert the lot into `stock_transactions` … `RETURNING id` (`repositories/portfolio/trades.py:44-81`).
5. **Write 2** — upsert the aggregated position in `psx_holdings`: buys recompute **weighted average cost** `(old_cost×old_shares + price×qty) / new_shares` (`services/portfolio/trades.py:22-45`); a sell that reaches 0 shares deletes the row.
6. **Write 3** — mirror into personal finance: a buy inserts an `expense` row in `user_transactions` with `category='Investment'`, `source='stock_trade'`, and a `stock_transaction_id` FK linking the two domains (`repositories/portfolio/trades.py:96-101`).
7. **Single `commit()`** (`services/portfolio/trades.py:115`) — all three writes succeed or none do. Response: the serialized transaction row, 200.

And the subtle part that shows real engineering: those mirrored `source='stock_trade'` rows appear in the transaction feed but are **excluded from every personal-finance expense aggregation** (monthly summary, spending-by-category, budget spent) — buying stock is an asset transfer, not spending. There's a dedicated end-to-end test for exactly this (`tests/test_stock_trade_exclusion.py`).

### One read, traced: `GET /api/portfolio/networth`

One CTE query joins **user data to market data** (`repositories/portfolio/valuation.py:56-117`): holdings ⋈ portfolios (scoped by `user_id`) ⟕ live snapshot ⟕ latest EOD close, computing prices in SQL. The price fallback chain is *inside the SQL*: `COALESCE(live_snapshot.price, latest_eod_close, avg_cost)` — "unpriceable holdings read flat instead of a spurious −100% loss" (this fixed a real bug found in the audit). The math on top is pure Python in `services/portfolio/networth.py`. These queries are backed by purpose-built indexes added in migration `20260712110000_performance_indexes.sql` — e.g. `idx_psx_ohlcv_symbol_date_desc ON psx_ohlcv (symbol, date DESC)` exists specifically to serve the `DISTINCT ON` reads in this file.

### The ingestion pipeline (this is "Project Integration" in one story)

> "There is no PSX API. So the backend *is* the API."

- **3 scrapers**: DPS (official PSX portal — market watch, 10y OHLCV, fundamentals, announcements; polite: `Semaphore(2)`, retry+backoff), TradingView scanner (sectors + logos for ~500 stocks), AhleTrade (real-time trade feed).
- **8 scheduled jobs** (`jobs/scheduler.py:276-286`): market snapshot every **5s** (only during PKT market hours, Mon–Fri 09:30–15:30), AhleTrade patch every 5s, TradingView every 5min, announcements every 15min, alert evaluation every 60s, OHLCV backfill nightly 02:00, index EOD nightly 01:00, fundamentals weekly Sunday 04:00.
- **All writes are idempotent upserts** keyed on natural keys (`symbol`, `symbol+date`, `code+date`) — a job can run twice with zero duplication.
- **Two-tier caching** — the refactor's biggest performance upgrade:
  - **Tier 1, in-process** (`services/memcache.py`): a tiny TTL cache with **stale-while-revalidate** semantics — fresh hit returns instantly; expired hit returns the stale value immediately and refreshes in the background; cold miss uses a **single-flight lock** so concurrent requests don't stampede the loader. Hot reads (snapshot 5s TTL, sectors 15s, index 60s — `services/market/_base.py:14-24`) never pay a network round-trip.
  - **Tier 2, Postgres read-through** (`services/cache.py:33-39`): serve from Supabase if fresh, else scrape + write — and even here, stale data is served immediately with the scrape moved to a background task, throttled to one scrape per resource per 60s. A user request only ever *waits* on a live scrape if the table is completely empty.
  - There's even a timing middleware logging per-request latency on hot market paths (`main.py:126-142`) — added specifically to measure the before/after of this cache work. Measured, not guessed.
- **Realtime for free**: `psx_market_snapshot` is in the `supabase_realtime` publication — the 5-second upsert **pushes live prices to every open browser tab via websocket with zero extra backend code**.

### Frontend integration readiness

- **CORS is config-driven** (`main.py:110-123`): `settings.cors_origins` takes a comma-separated origin list; when specific origins are configured, credentials are enabled; a wildcard automatically *disables* credentials (browsers reject wildcard+credentials, and it's unsafe). The code comment explains the reasoning inline.
- OpenAPI docs are public at `/docs`, and since user auth is a declared `HTTPBearer` security scheme, **Swagger's Authorize button works** — the interactive docs are fully self-serve for the frontend team.
- Consistent shapes: snake_case JSON, Decimals coerced to floats, dates to strings, errors always `{"detail": ...}` with correct codes. Big payloads gzip-compressed (`main.py:106`).
- The web client mirrors the auth design exactly (`lib/psx/client.ts`): market calls carry the shared API token; user calls attach the Supabase session JWT.

---

## 1.6 Design Decisions & Justifications

Rehearse these six; each is a decision → reasoning → trade-off triple.

1. **Separate Python service instead of doing everything in TypeScript.** Scraping (BeautifulSoup/lxml), numerics (numpy), and ML (scikit-learn) are Python's home turf; the frontend stays a clean consumer. Trade-off: two codebases — accepted for independent scaling and the right tool per job.

2. **Repository pattern with explicit transaction helpers.** All SQL lives in `repositories/`; services hold business rules and status-code decisions; routes are 2–3 line HTTP adapters. `repositories/base.py` gives three composable primitives — `connect()` (read), `begin()` (transaction), `session()` (multi-step unit of work) — so a service can wrap several repository calls in one atomic transaction. Benefits: every query is auditable in one place, services are testable without HTTP, and swapping data-access details never touches business logic.

3. **Hybrid data access (decision #41 in the project's decision log — `explaination.md`).** Supabase REST for bulk upserts (495 rows/1 call, 45s→3s), SQLAlchemy Core for typed joins and transactions, **no declarative ORM** — schema truth is SQL migrations, reflected at startup (`db/orm.py`). Named pattern: *"Layered Architecture with BaaS-Backed Microservices and Read-Through Cache."*

4. **Two-token auth model** (`middleware/auth.py` + `api/deps.py`). Machine endpoints (market data) take a shared `PSX_API_TOKEN` — like a building keycard. User endpoints require a per-user Supabase JWT verified against Supabase's JWKS, declared as an OpenAPI `HTTPBearer` security scheme. Public: only `/health`, `/docs`. Rationale: market data has no user context; user data must be identity-scoped.

5. **Postgres *is* the persistent cache and the message bus; process memory is the hot cache.** No Redis: hot reads live in an in-process TTL cache with stale-while-revalidate (`memcache.py`), persistent truth in Postgres, live fan-out via Supabase Realtime. Fewer moving parts, one backup story, one consistency model.

6. **Plan enforcement lives server-side, at two depths.** API writes go through `check_count_limit` (403 on quota); the frontend-direct watchlist path is guarded by a `SECURITY DEFINER` database trigger; a `prevent_profile_plan_self_update` trigger stops users upgrading their own plan even with direct DB access — and the *legitimate* plan-change path is the new `POST /api/profile/plan` endpoint, which runs on the backend's privileged connection and stamps `plan_selected_at` (migration `20260712030000`). UI gating is UX; the server and the database are the law.

**Bonus war story (if time allows):** the 2026-07-07 security hardening — a service key had been committed to git; keys were rotated to the new `sb_secret_`/`sb_publishable_` format, `.gitignore` fixed, and an RLS audit found `USING`-only policies that let a user UPDATE a row's `user_id` to someone else — closed by adding `WITH CHECK` to every policy (migration `20260707100000_rls_with_check_fix.sql`). Owning a fixed mistake reads as maturity, not weakness.

---

## 1.7 Quick Demo Script (1–2 min)

**Demo: full CRUD on Budgets — plus the error handling.** Chosen because it needs no market data, no valid tickers, exercises all four verbs, and shows off 422/400/404/401/403 on demand.

**Prep before the meeting:** start the backend (`uvicorn app.main:app` from `backend/`), sign in once from a terminal to mint a JWT, and open **http://localhost:8000/docs**.

**In Swagger UI:** click the green **Authorize** button (top right), paste the raw `eyJ...` token (without the word "Bearer" — the scheme adds it), Authorize → Close. Every user endpoint now sends your token automatically.

The sequence (each row is one "Try it out → Execute"):

| # | Endpoint | Body | Expected — what to say |
|---|---|---|---|
| 1 | `POST /api/finance/budgets` | `{"category": "Groceries", "limit_amount": 50000, "period": "monthly"}` | **200** + full row — "create returns the row via SQL RETURNING; note the category was normalized to lowercase server-side" |
| 2 | `GET /api/finance/budgets` | — | **200** — "scoped to my user_id from the JWT; `spent` is computed live from this month's actual transactions" |
| 3 | `PATCH /api/finance/budgets/{id}` | `{"limit_amount": 60000}` | **200** — "true PATCH: only the field I sent changed" |
| 4 | `POST /api/finance/budgets` | `{"category": "Fuel", "limit_amount": 10000, "spent": -5}` | **422** — "Pydantic `ge=0` rejected it before Postgres ever saw it" |
| 5 | `PATCH /api/finance/budgets/{id}` | `{}` | **400** `"No fields to update"` |
| 6 | `PATCH /api/finance/budgets/999999` | `{"limit_amount": 1}` | **404** — "same answer for 'not mine' and 'doesn't exist' — no info leak" |
| 7 | any user endpoint after Authorize → **Logout** | — | **401** `"Missing Authorization header"` — "clean 401, not a confusing 422" (re-Authorize after) |
| 8 | `DELETE /api/finance/budgets/{id}` | — | **200** `{"deleted": ...}` — cleanup |

**The closer (30 sec, shows integration, not just CRUD):**

```
POST /api/finance/transactions
{"merchant": "Imtiaz", "amount": 2500, "transaction_type": "expense", "category": "Groceries"}

GET /api/finance/budgets     → the Groceries budget now shows spent: 2500
```

Say: *"Notice I never told the budget anything — `spent` is computed live from real transaction data at read time, and it deliberately excludes stock-trade transactions so investing doesn't read as overspending. Derived data stays consistent with its source by construction."*

**If the audience wants flash instead:** `POST /portfolio/create` → add a holding for `OGDC` → `GET /portfolio/{id}/value` shows live P&L against the 5-second market snapshot → try adding symbol `"FAKE"` → 400 with a human-readable message. **Double-screen finale:** create a budget in Swagger, refresh the webapp's Finance page (localhost:8080, same account) — the row appears. One API, two consumers, zero mock data.

---

# 2. Intern-to-Expert Translation Guide

The three most complex flows in the backend, each explained with an analogy, then the real mechanics.

## 2.1 The Buy Order — `services/portfolio/trades.py` (`POST /portfolio/transactions`)

**Analogy: a bank teller processing a check.** The teller first checks your ID (JWT), confirms it's really your account (ownership), confirms the check is written correctly (validation), and confirms you're allowed this account type's limits (plan quota). Then — and this is the key part — she updates the ledger, your running balance, *and* the carbon-copy receipt book **in one motion**. If the pen dies halfway, she voids everything and starts over. Nobody ever sees a ledger entry without its matching balance update.

**Under the hood:** the route is 3 lines (`api/portfolio_extended.py:56-63`); the service (`services/portfolio/trades.py:48-116`) opens one DB session and wraps three writes — (1) the immutable trade record in `stock_transactions`, (2) the aggregated position in `psx_holdings` with weighted-average-cost math (`(old_cost×old_shares + price×qty) / total_shares`; a sell reaching zero shares deletes the position), (3) a mirrored expense/income row in `user_transactions` tagged `source='stock_trade'` and linked by a `stock_transaction_id` foreign key. A single `commit()` at line 115 makes it atomic — the "voided check" is a transaction rollback. The actual SQL for each write lives in `repositories/portfolio/trades.py` and `holdings.py`; the service never touches SQL itself. This is also a textbook answer to "how do your modules integrate?": the stock module and the finance module meet inside one database transaction — and the finance module then *deliberately ignores* those rows in its spending analytics, because buying stock is an asset transfer, not spending.

## 2.2 The Freshness Machine — `services/memcache.py` + `services/cache.py` + `jobs/scheduler.py`

**Analogy: a bakery with a counter basket and a display case.** Customers (API requests) grab from the **counter basket** (in-process cache) — zero waiting. If the basket's contents are a bit old, you still get one instantly while an assistant quietly restocks it from the **display case** (Postgres) behind you — that's *stale-while-revalidate*. If ten customers arrive at an empty basket at once, only one assistant goes to fetch — the rest wait on that single trip instead of all running to the back (*single-flight lock*). Meanwhile the baker (the scheduler) restocks the display case on a rhythm: bestsellers every 5 seconds during opening hours, specialty items nightly, rare items weekly — and the "baked at" sticker (`refreshed_at`) tells everyone how fresh things are. Only if both the basket *and* the case are completely empty does anyone bake on the spot.

**Under the hood:** hot market reads call `mem_cache.get_or_load(key, ttl, loader)` (`memcache.py:37-59`) with TTLs per data type (`services/market/_base.py:14-24` — snapshot 5s, sectors 15s, index 60s, history 1h). The loader is `CacheLayer` (`cache.py`), the Postgres read-through: fresh table → serve; stale → serve *anyway* and scrape DPS in a background task, throttled to once per 60s per resource. The 8 APScheduler jobs keep Postgres warm so the background scrapes rarely fire. The genius twist is unchanged: because `psx_market_snapshot` is in Supabase's realtime publication, restocking the display case automatically updates every browser's view via websocket. And a timing middleware (`main.py:129-142`) logs every hot endpoint's latency — the cache work is *measured*, not assumed.

## 2.3 The Two-Gate Security System — `middleware/auth.py` → `api/deps.py` → `services/auth.py` → `services/permissions.py`

**Analogy: an office building.** The lobby turnstile (`BearerTokenMiddleware`) checks *everyone*. Delivery bots heading to public floors (market data) swipe a shared building keycard (`PSX_API_TOKEN`). Employees heading to private floors (portfolio/finance/alerts) pass the turnstile but face a biometric scanner at their own office door (`require_user`) — it checks a government-issued ID (the Supabase JWT) against the issuer's public registry (JWKS), reads who you are (`sub` claim), and prints a day-badge listing your clearances (plan + limits). Inside, every filing cabinet is additionally labeled with an owner name (`WHERE user_id = :uid`), and the cabinet-count per employee is capped by their contract tier (`check_count_limit` → 403).

**Under the hood:** the middleware exempts public paths and passes user-path prefixes through to per-route dependencies. `require_user` is declared as an `HTTPBearer` security scheme (`api/deps.py:9-29`) — which is also why Swagger's Authorize button works. `resolve_supabase_user` detects the token algorithm from its header — RS256/ES256 verified via a **cached** `PyJWKClient` against `/auth/v1/.well-known/jwks.json`, legacy HS256 against the shared secret — then one SQL join (`profiles LEFT JOIN plan_features`) hydrates plan limits with `COALESCE` fall-backs to Free-tier defaults. If that lookup fails, auth still succeeds with safe defaults — a DB hiccup can degrade you to Free limits but never lock you out. And `check_count_limit` is deliberately a *pure function* — the service fetches the count from a repository and passes it in, keeping SQL out of the permission layer entirely.

---

# 3. The 5-Minute Q&A Survival Guide

Seven questions senior engineers at Folio3 are most likely to ask about *this specific code*, with answers that are honest about trade-offs (that's what earns respect).

---

**Q1. "Your backend connects as a privileged role, so Row-Level Security doesn't apply to it. How do you actually stop me from reading another user's budgets?"**

> "Correct — both backend paths (the pooler role and the service key) bypass RLS, so the backend enforces scoping in application SQL — and since the refactor, every one of those queries lives in one auditable place, the repositories layer. Three patterns depending on query shape: plain `WHERE user_id = :uid` on lists; pre-flight parent-ownership checks before touching children; and ownership folded *into* the mutation itself — our holding delete uses `DELETE … USING psx_portfolios WHERE … AND p.user_id = :uid RETURNING id` (`repositories/portfolio/holdings.py:131-137`), so 'not found' and 'not yours' are indistinguishable, both 404, one atomic statement, no information leak. The `user_id` always comes from the *verified JWT's* `sub` claim, never from the request body. RLS isn't wasted though: the frontend also talks to Supabase directly with the anon key for things like the watchlist, and there RLS `WITH CHECK` policies plus database triggers are the enforcement — we hardened this in migration `20260707100000` after finding `USING`-only policies that could let a user reassign a row's `user_id`."

**Q2. "I see raw SQL strings in the code. SQL injection?"**

> "Every query is parameterized — SQLAlchemy `text()` with named bind parameters (`:uid`, `:pid`) or Core expressions, so values travel separately from SQL text and the driver does the escaping; nothing user-supplied is ever interpolated into a statement. And architecturally, all SQL is confined to the `repositories/` package — you can audit the entire query surface by reading one directory. Where a query is built dynamically (partial updates), only *column names from a hardcoded whitelist* are interpolated; all *values* remain bound parameters. The choice of SQL over a declarative ORM is deliberate (decision #41 in our decision log): schema truth lives in SQL migrations, tables are auto-reflected at startup, and complex reads like the net-worth CTE (`repositories/portfolio/valuation.py`) are clearer as SQL than as ORM expression trees. Defense in depth continues below the app: DB CHECK constraints re-validate what Pydantic validated."

**Q3. "Your plan-limit check reads a COUNT and then inserts. Two concurrent requests could both pass the check. Race condition?"**

> "Yes — the count-then-insert around `check_count_limit` is not serialized, so two simultaneous creates from the same user could exceed a quota by one. We accepted that consciously: the race window is per-user (you'd have to race *yourself*), the damage is one extra budget row, not a security breach, and the fix costs more than the bug — options are a serializable transaction, `SELECT … FOR UPDATE`, or a database trigger. In fact we already use the trigger approach where it matters most: the watchlist is written directly from the frontend, so its limit *is* a `SECURITY DEFINER` trigger in Postgres — that one is race-proof. If quota integrity ever becomes business-critical, we promote the other limits to triggers too."

**Q4. "How is CORS configured? Wildcard origins with credentials is a classic mistake."**

> "It *was* exactly that mistake, briefly — and we fixed it properly rather than papering over it. CORS is now driven by a `cors_origins` setting (`main.py:110-123`): a comma-separated origin list enables credentials for those specific origins; if the config is a wildcard, the code *automatically disables* credentials, because wildcard-plus-credentials is both rejected by browsers and unsafe. The mitigating factor even during the wildcard period was that we authenticate with bearer tokens in the `Authorization` header, never cookies — so the classic credentialed-CORS/CSRF attack never applied; a malicious site can't make a browser attach our JWT. The reasoning is documented in a comment right above the middleware."

**Q5. "The scheduler runs inside the API process and rate limits are in-memory. What happens when you scale to two replicas?"**

> "Today, deliberately, we don't — `railway.json` pins 1 replica, which makes the in-process APScheduler safe (no duplicate jobs) and the in-memory rate limiter and TTL cache coherent. That's the right call at current load: the API is I/O-bound and one uvicorn worker handles it. The scale-out path is well understood: split the scheduler into a dedicated worker service (the code is already isolated in `jobs/` with a standalone evaluator entrypoint built for exactly that), move rate-limit state to Redis or Postgres, and accept slightly lower cache hit rates per replica — the in-process cache is stale-tolerant by design, so replicas don't need coherence. On the DB side we're already sized for it: a bounded connection pool (`pool_size=10, max_overflow=20, pool_pre_ping`) per replica through Supabase's transaction pooler, with `statement_cache_size=0` for pgbouncer compatibility — N replicas means a predictable N×30 connection ceiling, not exhaustion."

**Q6. "You depend on scraping a government website. What happens when DPS changes its HTML or blocks you?"**

> "Three layers of resilience. First, politeness so we don't get blocked: a semaphore caps us at 2 concurrent requests, there's retry-with-backoff, the 5-second job only runs during PKT market hours, and background re-scrapes are throttled to once per resource per minute. Second, redundancy: three independent sources — DPS, the TradingView scanner (which covers sectors for 478 stocks where DPS only had 181), and the AhleTrade real-time feed — with a price fallback chain: live feed → snapshot → EOD close → cost basis. Third, graceful degradation is now structural: the cache serves stale data immediately and refreshes in the background, so a DPS outage means users see slightly older prices — never errors, never waiting. If DPS restructures its HTML, the market-watch parser locates columns by header text rather than position, and worst-case we serve last-known-good data from Postgres while we patch one parser class."

**Q7. "Your creates return 200, not 201, and deletes return a body instead of 204. Is this really RESTful?"**

> "Fair critique — pragmatic REST rather than pedantic REST. Two deviations I'd own: creates return 200 with the *full created row* (we use SQL `RETURNING`, so the client gets the id and server-computed defaults in one round trip — the value of 201 is mostly the `Location` header, which our SPA doesn't use), and deletes return `{"deleted": id}` for frontend cache invalidation, which rules out 204. The semantics that actually protect correctness are right: PATCH is true partial update via `exclude_unset`, 401/403/404/422 are used precisely — including clean 401s instead of FastAPI's default 422 on missing auth headers, which we explicitly fixed — auth is a declared OpenAPI security scheme, and mutations are idempotent where it matters (holdings upsert on a natural key, with the weighted-average recomputed in SQL). Adding `status_code=201` and `response_model=` declarations is a cheap polish item already noted for the OpenAPI contract's sake."

---

## Pre-Presentation Checklist

- [ ] Backend starts clean: `cd backend && uvicorn app.main:app` — watch for the `startup` log line and scheduler job registrations
- [ ] `/api/health` and `/api/health/db` return OK (health/db shows real DB round-trip latency — nice to show)
- [ ] Test-user JWT minted; Swagger **Authorize** button tested (raw token, no "Bearer" prefix)
- [ ] One budget pre-created so READ isn't empty on first show
- [ ] Webapp running at localhost:8080 and logged in as the same account (for the double-screen finale)
- [ ] Know your numbers cold: **~56 endpoints, 12 routers, ~29 tables, 8 jobs / 5-second refresh, 4 layers**
- [ ] If asked "what's NOT done": ML model is untrained (falls back to HOLD — code is complete, training is a script run), Stripe payments deliberately deferred per spec, push notifications deferred. Confident honesty > vague completeness.
- [ ] Known test-infra quirk (only if asked): all 36 tests pass individually; running the full suite in one process trips an event-loop/connection-pool interaction in pytest (the new pooled engine outlives per-test event loops). It's a test-harness artifact — production runs one long-lived loop — with a known `conftest.py` fix queued.

*Good luck — you know this backend better than anyone in the room now.*
