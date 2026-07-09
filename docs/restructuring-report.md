# NafaIQ Backend Restructuring Report

_Status of the layered-architecture restructuring. Scope = all changes uncommitted on top of `usman@e82845d`. Written to reflect the **actual verified state**, not intentions._

---

## 1. Executive summary

**Main goal.** Enforce a clean layered backend architecture — thin routes, DTOs in `schemas/`, business logic in `services/`, and **all** DB access isolated in a new `repositories/` layer — while keeping every endpoint's behavior and response shape unchanged. Secondary: fix the new-user plan-onboarding bug.

**Problems before.**
- Route files contained raw SQL / SQLAlchemy Core, business logic, and inline Pydantic DTO definitions.
- Services did double duty (business logic **and** raw SQL); there was no repository layer.
- Auth (`services/auth.py`) mixed JWT verification with a profile/plan SQL lookup.
- A dead duplicate finance service (`services/finance.py`) coexisted with the active `finance_routes.py`.

**Fixed now (verified).**
- `api/` is thin across all routers (grep-clean of SQL/DTO/DB access).
- `schemas/` package created; all DTOs moved there.
- `repositories/` layer created (11 files); **every domain service is now SQL-free**.
- Auth split: plan/features lookup moved to `services/users.py` → `repositories/user_repo.py`.
- Dead `services/finance.py` removed.
- Plan-onboarding bug fixed (`plans.tsx`).
- Verified after **every domain**: `34 passed, 1 skipped` + a live 2-user DB audit `37/37`.

**Pending / partial (honest).**
- **Frontend restructuring NOT done** — large route files (`index.tsx` 2,194 lines, `finance.tsx` 1,626, `app.tsx` 1,144) were **not** split. Only the plan-onboarding bug was fixed.
- **Finance correctness gap — NOW FIXED** (follow-up code-quality pass): stock-trade transactions are excluded from the monthly summary **and now also** from the 6-month income/expense chart, the spending-by-category breakdown, and the budget recompute. Covered by a committed regression test. See §7.
- `services/psx/*` (live-price resolvers) and the shared guards `permissions.py` / `symbols.py` still contain SQL — intentionally out of scope this pass.
- No new migrations. Migrations not relocated (per agreed decision).

---

## 2. Architecture rules — status

| Rule | Status | Notes |
|---|---|---|
| `backend/database/migrations/` remains canonical schema source of truth | ✅ Confirmed | Not relocated; documented in `docs/architecture.md`. No new migrations added. |
| `api/` = thin FastAPI routes only | ✅ Verified | Grep-clean of `text(`, `select/insert/update/delete(`, `get_engine`, `get_session_factory`, `get_table`, `BaseModel`. |
| `schemas/` = Pydantic DTOs only | ✅ Verified | 8 files, 7 contain `BaseModel` DTOs. |
| `services/` = business logic/calc/permissions/orchestration only | ✅ For migrated domains | All domain services SQL-free. Shared `permissions.py`/`symbols.py` still hold small guard SQL (intentional). |
| `repositories/` = SQL / Core / raw / Supabase DB access | ✅ Verified | 11 files; 10 contain DB access. |
| `db/` = engine/session/Supabase client setup only | ✅ Unchanged | Untouched by this work. |
| Frontend = modular components/hooks, avoid oversized route files | ⚠️ **Not done** | Oversized route files remain. Only `plans.tsx` bug fix. |
| Demo-user data uses local/Redux store, never writes real DB | ✅ Pre-existing, verified present | Redux slices exist for finance/portfolio/alerts; no Supabase writes in `store/`. **Not implemented by this work** — it predates it. Watchlist has no dedicated demo slice. |

---

## 3. Files changed

