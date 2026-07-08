# Per-User Data Flow on Frontend — Design Spec

**Date:** 2026-07-10
**Branch:** `dev` (currently checked out)
**Working directory:** `D:\NafaIQ-Monorepo` ONLY
**Mode:** Build

## 1. Goal

When a user is logged in, the dashboard, finance module, and portfolio must show data from the database (their transactions, goals, budgets, holdings, watchlist). When the user is anonymous, fall back to the existing demo data for marketing purposes.

In addition, the KSE-100 (and KSE-30, KMI-30, KSE All Share) candlestick chart on `/psx` must render real OHLCV candles instead of degenerate 1-px dojis.

## 2. Non-Negotiable Constraints

1. **No file, component, table, or implementation may be removed.** Only additions or data-source swaps.
2. **No emojis in new code.** Existing `lib/data.ts` and `lib/finance/data.ts` keep emojis (anonymous fallback, untouched).
3. **Replace dummy data with real user data, but keep the implementation as-is.** Component shape, layout, animations, modals, behavior all preserved.
4. **No important file/code/table may be removed without explicit user permission.**
5. **Working directory:** `D:\NafaIQ-Monorepo` ONLY. No other folders.

## 3. Out of Scope (DO NOT TOUCH)

| Item | Reason |
|---|---|
| AI Portfolio Report content (`portfolio.tsx:680-757`) | Deferred to future project — button shows "Coming soon" |
| AI Finance Report content (`finance.tsx:1109-1189`) | Deferred to future project — button shows "Coming soon" |
| Haqeeqi Daulat panel (`portfolio.tsx:99-260`) | Deferred — left as-is |
| AI Recommendation widget on dashboard (`app.tsx:141-181`) | Out of scope — do not touch text |
| Landing page (`index.tsx`) | Out of scope — marketing dummy data stays |
| Team page (`team.tsx`) | Out of scope |
| Plans/pricing page (`plans.tsx`) | Out of scope |
| Testimonials (`components/landing/TestimonialsSection.tsx`) | Out of scope |
| Learn curriculum (`lib/learn/data.ts`, `LESSONS`, `GLOSSARY`, `LESSON_CONTENT`) | Out of scope |
| Zakat tab (`finance.tsx:1191-1403`) | Out of scope — calculator with local state |
| Notification bell (`AppShell.tsx:47-51, 227-323`) | Already wired — leave alone |
| Alerts page (`alerts.tsx`) | Already wired — leave alone |
| Transactions tab in Finance | Already wired — leave alone |
| Bills tab in Finance | Already wired — leave alone |
| `lib/data.ts` and `lib/finance/data.ts` exports | Untouched — anonymous fallback |
| `use-finance-store.ts` (localStorage) | Untouched — anonymous fallback |
| All `STOCKS`, `HOLDINGS`, `GOALS`, `BUDGETS`, `BILLS`, etc. constants | Untouched — anonymous fallback |
| Component shapes, layouts, animations, modals, button placements | All preserved |
| Existing files outside data-source swap points | No changes |

## 4. Architecture

### 4.1 Backend (FastAPI + SQLAlchemy Core + Supabase)

**New endpoints (additive, no existing endpoints modified):**

| Endpoint | Auth | Returns |
|---|---|---|
| `GET /api/portfolio/networth` | User JWT | `{total_market_value, total_cost_basis, total_unrealized_pnl, total_unrealized_pnl_pct, today_pnl, today_pnl_pct, portfolio_count, holding_count}` summed across all user portfolios |
| `GET /api/finance/summary?month=YYYY-MM` | User JWT | `{month, income, expenses, savings, savings_rate, last_month_income, last_month_expense}` |
| `GET /api/finance/income-expense?months=6` | User JWT | `[{month, income, expense}]` ordered by month ASC |
| `GET /api/finance/spending-by-category?days=30` | User JWT | `[{category, amount, pct}]` ordered by amount DESC |
| `GET /api/market/history-coverage` | PSX token | `[{symbol, days_available, oldest_date, newest_date}]` |

**New migration (additive):**

