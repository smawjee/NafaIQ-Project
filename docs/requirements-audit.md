# NafaIQ — Requirements Audit (Discovery Phase)

Date: 2026-07-09. Branch: `dev`. Method: read-only inspection of backend (FastAPI/Python), frontend (`frontend/packages/web`), and database migrations (`backend/database/migrations`).

Status labels: **DONE** (implemented and wired), **PARTIAL** (exists but incomplete or needs work), **MISSING** (not present), **DEFERRED** (intentionally out of scope per spec).

---

## Verification results (2026-07-09, live run)

| Check | Result |
|---|---|
| `pnpm install` (all workspaces) | Pass |
| `pnpm run typecheck` | **Pass** — 3/3 workspaces (web, shared, mobile), 0 errors |
| `pnpm run lint` | **Pass** — exit 0 |
| `pnpm run build` (web SSR/nitro) | **Pass** — built in ~7s, full `.output` generated |
| Python venv install (`pip install -e ".[dev]"`) | Pass on Python 3.14 (all native cp314 wheels; no source builds) |
| Backend pure-function tests | **Pass** — 23/23 |
| Backend full pytest suite (live Supabase) | **Pass** — 34 passed, 1 expected skip (fx_rates, Phase 5) |
| Backend boot + `/api/health/db` | **Pass** — Supabase pooler ping ok (~1.4s) |
| Real market data `/api/market/snapshot` | **Pass** — 497 live PSX symbols |
| Benchmark `/api/market/kse100` | **Pass** — 2026-07-09 index + 1yr series |
| Migrations applied (test_migrations_applied) | **Pass** — schema in sync with migration files |

**New findings during verification:**
1. **`asyncpg` was a missing declared dependency** (async engine uses `postgresql+asyncpg://`). Without it all DB queries fail. FIXED — added `asyncpg>=0.30` to `backend/pyproject.toml`.
2. **Unauthenticated user endpoints return HTTP 422, not 401.** `/api/finance/summary` with no token -> 422 (validation error on missing header) instead of a clean 401 Unauthorized. Minor API-correctness item.
3. **KSE-100 index history has open/high/low = 0 for pre-migration rows** (only `close` backfilled by `20260710010000_index_ohlcv.sql`). Index candlesticks before that point render flat. Data-quality item (backfill).
4. **Supabase type regen is blocked locally** — CLI `--db-url` path needs podman/Docker (not installed); `--project-id` path needs a login token. Requires your action (see manual steps).
5. **Security note:** the Supabase CLI echoed the DB connection string (incl. `SUPABASE_DATABASE_PASSWORD`) into this session's error log. Not written to any file or committed. Consider rotating the DB password.

Bottom line: **the app builds, typechecks, lints, tests, boots, and serves real data end-to-end.** Nothing is fundamentally broken.

---

## P0 execution log (2026-07-09)

- **asyncpg missing dependency** — FIXED. Added `asyncpg>=0.30` to `backend/pyproject.toml` (async engine `postgresql+asyncpg://` requires it).
- **Unauthenticated user endpoints returned 422** — FIXED in `backend/src/app/api/deps.py`: `require_user` now accepts an optional `Authorization` header and raises a clean **401** when it is missing/malformed. Verified: `tests/test_networth.py` passes.
- **Transaction-category enum widening** — NO CHANGE NEEDED (resolved by inspection). `user_transactions` already has a separate free-text `category` column; `transaction_type` is intentionally the accounting direction (income/expense) that the savings/income-expense math depends on. Categories like investment/bill/transfer belong in `category` (already unconstrained). Widening `transaction_type` would corrupt finance calculations. Optional future work: a category *picker* in the UI (frontend-only, no migration).
- **Supabase type regen + any migrations** — token-gated. Awaiting `SUPABASE_ACCESS_TOKEN` to run `npx supabase gen types typescript --project-id gmonfgxmjgzipnbhgimv --schema public` (the `--project-id` path uses the Platform API, no Docker needed) and to apply future migrations via CLI.
- **KSE-100 index OHLC = 0 for old rows** — DEFERRED (cosmetic). The "Performance vs KSE-100" chart uses the `close` line, not candlesticks, so the zero OHL values do not affect the benchmark. Revisit only if the index is ever shown as candlesticks.

## Portfolio calculation bug fixes (2026-07-09)