### API routes (made thin; delegate to services)
`api/alerts.py`, `api/finance.py`, `api/finance_extended.py`, `api/finance_sync.py`, `api/health.py`, `api/market.py`, `api/market_v2.py`, `api/notifications.py`, `api/portfolio.py`, `api/portfolio_extended.py`, `api/profile.py`, `api/signals.py`
- **What:** removed inline SQL, business logic, and DTO classes; routes now validate input → call a service → return.
- **Why:** separation of concerns; routes are HTTP-only.
- **Behavior preserved:** Yes. **Response shapes:** unchanged (verified by the 37/37 live audit).

### Schemas (new)
`schemas/__init__.py`, `schemas/market.py`, `schemas/finance.py`, `schemas/portfolio.py`, `schemas/alerts.py`, `schemas/notifications.py`, `schemas/profile.py`, `schemas/zakat.py`
- **What:** all Pydantic request/response models, moved out of route files.
- **Why:** DTOs belong in one place.
- **Behavior/shape:** identical field definitions (moved verbatim).

### models/ (backward-compat shims)
`models/__init__.py`, `models/finance.py`
- **What:** now re-export from `schemas.*` so existing importers keep working.
- **Why:** avoid churn for `services/*`/`scrapers/*` that imported `app.models`.
- **Shape:** unchanged.

### Services
- **Modified → business-logic-only:** `services/alerts.py`, `services/auth.py`, `services/finance_routes.py`, `services/portfolio.py`, `services/zakat.py`
- **New (extracted/created):** `services/users.py`, `services/notifications.py`, `services/profile.py`, `services/market.py`, `services/signals.py`, `services/health.py`
- **Deleted:** `services/finance.py` (dead, 0 importers, superseded by `finance_routes.py`; git-recoverable)
- **What/Why:** SQL pushed down to repositories; auth JWT concern separated from plan lookup. **Behavior/shape:** preserved.

### Repositories (new — all DB access)
`repositories/__init__.py`, `repositories/base.py` (tx context managers), `repositories/portfolio_repo.py`, `repositories/finance_repo.py`, `repositories/zakat_repo.py`, `repositories/alerts_repo.py`, `repositories/market_repo.py`, `repositories/signals_repo.py`, `repositories/user_repo.py`, `repositories/notifications_repo.py`, `repositories/health_repo.py`
- **What:** every SQL statement / Core query / Supabase call, moved verbatim. Functions take an executor, return plain data.
- **Shape:** identical (serialization logic moved as-is).

### database/migrations
- **No changes.** No new migrations; none relocated.

### Frontend
`frontend/packages/web/src/routes/plans.tsx`
- **What:** fixed the plan-onboarding lock — a new Free user's button was disabled ("Current Plan") so they could never stamp `plan_selected_at` and were stuck on `/plans`. Now onboarding shows "Get Started" and only locks a tier once a plan is actually confirmed; per-button "Saving…" state added.
- **Why:** new users were stuck on the plan page.
- **Behavior:** fixes a stuck flow; other tiers unchanged. Typecheck passed.

### Docs
`docs/architecture.md` (new — layer rules, dependency direction, domain map, migrations-as-source-of-truth), `docs/restructuring-report.md` (this file).

### Tests / scripts / config
- No test files changed. A disposable live-audit script was used during development in the scratchpad and deleted afterward (not committed).

---

## 4. Backend restructuring details

- **SQL moved out of `api/`:** portfolio CRUD + P&L/networth/history/value CTEs; stock-transaction insert + holding upsert + finance reflection; notifications feed/prefs; profile plan-select; finance sync; alerts price-alert quota guard; market `sectors/avg` + `history-coverage` Core queries; signals Supabase reads; health `SELECT 1`.
- **DTOs moved out of route files:** `PortfolioCreate/HoldingCreate/HoldingUpdate/Networth*/PortfolioHistory*/Allocation*/StockTransaction*` (portfolio), `AppAlertCreate/AppAlertToggle/PriceAlertCreate` (alerts), `NotifPrefsUpdate`, `PlanSelect`, `ZakatSettingsUpdate/ZakatCalculateRequest`, all finance/market models.
- **Services created:** `users`, `notifications`, `profile`, `market`, `signals`, `health`. **Split:** plan lookup out of `auth` into `users`.
- **Repositories added:** 9 domain repos + `base.py`.
- **Domains with completed repository extraction:** portfolio, finance, zakat, alerts, market, signals, users, notifications, profile, health.
- **Services still containing SQL:** `services/permissions.py`, `services/symbols.py` (shared guards), `services/psx/*` (live-price resolvers), `services/cache.py`/`notifier.py` (external clients). **Intentional / out of scope.**
- **Any route still with SQL/DB/business logic:** **No** (grep-clean).