| Migration | Changes |
|---|---|
| `20260710010000_index_ohlcv.sql` | `ALTER TABLE psx_index_eod ADD COLUMN open NUMERIC(12,2) DEFAULT 0, ADD COLUMN high NUMERIC(12,2) DEFAULT 0, ADD COLUMN low NUMERIC(12,2) DEFAULT 0` |

**Existing tables NOT modified:** `psx_market_snapshot`, `psx_ohlcv`, `psx_holdings`, `psx_portfolios`, `user_transactions`, `user_goals`, `user_budgets`, `user_bills`, `user_settings`, `user_alerts`, `in_app_notifications`, `user_notification_prefs`, `user_watchlist`, `price_alerts`, `profiles`.

**Auth propagation:** All new user-JWT endpoints go through existing `require_user` dependency. New prefixes added to `USER_PATHS_PREFIXES` in `backend/src/app/middleware/auth.py`.

**Startup check:** In `app/main.py` lifespan, after `ensure_reflected()`, log a warning per symbol with <20 days of `psx_ohlcv` data. Non-blocking.

**Today's P/L SQL pattern:**
```sql
WITH prev_close AS (
  SELECT DISTINCT ON (symbol) symbol, close AS previous_close, date AS prev_date
  FROM psx_ohlcv
  WHERE date < CURRENT_DATE
  ORDER BY symbol, date DESC
)
SELECT
  COALESCE(SUM((ms.price - pc.previous_close) * h.shares), 0) AS today_pnl,
  COALESCE(SUM(pc.previous_close * h.shares), 0) AS prev_value
FROM psx_holdings h
JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
JOIN psx_market_snapshot ms ON ms.symbol = h.symbol
LEFT JOIN prev_close pc ON pc.symbol = h.symbol
```

If `prev_close` is NULL for a symbol (no historical data), that holding contributes 0 to today_pnl (with a log warning).

### 4.2 Frontend (React Query + Supabase JS)

**New hook files (additive):**

| File | Exports |
|---|---|
| `src/hooks/use-finance-summary.ts` | `useFinanceSummary(month?)` |
| `src/hooks/use-finance-budgets.ts` | `useFinanceBudgets()`, `useCreateBudget()`, `useUpdateBudget()`, `useDeleteBudget()` |
| `src/hooks/use-finance-goals.ts` | `useFinanceGoals()`, `useCreateGoal()`, `useContributeGoal()`, `useDeleteGoal()` |
| `src/hooks/use-finance-series.ts` | `useIncomeExpenseSeries(months=6)`, `useSpendingByCategory(days=30)` |

**Extension (additive):**

| File | Change |
|---|---|
| `src/hooks/use-portfolio.ts` | Add `usePortfolioNetworth()` alongside existing exports |

**Supabase types (additive):**

Append 8 new table types to `src/integrations/supabase/types.ts`:
- `user_budgets`
- `user_bills`
- `user_goals`
- `user_transactions`
- `user_settings`
- `user_alerts`
- `in_app_notifications`
- `user_notification_prefs`

Existing types unchanged. After appending types, remove `as any` casts in `use-alerts.ts`, `use-notifications.ts`, `lib/finance/financeBills.ts`.

**Component edits (data-source swaps only):**

| File | Allowed Edits |
|---|---|
| `routes/app.tsx` | KPI card values (lines 188-211), watchlist strip (line 277), savings goals (line 304-335), spending donut (line 253) |
| `routes/finance.tsx` | Overview KPIs (lines 227-230), sparkline data (lines 256, 276), 6-month chart (line 356), Budgets tab data source, Goals tab data source |
| `routes/portfolio.tsx` | KPI card fallbacks (lines 403-417), `SECTOR_ALLOC`, `STOCK_ALLOC` data sources |
| `routes/psx.tsx` | KSE-100 special case at line 137 (remove guard) |
| `lib/psx/types.ts` | Add `open`, `high`, `low` to `ApiIndexBar` (additive) |

### 4.3 Anonymous Fallback Pattern

```ts
const { user } = useAuth();

if (user) {
  // use real hooks
  const { data: summary } = useFinanceSummary();
  // ...
} else {
  // use dummy data from lib/data.ts and lib/finance/data.ts
  // ...
}
```