Reported symptom: Portfolio Value PKR 0 while Total Invested PKR 191,808, Gain -100%, Today's P/L 0. Root cause diagnosed from live data: holdings joined to a NULL market price -> market_value = shares*0 = 0.

Three distinct bugs found + fixed (verified live 11/11 as a real user):
1. **No price fallback.** Value/networth/allocation queries read `psx_market_snapshot` only. Real symbols not in today's snapshot (e.g. ENGRO - in the profile reference, priced only in OHLCV) showed as 0. FIX: resolve current price = live snapshot -> latest OHLCV close, and fall market value back to cost basis when a symbol is entirely unpriceable (so it reads flat/0% instead of -100%). Applied in `api/portfolio.py` (portfolio_value + networth) and `services/portfolio.py` (value_for_portfolio + networth, which drive allocation).
2. **No symbol validation.** Users could add non-existent tickers ("DF", "DSDS"). FIX: new `app/services/symbols.py::require_known_symbol` validates against psx_profile ∪ snapshot ∪ ohlcv; wired into both add-holding endpoints. Unknown symbols now return 400.
3. **Holding purchase not in personal finance.** A buy wrote `stock_transactions` but not `user_transactions`, so it never appeared in the Finance feed. FIX: `create_stock_transaction` now also inserts a `user_transactions` row (buy=expense, sell=income, category 'Investment', source 'stock_trade'). Note: buys count toward monthly expenses/savings-rate; can be excluded by filtering category='Investment' if desired.

Verified: HBL priced from live snapshot; ENGRO priced from EOD (not 0); DF rejected 400; networth total value > 0 and unrealized not -100%; 2 Investment expense txns created; allocation includes ENGRO. Backend 34 passed/1 skip.

Outstanding data note: existing holdings "DF" (portfolio 6) and "DSDS" (portfolio 3) are invalid tickers (test data). They now display at cost (0% gain) instead of -100%, but should be deleted. ENGRO (portfolio 2) now prices correctly from EOD.

## Live per-user flow + calculation verification (2026-07-09)

Tested as a REAL disposable user (created via Supabase admin, deleted after — cascade-clean). Demo user is intentionally frontend-only (dummy data, local CRUD, never DB), so it was excluded. **13/13 checks passed:**
- Signup -> `profiles` row auto-created by trigger (plan=Free). Auth->profile linkage works.
- Add holding (buy) via the real UI path `POST /portfolio/transactions`: creates a `stock_transactions` purchase row AND upserts `psx_holdings` (weighted avg cost). Both linked to the user.
- Calculations correct vs manual-from-DB: `market_value = shares*price`, `unrealized = shares*(price-avg_cost)`, **`today_pnl = shares*(price - previous_close)`**, allocation-by-stock includes the holding.
- Finance: income+expense -> `user_transactions`; `/finance/summary` returns income=100000, expenses=30000, net=70000 (computed from DB). Budget + goal -> `user_budgets` / `user_goals`.
- Delete user -> ALL rows cascade to 0 across profiles/txns/stock/budgets/goals/portfolios.

**Two add-holding paths (consistency note):** the UI uses `POST /portfolio/transactions` (records the purchase + holding — correct). A secondary `POST /portfolio/{id}/holdings` endpoint upserts the holding only, with NO transaction row. Not used by the web UI, but inconsistent — should either record a transaction too or be retired.

## Finance table duplication — full dependency map (2026-07-09)

The live DB has two finance table sets. Verified who uses what:
| Table | Used by | Status |
|---|---|---|
| `user_transactions`, `user_budgets`, `user_goals`, `user_bills` | Python API (`finance_routes.py`) <- old hooks <- `finance.tsx` (ACTIVE) | Live, correct, verified |
| `finance_transactions`, `finance_bills` | `lib/finance/financeTransactions.ts` / `financeBills.ts` (direct Supabase) | **Written but imported NOWHERE** - unwired scaffolding (email-import: has `email_subject`/`raw_text`) |
| `email_import_items` | nothing | Orphan (0 rows) |
| `budgets`, `goals` (bare) | nothing | Orphans (goals has 2 stray rows) |
| `finance_sync.py` (`/finance/sync-budgets`) | recalculates `user_budgets.spent` from `user_transactions` | Uses the OLD tables |