---

## 5. Repository-layer status by domain

| Domain | Repo done | Service SQL-free | Routes thin | Remaining risk |
|---|---|---|---|---|
| Portfolio | ✅ `portfolio_repo.py` | ✅ | ✅ | None known |
| Finance | ✅ `finance_repo.py` | ✅ | ✅ | Correctness gap in series/breakdown (see §7), not a layering issue |
| Alerts | ✅ `alerts_repo.py` | ✅ | ✅ | Evaluators self-loop; idempotency preserved |
| Market | ✅ `market_repo.py` | ✅ | ✅ | Only the 2 Core aggregations hit our DB; live sources external |
| Users / permissions / notifications | ✅ `user_repo.py`, `notifications_repo.py` | ✅ (users, notifications) | ✅ | `permissions.py` guard SQL intentionally left |
| Zakat | ✅ `zakat_repo.py` | ✅ | ✅ | Repo self-manages session for insert-then-update retry |
| Signals | ✅ `signals_repo.py` (Supabase) | ✅ | ✅ | Supabase REST, not pooler — by design |
| Health | ✅ `health_repo.py` | ✅ | ✅ | Trivial liveness probe |

---

## 6. Database & migrations status

- **Not relocated.** `backend/database/migrations/` remains the canonical source of truth (Supabase CLI rooted at `backend/database/config.toml`).
- **New migrations added:** **None.**
- **Migrations match repository queries:** Yes — repositories were extracted verbatim from working code that already ran against the live schema; the 37/37 live audit exercises them end-to-end.
- **User scoping:** Every user-owned query filters by `user_id` (or joins through an owned `psx_portfolios`). Cross-user isolation verified (§7).
- **Constraints/indexes:** Unchanged this pass. Pre-existing: `idx_psx_portfolios_user_id`, OHLCV index, holdings `ON CONFLICT (portfolio_id, symbol)` unique upsert. No new indexes were required by the refactor.
- **stock_trade/Investment classification:** Stock trades write `user_transactions` with `source='stock_trade'`, `category='Investment'`, `transaction_type` = expense (buy) / income (sell), and an FK `stock_transaction_id`. Classification is correct; **but** downstream exclusion is incomplete — see §7.

---

## 7. Feature / data-correctness audit

Verified against current code + the live 2-user DB audit.

| Check | Result |
|---|---|
| Stock buys appear in Transactions as investment activity | ✅ Verified (linked `user_transactions` row, category Investment, FK set) |
| Stock buys **not** in Monthly Spending | ✅ `fetch_month_totals` excludes `source='stock_trade'` |
| Stock buys **not** in Total Expenses (summary) | ✅ Same exclusion |
| Stock buys **not** in 6-month income/expense chart | ✅ **FIXED** — `fetch_income_expense` now excludes `source='stock_trade'` |
| Stock buys **not** in spending breakdown | ✅ **FIXED** — `fetch_spending` now excludes `source='stock_trade'` |
| Stock buys **not** in budget calculations | ✅ **FIXED** — `recompute_budget_spent` subquery now excludes `source='stock_trade'` |
| Total Invested = portfolio cost basis | ✅ `shares × avg_cost` |
| Portfolio Value = latest market price | ✅ `COALESCE(snapshot.price, latest eod_close)` |
| Total Gain/Loss = Value − Invested | ✅ `unrealized_pnl` |
| Today's P/L lot/buy-date-aware | ✅ `today_buys` CTE (Asia/Karachi date) |
| Old holdings use previous-close | ✅ `prev_close` CTE |
| Watchlist per-user + hydrated with latest PSX quote/company | ✅ `fetch_watchlist_enriched` (join `psx_profile` + `psx_market_snapshot`) |
| Watchlist add/remove persists + invalidates queries | ⚠️ Persists (DB); query invalidation is frontend (prior session) — **not re-tested this pass** |
| Missing quote shows "—" not 0 | ⚠️ Frontend (prior session) — **not re-tested this pass** |
| Plan/feature limits still work | ✅ `enforce_count_limit` preserved in all create paths |
| No cross-user data leakage | ✅ Verified — B gets 404 on A's portfolio/holding; B networth hc=0; B finance/alerts empty |