This pattern is already used in `portfolio.tsx`, `alerts.tsx`, `finance.tsx` (transactions/bills) and `AppShell.tsx` (notifications). We extend it consistently.

## 5. Data Flow

```
User logs in → Supabase session JWT
                ↓
React Query hook fires → fetch with Authorization: Bearer <jwt>
                ↓
FastAPI /api/* endpoint → require_user decodes JWT → user_id
                ↓
SQLAlchemy Core text() query filtered by user_id
                ↓
Postgres executes → RLS also checks auth.uid() = user_id
                ↓
JSON response → React Query cache → component renders
```

## 6. Error Handling

- **Network/API error:** Show existing skeleton (already implemented) + toast with retry. Never silently fall back to dummy data for logged-in users.
- **Empty data (new user, no rows yet):** Show empty state with CTA to add first item. Don't substitute dummy data.
- **Auth expired:** Existing `useAuth` redirects to `/auth` via `AuthGate`.
- **Missing previous_close for symbol:** Today's P/L contribution from that symbol is 0, with a backend warning log.

## 7. Testing

### Backend
- Pytest tests for each new endpoint:
  - Auth required (401 without JWT)
  - User isolation (returns only current user's data)
  - Aggregation correctness with seeded data
  - Empty case (no rows → 0/empty arrays)
  - Today's P/L computation correctness
  - Spending-by-category ordering
  - 6-month series ordering

### Frontend
- Manual test flow per route as logged-in user:
  - Empty state (new account)
  - 1 row
  - Many rows
- Switch to anonymous → all dummy data shows
- Switch back to logged-in → real data shows
- KSE-100 chart shows real candles

## 8. Phases

Each phase produces a working state. Each phase ends with: tests pass → commit → branch updated.

1. **Phase 0** — KSE-100 candlesticks fix (migration, backend, frontend type, remove guard)
2. **Phase 1** — Backend aggregation endpoints + tests
3. **Phase 2** — Today's P/L + 20-day history guarantee (verify, startup check, endpoint)
4. **Phase 3** — Supabase types (8 new tables)
5. **Phase 4** — Frontend hooks (4 new files + 1 extension)
6. **Phase 5** — Dashboard wiring (`app.tsx` data-source swaps)
7. **Phase 6** — Finance wiring (`finance.tsx` data-source swaps)
8. **Phase 7** — Portfolio wiring (`portfolio.tsx` data-source swaps)
9. **Phase 8** — Manual testing
10. **Phase 9** — Commit + push to dev

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `psx_ohlcv` has <20 days for some symbols | Verify at start; trigger backfill or wait for daily 02:00 job; startup warning |
| Existing tests break when adding new migration | Run tests after each phase |
| Existing frontend tests break with type changes | Run typecheck after each phase |
| P&L calculation differs from current `psx_market_snapshot.change`-based calc | Use `psx_ohlcv` for source of truth; verify with backtest |
| RLS prevents aggregation queries | Use service_role connection (already used); filter `user_id` at app layer |

## 10. Acceptance Criteria

- [ ] Logged-in user sees real net worth, today's P/L, monthly spending, watchlist, savings goals, spending donut on `/app`
- [ ] Logged-in user sees real income, expenses, savings, savings rate, 6-month chart on `/finance` Overview
- [ ] Logged-in user sees real budgets on `/finance` Budgets tab (CRUD works)
- [ ] Logged-in user sees real goals on `/finance` Goals tab (CRUD works)
- [ ] Logged-in user sees real sector/stock allocation on `/portfolio`
- [ ] KSE-100 chart shows real candles with wicks and bodies
- [ ] KSE-30, KMI-30, KSE All Share also show real candles
- [ ] Anonymous user still sees all dummy data (no regression)
- [ ] Today's P/L matches `SUM((ms.price - ohlcv.close) * h.shares)` calculation
- [ ] All existing tests pass
- [ ] No file/component removed
- [ ] No emojis in new code
- [ ] Code committed and pushed to `dev`