**WIP inconsistency:** the new frontend layer writes `finance_transactions`, but `finance_sync.py` reads `user_transactions` — budget "spent" would never reflect the new path. The email-import migration is incomplete and internally split.

**Recommendation (NOT executed - needs your call):** the active, verified-correct schema is `user_*`. Either (a) finish migrating finance to the `finance_*` + email-import model and retire `user_*`, or (b) keep `user_*` and fold email-import fields into it, dropping the `finance_*` duplicates. Orphans `budgets` and `goals` (bare) have no references and can be dropped once you confirm the 2 `goals` rows are disposable. No table dropped without your sign-off.

### RESOLVED (2026-07-09): consolidated onto user_* (option b)
- Backed up all 5 drifted tables (DDL + data) to `database/backups/20260709_dropped_finance_tables_backup.sql` (restorable).
- Added migration `20260712000000_consolidate_finance_onto_user_tables.sql` (DROP the 5 tables).
- Applied on production via Supabase SQL Editor (human-run, per project workflow). Verified: live public tables now **29 == migration count**, none of the 5 remain.
- Removed unwired frontend lib files `lib/finance/financeTransactions.ts` + `financeBills.ts` (imported nowhere).
- Regenerated `types.ts` (5 tables gone). Re-verified GREEN: typecheck 3/3, web build, backend 34 passed/1 skip, and the full real-user flow **13/13**.
- Future email-import: add `email_subject`/`raw_text`/`source` columns to `user_transactions` rather than a parallel table.
- Dropped rows were developer test data linked to a few team user_ids; preserved in the backup file if ever needed.

## Supabase type regen + DB-drift discovery (2026-07-09)

- **`types.ts` regenerated from the live DB** (`--project-id gmonfgxmjgzipnbhgimv`). Strict superset of the old file (no table removed), typecheck passes. Backup saved in session scratchpad.
- **IMPORTANT — live DB has tables NOT in `backend/database/migrations/`:** the regen surfaced `finance_transactions`, `budgets`, `goals`, `finance_bills`, and `email_import_items` in addition to the expected `alert_events`, `plan_features`, `stock_transactions`, `user_zakat_settings`, `user_zakat_records`. The first set (plus `email_import_items`) matches active in-progress work (`api/finance_sync.py`, `finance.tsx` edits) — an email-receipt import / finance-sync feature. So:
  - The "phantom `finance_transactions`" flagged in the initial audit is NOT phantom — it exists in the live DB; it just has no migration file in the repo.
  - **Migration drift:** several live tables lack corresponding files in `backend/database/migrations/`. These should be captured as migration files so the repo can recreate the DB. (Owner: whoever created them via dashboard/CLI.)
- **Not touched:** the in-progress files (`main.py`, `auth.py`, `cache.py`, `psx/benchmark.py`, `alerts.tsx`, `finance.tsx`, `api/finance_sync.py`) and `services/finance.py` — left entirely alone per instruction.

## P1 execution log (2026-07-09) — RBAC hardening

**Key reframing (verified against `plans.tsx` + `AppShell.tsx` nav):** the pricing gates *features and limits within sections*, NOT whole sections. Every plan (Free/Pro/Premium) can open all six app areas (Dashboard, PSX, Portfolio, Finance, Learn, Alerts). Therefore **route-level section-blocking guards would be incorrect** — they would invent restrictions the landing page doesn't have (violating rule #18). RBAC work is correctly feature/limit gating + server enforcement, not route walls.

- **Backend tier-enforcement audit — DONE.** Findings:
  - Count limits ARE enforced server-side via `enforce_count_limit`: portfolios (`api/portfolio.py:62`), holdings (`api/portfolio.py:134`), price-alerts (`api/alerts.py:103`), transactions (`api/portfolio_extended.py:163`), budgets/bills/goals (`finance_routes.py:184/257/330`). Watchlist enforced by DB trigger. RLS + `prevent_profile_plan_self_update` solid. **This is real enforcement, not hidden-button theater.**
  - Feature-flag gating is NOT enforced server-side: `require_tier` exists but is unused; `has_realtime_psx` / `has_screener_full` / `has_export` are loaded into the user object but never checked. Real-time-vs-delayed PSX data in particular cannot be enforced on the current market endpoints (they use shared-token auth with no per-user context). Low practical urgency now (no payments -> everyone is effectively Free), but documented as a known limitation.