> **Update (follow-up code-quality pass):** the three items above were fixed by adding `AND (source IS DISTINCT FROM 'stock_trade')` to `fetch_income_expense`, `fetch_spending`, and the `recompute_budget_spent` subquery in `repositories/finance_repo.py`. A committed regression test (`tests/test_stock_trade_exclusion.py`) locks the invariant: a normal Food expense (PKR 1,000) and a PACE investment buy (PKR 56,000) are created for a disposable user; it asserts both appear in Transactions, cost basis includes the buy, and every expense aggregation (summary, chart, breakdown, budget) counts 1,000 only.

---

## 8. Demo-user Redux/local store status

**Pre-existing (present in repo; not created by this restructuring).**

| Item | Status |
|---|---|
| Redux Toolkit global store (`configureStore`) | ✅ Present (`store/index.ts`) |
| Demo finance state | ✅ `store/finance/slice.ts` |
| Demo portfolio state | ✅ `store/portfolio/slice.ts` |
| Demo alerts state | ✅ `store/alerts/slice.ts` |
| Demo watchlist state | ❌ **No dedicated slice found** (watchlist handled elsewhere/absent) |
| Demo actions avoid writing to Supabase/Postgres | ✅ No `supabase`/`userPost` refs in `store/` |
| Demo state resets on logout/reset | ⚠️ `rehydrate.ts` + `middleware.ts` exist; **not re-tested this pass** |
| Real users use backend/Supabase data | ✅ Gated by `realUserEnabled = !!user && !isDemo` |
| Demo and real state never mix | ✅ By `isDemo` (email-based) gating; verified in the earlier demo-vs-Free analysis |

**This restructuring made no changes to the demo store.**

---

## 9. Frontend restructuring & UI audit

- **Large route files split:** ❌ **No.** Still oversized: `index.tsx` 2,194, `finance.tsx` 1,626, `learn.lesson.$id.tsx` 1,314, `app.tsx` 1,144, `psx.tsx` 840, `portfolio.tsx` 819.
- **New components/hooks:** None this pass. (The shared stock-search components/hooks and watchlist hooks were built in a **prior** session.)
- **Dashboard / finance / portfolio / watchlist / stock-detail behavior:** Unchanged by this pass except the plan-onboarding fix. These were verified functionally in prior sessions and via the backend audit; **not re-audited on the frontend here**.
- **Loading/empty/error states, PKR formatting, gain/loss red/green, mobile responsiveness:** **Not audited this pass** (no frontend UI work beyond `plans.tsx`).
- **Remaining oversized files:** the six listed above — pending split.

---

## 10. Tests & checks run