- **Upgrade-CTA correctness fix — DONE** (`AppShell.tsx`). The header and mobile drawer previously always said "Upgrade to Pro" regardless of plan (wrong for Pro/Premium users). Added `upgradeCta(plan)`: Free -> "Upgrade to Pro", Pro -> "Go Premium", Premium -> no CTA. Verified via typecheck.
- **Reusable locked UI — ALREADY EXISTS** (`components/shared/LockedCard.tsx`): design-consistent lock card with plan-aware "Upgrade to {plan}" link. Adequate for feature gating; no new component needed.
- **Per-page feature-locked states — RECOMMEND doing with the dev server up.** Adding locked/blur states for realtime toggle, export, screener, AI-over-limit, and count-limit prompts touches the large page files (`psx.tsx`, `portfolio.tsx`, `finance.tsx`, `alerts.tsx`) and benefits from visual verification. Best done one page at a time with the app running, not blind.
- **Central demo guard — LOWER URGENCY than first flagged.** The demo account is a real Supabase user, and RLS scopes every row to that user_id, so demo writes cannot leak into *other* users' data (no cross-user hole). The existing per-component `!isDemo` gating works (build/tests green). Centralization is optional polish, not a security fix.

## 0. Headline finding

The project is **far more complete than the `recall/` status notes claim.** The tracker (`recall/progress.md`, dated 07-08) says "Phases 3-9 pending / Finance & Portfolio are client-side mock only," but migrations dated 07-09 -> 07-11 and the matching backend services and frontend hooks were added *after* that note. The persistence layer, API surface, calculations, PSX integration, demo mode, and role model **already exist and are wired end-to-end** for most sections of the spec.

Rough completion by weight: **~75-85% implemented.** The remaining work is mostly:
1. **Reconciliation** of duplicated code paths (v1 vs v2 PSX stacks; two alert paths; a dead legacy finance service).
2. **Verification & testing** that the wired flows actually produce correct values against live Supabase + PSX.
3. **Targeted gap-fills** (professional locked/upgrade UI, route/nav permission guards, wider transaction-category enum, regenerated Supabase types, confirming chart default range is recent).
4. **Genuinely missing / deferred** items (payments, push delivery, ML model training).

**Canonical plan/role names (from `plans.tsx` + `plan-features.ts` + DB `plan_features`): `Free` / `Pro` / `Premium`.** "Premium" is the top/custom tier (price renders as "Custom", CTA "Contact Us"). Use these exact names everywhere.

---

## 1. Environment / setup status

| Item | Status | Notes |
|---|---|---|
| Node 24 / pnpm 9.15 | DONE | JS deps installed (`pnpm install`, all workspaces) |
| Python venv (3.14) | DONE | `backend/.venv`; all deps have native cp314 wheels (numpy 2.5, pandas 3.0, scikit-learn 1.9, scipy 1.18, lxml 6.1) — no source builds |
| `.env` (backend + web) | DONE | Both present and fully filled (no placeholders); backend adds `SUPABASE_JWT_SECRET`, `RESEND_API_KEY` |
| Repo mirror at dev/usman | DONE | Local `dev` == `origin/dev` == `origin/usman` (same commit `7b5c255`) |

---

## 2. Section-by-section requirement status

### Section 2 — Demo user flow — PARTIAL (works; isolation is convention-based)
- Demo entry buttons on landing (`routes/index.tsx`) and `routes/auth.tsx`; `DemoBanner` shows "changes not stored permanently".
- `use-demo.ts`: `isDemo = user.email === VITE_DEMO_EMAIL` (`demo@nafaiq.com`). Demo is a **real Supabase auth account**, not a mock session.
- Demo data = static fixtures (`lib/finance/data.ts`, `lib/data.ts`, `@nafaiq/shared`) swapped in when `isDemo`. Covers dashboard, psx, portfolio, finance, alerts, goals, zakat, budgets, bills, watchlist, holdings, learn, settings.
- **Gap:** isolation depends on every hook/mutation caller passing `!isDemo && !!user`; it is per-component convention, **not centrally enforced**. Because the demo user is a live Supabase account, any un-gated `supabase.from(...)` call could touch real rows. Recommend a centralized demo guard.