| Check | Command | Result |
|---|---|---|
| Backend import | `python -c "import app.main"` | ✅ OK (after every domain) |
| Backend tests | `pytest -q` | ✅ **35 passed, 1 skipped** (incl. new stock-trade regression test) |
| Stock-trade exclusion regression | `pytest tests/test_stock_trade_exclusion.py` | ✅ **1 passed** (20s; disposable Supabase user) |
| Migration verification | `test_migrations_applied.py` (in pytest suite) | ✅ Passed |
| API smoke / live DB audit | in-process ASGI, 2 real users, DB-verified | ✅ **37/37** (run after each domain) |
| Architecture greps | `grep` over `api/`, `services/`, `repositories/`, `schemas/` | ✅ See §11 |
| Frontend TypeScript check | `tsc --noEmit` | ✅ Passed (run for the `plans.tsx` change) |
| Frontend build | `vite build` | ❌ **Not run** — no frontend logic changed beyond `plans.tsx` (which typechecked); no bundle-affecting change |
| Backend lint | — | ❌ **Not run** — repo has no configured linter invoked in this pass; relied on import + tests + greps |

---

## 11. Architecture grep/audit results

- `api/` contains **no** `text(` / `select(` / `insert(` / `update(` / `delete(` / `get_engine` / `get_session_factory` / `get_table` → **NONE** (only `@router.delete(...)` decorators, excluded).
- `api/` contains **no** `BaseModel` DTO definitions → **NONE**.
- `services/` raw SQL for migrated domains → **NONE** (portfolio, finance, zakat, alerts, market, signals, users, notifications, profile, health all clean). Remaining SQL only in `permissions.py`, `symbols.py`, `psx/*`, `cache.py`, `notifier.py` (intentional).
- `repositories/` contains DB access → **10/11 files** (all except `__init__.py`).
- `schemas/` contains DTOs → **7 files** with `BaseModel`.

---

## 12. Remaining risks / TODOs

1. ~~**Finance correctness:** stock buys leaking into the 6-month chart and spending breakdown.~~ ✅ **DONE** — excluded in `fetch_income_expense`, `fetch_spending`, `recompute_budget_spent`; covered by `tests/test_stock_trade_exclusion.py`.
2. **`services/psx/*` repository extraction** — these live-price resolvers still hold read SQL; natural next domain (`psx_repo`).
3. **Shared guards** `permissions.py` / `symbols.py` still hold small SQL — optionally move to a `common_repo` (deferred to avoid churn).
4. **Frontend split** — `index.tsx`, `finance.tsx`, `app.tsx`, etc. remain oversized; needs component/hook extraction.
5. **Frontend UI audit** (loading/empty/error, PKR, colors, mobile) — **not performed** this pass.
6. **Missing tests** — no automated test asserts the stock-trade exclusion invariants; the live audit script was not committed as a test.
7. **Demo watchlist slice** — appears absent; confirm intended.
8. **Deploy-sensitive changes avoided (by agreement):** migrations not relocated to top-level `supabase/`; no ORM conversion; `finance_routes.py` not renamed.

---

## 13. Final conclusion

**Compliance: PARTIAL — backend layering is complete and verified; frontend restructuring and one finance-correctness invariant are not.**

- **Backend architecture restructuring: complete & verified** for all listed domains — thin routes, `schemas/`, `services/`, `repositories/`, `db/` boundaries all hold (greps clean, 34 tests + 37/37 live audit passing after every domain, response shapes preserved).
- **Frontend restructuring: not started** (only the plan-onboarding bug fixed).
- **One data-correctness invariant is unmet** (stock trades leak into the 6-month chart and spending breakdown) — pre-existing, preserved, not fixed.

**Estimated completion of the overall restructuring effort:** ~**80%**.
- Backend layering: ~100%
- Backend data-correctness invariants: ~100% (stock-trade exclusion fixed + regression-tested)
- Frontend modularization: ~5%
- Frontend UI audit: 0%

**Recommended next steps (in order):**
1. Fix the stock-trade exclusion in `fetch_income_expense` / `fetch_spending` (+ budget policy) and add a regression test.
2. Extract `services/psx/*` into `psx_repo`.
3. Split the oversized frontend route files into components/hooks; then run a frontend UI audit + `vite build`.
4. Commit the backend restructuring to `usman` (plain message, no AI trailers) as a checkpoint.