### Section 3 — Role-based access control — PARTIAL
- Plan model complete: DB `plan_features` (Free/Pro/Premium, per-plan numeric limits + boolean feature flags), backend `services/permissions.py`, frontend mirror `lib/plan-features.ts`, hooks `use-plan.ts` + `use-permissions.ts`.
- DB-level enforcement exists: RLS everywhere, `enforce_user_watchlist_plan_limit` trigger, `prevent_profile_plan_self_update` trigger.
- Backend `permissions.enforce_count_limit` used in finance CRUD.
- **Gaps:** (a) Frontend gating is **advisory only** — no route guards / redirects; sidebar/nav does not yet hard-respect permissions. (b) Backend enforcement coverage is uneven — needs an audit that every protected create/mutation checks tier/limits. (c) Professional **locked/upgrade UI states** are minimal (mostly `plans.tsx`); gated features need consistent locked cards. (d) `useUpgradePlan()` throws by design (no payments) — correct for now.

### Section 4 — Real logged-in user data — DONE (minor reconciliation)
- Per-user tables with RLS `auth.uid() = user_id` + `WITH CHECK`; backend resolves `user_id` from Supabase JWT (`services/auth.py`, `api/deps.py::require_user`). Queries are user-scoped. Frontend hooks attach JWT bearer (`lib/psx/client.ts`).
- **Gaps:** watchlist reads/writes go **direct to Supabase** (`user_watchlist`, RLS-safe); two alert code paths coexist (`use-alerts.ts` direct-Supabase vs `use-alert-events.ts` API) — reconcile to one.

### Section 5 — Database & ORM architecture — DONE for schema; ORM caveat
- All core entities exist with FKs, CHECK constraints, indexes, timestamps, RLS (see Section 5 table below).
- **Important architecture note:** the "SQLAlchemy ORM" is actually **SQLAlchemy Core + runtime reflection + raw SQL** (`db/orm.py`, `db/sqlalchemy.py`). The declarative classes in `db/models/*` are **typing-only decoration** — never used for queries or `create_all`. This is a deliberate, documented decision (`recall/explaination.md` #41). The spec repeatedly says "use SQLAlchemy ORM where possible"; the codebase intentionally does not. **Decision needed:** keep Core (recommended — least risk, matches Supabase-owns-schema model) or refactor to true ORM sessions (large, risky). See open question Q1.
- **Missing:** `budget_categories` table — categories are a text column on `user_budgets` (acceptable; only build if category management is required).

### Section 6 — Supabase — DONE (types drift)
- RLS on every table; frontend uses **anon key only**, backend uses service/secret key — no secret leak in client. `handle_new_user` trigger links `auth.users` -> `profiles` 1:1.
- **Gap:** generated `web/src/integrations/supabase/types.ts` is **stale** — it declares a phantom `finance_transactions` table (real table is `user_transactions`) and omits `plan_features`, `stock_transactions`, `alert_events`, zakat tables. **Regenerate types** (command in `AGENTS.md`).

### Sections 7-9 — PSX data / service architecture / calculations — DONE (with duplication)
- All required DPS endpoints implemented: market-watch, symbols, historical (POST), company, announcements (POST), payouts (POST), index EOD. AhleTrade real-time feed implemented. TradingView Pakistan scanner implemented.
- **Duplicated across two stacks:** `app/scrapers/*` (v1, drives scheduler + cache) and `app/services/psx/*` (v2, serves `market_v2` + portfolio). Also **two indicator engines** (`services/indicators.py` for the API; `ml/features.py` for the model) and **two DPS clients**.
- Latest-price resolver with fallback chain (AhleTrade -> snapshot -> DPS), previous-close from `psx_ohlcv`. Indicators: SMA/EMA/RSI/MACD/Bollinger/ATR/ADX/Stochastic/OBV/Williams %R/Donchian.
- `services/calculations.py` centralizes: holding value, cost basis, unrealized P/L (+%), today P/L (`qty * (latest - prev_close)`), portfolio totals, allocation by stock, allocation by sector, `portfolio_history_from_ohlcv`, `performance_vs_kse100`, savings rate, budget usage, goal progress, bill due, month-over-month compare, zakat estimate.
- **Gaps / to verify:** (a) confirm candle charts **default to a recent range** (1D-1Y), not 2016 — needs a UI check. (b) ML signal model is **untrained** — `signal_engine` falls back to HOLD until `signal_model.joblib` is trained (`scripts/train_signal_model.py`). (c) Consolidate v1/v2 duplication (tech debt, not blocking).

### Section 10 — Holdings & stock transactions — DONE (verify reflection)
- Holdings CRUD via `/api/portfolio/{id}/holdings` (+ `/transactions`); `stock_transactions` table with `quantity>0`, `price>=0`, `side` and `source` CHECKs, indexes, RLS. Watchlist CRUD via `user_watchlist` (v2). Calculations wired.
- **Verify:** adding a holding also creates the corresponding `stock_transactions` row (spec wants purchase to reflect into transaction history).

### Section 11 — Dashboard — DONE
- `routes/app.tsx`: `useShowcaseDashboard = isDemo` vs `realUserEnabled = !!user && !isDemo`. Real hooks feed portfolio value, net worth, today P/L, monthly income/expense, savings, goals, budgets, bills, alerts, watchlist, holdings, recent transactions. Charts real-backed.

### Section 12 — Portfolio — DONE (KSE-100 history approximate)
- Allocation by sector/stock (donuts), performance vs KSE-100 (benchmark overlaid on area chart), month/year value graph — all via Python API from user holdings. Historical portfolio reconstruction is approximate (`portfolio_history_from_ohlcv`), which the spec explicitly permits.

### Section 13 — Finance — DONE (category enum + dead code)
- `services/finance_routes.py` (active) provides transactions/goals/budgets/bills/settings CRUD + summary, income-vs-expense series, spending-by-category. Monthly income/expense, net savings, savings rate, month-over-month comparison, 6-month overview, spending & savings breakdown all present.
- **Gaps:** (a) `user_transactions` CHECK currently allows `transaction_type IN ('income','expense')` only — spec wants **investment / bill / transfer** too; widen the enum (migration). (b) `services/finance.py` is a **dead, superseded** read-only service — remove or reconcile. (c) Transaction system is structured for future email-receipt ingestion (`source` column already supports `brokerage_email`/`import`) — good.

### Section 14 — Budgets — DONE
- CRUD via `/api/finance/budgets`; usage %, thresholds; `evaluate_budget_alerts` in `services/alerts.py`. Unique `(user_id, lower(category), period)`.

### Section 15 — Bills — DONE
- CRUD via `/api/finance/bills` (+ `/paid`); recurring flag, due dates, status enum; `evaluate_bill_reminders`.

### Section 16 — Goals — DONE
- CRUD via `/api/finance/goals` (+ `/contribute`); progress from saved/target (CHECK `saved BETWEEN 0..target`); `evaluate_goal_alerts` (milestone).

### Section 17 — Zakat — DONE
- `user_zakat_settings` (configurable: `standard_2_5` / `custom_rate` / `manual_only`, nisab source gold/silver/cash/manual) + `user_zakat_records` (history, unique per year+method). Endpoints `/api/finance/zakat/settings|history|calculate`. Extensible as spec requires.

### Section 18 — User settings — DONE
- `user_settings` (monthly_income, currency, language, plan) + `user_notification_prefs`. Per-user, persisted, RLS. Demo uses demo-safe settings.

### Section 19 — Alerts system — DONE (strong) + duplication
- Alert types stock_price / bill / budget / goal. Tables: `price_alerts` (stock, with above/below/cross conditions, one_time, notify_push/email), `user_alerts` (rules), `alert_events` (notification/trigger history, channels in_app/email/push). Evaluators for all four types + `evaluate_all`, exposed via `POST /api/alerts/evaluate` (scheduled-job compatible). `notifier.py` already sends **email via Resend** and creates in-app notifications.
- **Gaps:** (a) Two frontend alert paths (`use-alerts.ts` vs `use-alert-events.ts`) — reconcile. (b) Confirm the evaluator is actually **scheduled** (APScheduler `jobs/`) vs only manual endpoint. (c) Push delivery is correctly **DEFERRED** (preference fields stored for later).

### Section 20 — LearnHub — DONE (keep as-is)
- Fully static content (`@nafaiq/shared` lesson/glossary data) + localStorage progress (`use-learn.tsx`). Same for all users. Matches spec: no DB, no personalization this phase. (Note: lightweight localStorage progress already exists — harmless; leave it.)

### Section 21 — Frontend behavior & UX — PARTIAL
- User states supported (visitor / demo / Free / Pro / Premium) via `isDemo` + `plan`.
- **Gaps:** professional **locked/upgrade** states across gated features; **sidebar/nav/route guards** that hard-respect permissions (currently advisory); a per-page pass for loading / empty / error states.

### Section 22 — Data visualization — DONE
- Recharts wrappers (`components/charts/charts.tsx`): portfolio area + KSE-100 benchmark, spending donut, allocation sector/stock donuts, income-vs-expense, candlestick/price line, budget/goal progress. Real data for logged-in, dummy for demo.

### Section 23 — Central calculations — DONE
- Business math centralized in `services/calculations.py` (pure functions, unit-tested in `tests/test_calculations.py`). PSX fetching kept out of finance logic. Verify no significant duplicate math lives in React components.

### Section 24 — Backend / API — DONE (cleanup)
- Organized routers + service layer; pydantic validation; user-scoped queries; PSX separated from finance. **Cleanup:** v1/v2 PSX duplication, dead `services/finance.py`, ORM-vs-Core clarity.

### Section 25 — Security & correctness — DONE (strong)
- No service key in client; RLS + WITH CHECK prevent cross-user access and ownership reassignment; plan self-upgrade blocked at DB; input validation via pydantic + DB CHECKs.
- **Tech debt:** CORS is `*` (noted in `recall`); do an input-validation completeness pass on CRUD.

---

## 3. Consolidated data model (already in DB)

profiles (+ generated `tier`), plan_features · psx_market_snapshot, psx_ohlcv, psx_fundamentals, psx_profile, psx_announcements, psx_dividends, psx_index_eod, psx_ticks, psx_signals · psx_portfolios, psx_holdings, stock_transactions · user_watchlist (v2) + psx_watchlist (v1 legacy), price_alerts (v2) + psx_alerts (v1 legacy) · user_transactions, user_budgets, user_bills, user_goals, user_settings · user_zakat_settings, user_zakat_records · user_alerts, in_app_notifications, user_notification_prefs, alert_events.

Missing vs spec: `budget_categories` (text column instead — optional). Everything else in the spec's entity list exists.

---

## 4. Genuinely missing / deferred

| Item | State | Spec intent |
|---|---|---|
| Payment processing (Stripe) | MISSING | DEFERRED — do not build (role/subscription only) |
| Push notification delivery | MISSING | DEFERRED — preference fields stored |
| Real email delivery | PARTIAL | `notifier.py` sends via Resend already; spec said defer — verify/keep behind flag |
| Email receipt scraping | MISSING | DEFERRED — `source` column ready for it |
| LearnHub personalization/DB | MISSING | DEFERRED — keep static |
| ML signal model trained | MISSING | Model code complete; `.joblib` not trained (falls back to HOLD) |
| Wider transaction categories | MISSING | Add investment/bill/transfer to enum |
| Regenerated Supabase types | STALE | Regenerate (types drift) |
| Route/nav permission guards | MISSING | Add hard gating |
| Professional locked/upgrade UI | PARTIAL | Add consistent locked states |

---

## 5. Open questions before implementation

- **Q1 (biggest):** ORM philosophy. The spec says "use SQLAlchemy ORM"; the codebase deliberately uses SQLAlchemy **Core + reflection + raw SQL** (Supabase owns the schema via SQL migrations). Keep Core (recommended, low risk) or refactor to true ORM sessions (large)?
- **Q2:** Reconcile duplication now (v1/v2 PSX, two alert paths, dead finance.py) or defer as tech debt?
- **Q3:** Priority order — do you want correctness/verification first (make sure existing wiring produces right numbers on live data), or feature-gap fills first (locked UI, categories, route guards)?

---

## 6. Recommended next phases (post-discovery)

1. **Stabilize & verify:** regenerate Supabase types; run typecheck/lint/pytest; stand up backend + web locally against Supabase; confirm each screen renders real data and calculations match.
2. **RBAC hardening:** central demo guard; route/nav permission guards; consistent locked/upgrade UI; audit backend tier enforcement coverage.
3. **Targeted gap-fills:** widen transaction-category enum (migration); confirm/adjust chart default range; ensure holding-add reflects into `stock_transactions`.
4. **Reconciliation:** collapse duplicate PSX stacks and alert paths; delete dead `finance.py`.
5. **Optional/deferred:** train ML model; leave payments/push/email-scrape scaffolded.
