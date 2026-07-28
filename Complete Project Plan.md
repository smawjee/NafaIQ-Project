# NafaIQ — Complete Project Plan

> **Purpose:** This document is the master implementation guide that takes NafaIQ from its current state (PSX module feature-complete, everything else running on mock data) to a fully production-ready application.
> **Last analyzed:** 2026-07-07
> **Status:** Planning document — intended to guide implementation across 10 phases.

---

## 1. Executive Summary

NafaIQ is a Pakistan Stock Exchange trading terminal + personal finance manager + AI financial tutor, delivered as a Progressive Web App. The project is built on a split-stack architecture:

- **Frontend** — TanStack Start (React 19, Vite 8, Nitro SSR) with Supabase Auth and React Query
- **Backend (PSX data)** — Python FastAPI microservice (`services/psx-api/`) that scrapes DPS / TradingView / AhleTrade and caches in Supabase Postgres
- **Database / Auth / Realtime** — Supabase (Postgres, Auth, Realtime, RLS)
- **AI** — Google Gemini 3 Flash via the Lovable Gateway (`learn-ai.functions.ts`)

### Current state at a glance

| Area | State |
|---|---|
| PSX data scraping & API (3 scrapers, 17 endpoints) | ✅ Complete |
| PSX frontend integration (15 hooks, 7 surfaces, realtime) | ✅ Complete |
| Supabase schema (15 tables, RLS, realtime) | ✅ Mostly complete — 4 RLS gaps |
| ML signal engine (27 features, walk-forward GBC) | ♻ Code complete, model not trained |
| Finance page (transactions, budgets, goals, bills, Zakat) | ⚠️ Client-side mock only — no persistence |
| Portfolio page (holdings, Haqeeqi Daulat, AI report) | ⚠️ Client-side mock only |
| AI features (Haqeeqi Daulat, AI Reports, AI Tutor) | ⚠️ Hardcoded strings — no LLM calls |
| Watchlist & price alerts | ✅ Supabase RLS |
| Auth (sign-in, sign-up, Google OAuth, email confirm) | ✅ Mostly complete — no password reset |
| Payments / subscription plans (`/plans`) | ❌ UI only — no Stripe |
| Notifications (price alerts) | ❌ DB write only — no delivery (email/push) |
| Production hardening (rate limiting, error monitoring, tests) | ❌ Missing |
| Dead code (v1 tables, unreferenced `psx.functions.ts`) | ❌ Cleanup pending |
| Critical `.env` leak of service-role key | ❌ **Immediate rotation required** |

### Phases summary

The roadmap below contains **10 phases** spanning 4–5 months of work for a single developer. Phases are designed to be shippable increments — at the end of every phase the app is demonstrable.

| # | Phase | Effort | Priority |
|---|---|---|---|
| 0 | Security incidents + .env rotation | 1 day | 🔴 Urgent |
| 1 | DB cleanup + types.ts sync + RLS hardening | 1 week | 🟠 High |
| 2 | PSX API auth + rate limiting + dead code removal | 1 week | 🟠 High |
| 3 | ML model training + screener UI wiring + backtest fix | 2 weeks | 🟠 High |
| 4 | Finance module: Supabase persistence + real transactions | 3 weeks | 🟠 High |
| 5 | Portfolio module: real holdings + Haqeeqi Daulat live calc | 2 weeks | 🟡 Medium |
| 6 | AI features: real LLM calls for Reports, Tutor, Recommendations | 2 weeks | 🟡 Medium |
| 7 | Auth completion: password reset, MFA, profile editing | 1 week | 🟡 Medium |
| 8 | Payments: Stripe integration + plan gating | 2 weeks | 🟡 Medium |
| 9 | Production hardening: tests, monitoring, CI/CD, deployment | 2 weeks | 🟢 Poland |

---

## 2. Current Project Assessment

### 2.1 What's done well

- **PSX data pipeline is genuinely production-shaped.** Three scrapers, read-through cache with bulk upserts, 5s/15min/daily/weekly job scheduling, realtime broadcast on `psx_market_snapshot`. 8 background jobs coordinate cleanly.
- **Single source of truth pattern** for PSX UI data — `usePsxLiveMarket()` is one React Query key shared across 7 surfaces, eliminating price contradictions. Realtime patches the same key.
- **Auth profile auto-creation** via `on_auth_user_created` trigger is correctly implemented.
- **Public-read RLS** for market data is the right pattern; only the API service-role key writes.
- **Theme system** is well-engineered: pre-hydration inline script prevents FOUC, single `nafaiq-landing-theme` localStorage key.
- **Bilingual** (English/Urdu RTL) is in production-ready shape: 606 UI keys + 452 Learn keys, `useSyncExternalStore` for performance.

### 2.2 What's partially done (works but has gaps)

- **PSX UI surfaces** are wired to real data, but: signal shown is hardcoded "HOLD" in the screener, watchlist prices use the static `STOCKS` map in `psx.tsx:610-642`, AI Analysis text in `psx.tsx:425-430` is a hardcoded typewriter string.
- **Stock detail** (`stock.$ticker.tsx`) has live data but: "52W Low" is hardcoded `—`, "Add to Portfolio" button has no handler (`portfolio.tsx:326-328` mirrors this), and the AI technical analysis text is hardcoded.
- **ML signal** is fully wired except: model file isn't trained, `signal_engine.py:18` uses fragile hardcoded class label mapping, `train_signal_model.py` env vars are `PSX_SUPABASE_*` (mismatch with runtime `SUPABASE_*`), and the "walk-forward" folds are actually cumulative (look-ahead bias).
- **Watchlist + price alerts** work in Supabase but: alert delivery isn't implemented (only the DB row is marked triggered), and `job_check_alerts` runs only every 60s.

### 2.3 What's missing entirely

- **No authentication on the Python API.** Every endpoint is public; anyone can read OR write all PSX data, `psx_signals`, and `price_alerts`.
- **No rate limiting** on the API. The 5s/15min scheduler intervals don't protect the API surface from per-client abuse.
- **No tests anywhere** — the `tests/` directory contains only an empty `__init__.py`.
- **No error monitoring** (Sentry/equivalent). Production errors will be invisible.
- **No CI/CD pipeline**. Manual deploys only.
- **No `.env.example` for the frontend**. The Python service has one; the frontend doesn't.
- **`types.ts` is stale** — covers only 4 of 15 tables. App code gets `any` for 11 tables.
- **V1 tables `psx_watchlist` / `psx_alerts` are dead code** — v2 (`user_watchlist` / `price_alerts`) replaced them but v1 was never dropped.
- **`psx/functions.ts` is dead code** — the routes call `psx/client.ts` directly via React Query, never through `createServerFn`.
- **No password reset, no MFA, no profile editing UI**, no notification channels.
- **No Stripe/payment integration** — `/plans` page is a static page that routes back to `/app`.
- **Finance/portfolio pages are localStorage demos** — the entire `useFinanceStore` is per-device. No cross-device sync.
- **AI features use hardcoded strings** — no LLM is ever called outside `learn/ai-functions.ts`.
- **Backtest endpoint is a stub** — `backtest.py:21` ignores `filter_spec`, `kse_return=0` is hardcoded.
- **Two divergent RSI implementations** — `features.py:_rsi` (simple MA, used at training) vs `indicators.py:_rsi` (Wilder's, used at serving) → trained model's feature ≠ served value.
- **The `.env` file is committed to git** with what appears to be a real service-role JWT.

### 2.4 Technical debt inventory

| # | Issue | Location | Severity |
|---|---|---|---|
| 1 | Service-role key committed to git | `services/psx-api/.env`, `.env` (root) | 🔴 Critical |
| 2 | CORS `allow_origins=["*"]` on the API | `services/psx-api/app/main.py:53` | 🔴 High |
| 3 | 4 RLS policies missing `WITH CHECK` | `psx_watchlist`, `psx_alerts`, `psx_portfolios`, `psx_holdings` | 🟠 High |
| 4 | `types.ts` covers 4/15 tables | `src/integrations/supabase/types.ts` | 🟠 High |
| 5 | `CacheLayer` instantiated per request (no singleton) | `services/psx-api/app/api/market.py:12-13` | 🟠 High |
| 6 | `signal_engine.py` uses hardcoded class label map | `services/psx-api/app/services/signal_engine.py:18` | 🟠 High |
| 7 | `train_signal_model.py` env var name mismatch | `SUPABASE_*` vs `PSX_SUPABASE_*` | 🟠 High |
| 8 | Two RSI implementations (train vs serve) | `features.py:97` vs `indicators.py:48` | 🟠 High |
| 9 | "Walk-forward" folds are cumulative (look-ahead bias) | `train_signal_model.py:fold ranges` | 🟠 High |
| 10 | Backtest endpoint is a stub | `services/psx-api/app/services/backtest.py` | 🟡 Medium |
| 11 | `psx_ticks` has `REPLICA IDENTITY FULL` but isn't in `supabase_realtime` publication | migration `20260706130000` | 🟡 Medium |
| 12 | 13 silent `except Exception: pass` blocks | `signals.py`, `cache.py`, `market.py`, `train_signal_model.py` | 🟡 Medium |
| 13 | `dependencies=tenacity` declared but never used | `services/psx-api/pyproject.toml` | 🟢 Low |
| 14 | Docker runs as root, no HEALTHCHECK, dev deps in image | `services/psx-api/Dockerfile` | 🟢 Low |
| 15 | `psx/functions.ts` is unreferenced dead code | `src/lib/psx/functions.ts` | 🟢 Low |
| 16 | `psx_watchlist` / `psx_alerts` v1 tables are dead | migrations `20260706120000` | 🟢 Low |
| 17 | `_loaded` race in `signal_engine.py` (sets to True on partial failure) | `signal_engine.py:30-39` | 🟢 Low |
| 18 | `announcement_id` collision risk | `dps.py:401` | 🟢 Low |
| 19 | Friday early close not handled in `_is_market_open` | `scheduler.py` | 🟢 Low |
| 20 | Index `idx_psx_ms_sym` and `idx_user_watchlist_user` are redundant with UNIQUE | migration `20260706130000` | 🟢 Low |
| 21 | No `idx_psx_portfolios_user_id` for RLS hot path | migration `20260706120000` | 🟢 Low |
| 22 | 3 mock data sources still imported by 6 files | `src/lib/data.ts`, `src/lib/finance/data.ts` | 🟡 Medium |
| 23 | `psx/client.ts:20` hardcodes `http://localhost:8000` | `src/lib/psx/client.ts` | 🟡 Medium |

### 2.5 Architecture decisions that are good and should not change

These are documented in detail in `explaination.md` decisions 1-31 and should be preserved:

- Python FastAPI microservice (not MCP, not all-TS)
- Supabase (not Postgres+Redis, not Firebase)
- TanStack Router + Start (not Next.js, not Remix)
- Pure numpy indicators (not pandas-ta — Python 3.14 compat)
- structlog (not stdlib logging)
- Pydantic v2 (not dataclasses)
- Read-through Supabase cache (not write-through, not pure scrape)
- Supabase Realtime (not WebSocket to Python)
- APScheduler in-process (not Celery, not pg_cron)
- 5-second market refresh (not 1s, not 30s)
- TradingView scanner for sectors (over DPS — DPS covers only 181/495)
- Direct fetch for local dev (not createServerFn) — `psx.functions.ts` kept for production
- Bypass auth on PSX routes in local dev
- Walk-forward ML validation (in concept, but implementation needs fixing — see Phase 3)
- Single `usePsxLiveMarket()` hook

---

## 3. System Architecture Overview

```
                    ┌────────────────────────────────────┐
                    │  Browser (PWA)                     │
                    │  React 19 + TanStack Router/Start  │
                    │  TanStack Query · shadcn/ui        │
                    │  Supabase JS · Supabase Realtime   │
                    └────┬───────────────────┬───────────┘
                         │ HTTPS            │ WSS (realtime)
                         │ (REST)           │
   ┌─────────────────────▼──┐         ┌─────▼──────────────┐
   │  Supabase             │         │  Supabase          │
   │  - Auth (email/Gmail) │         │  - Realtime        │
   │  - Postgres (15 tbls) │         │    psx_market_     │
   │  - RLS (own data)     │         │    snapshot        │
   │  - Storage (avatars)  │         └─────▲──────────────┘
   └─────▲────────▲────────┘               │
         │        │                         │ broadcasts
         │        │ SQL                     │
         │        │ (service_role)          │
   ┌─────┴────────┴────────────────┐    ┌───┴───────────────────────┐
   │  Python FastAPI              │    │  Python APScheduler jobs  │
   │  (services/psx-api/)         │◄───┤  - market snapshot 5s     │
   │  - 17 REST endpoints         │    │  - ahletrade poller 5s    │
   │  - 3 scrapers                │    │  - announcements 15min    │
   │  - Read-through cache        │    │  - tv sectors 5min        │
   │  - ML signal engine          │    │  - fundamentals weekly    │
   │  - Indicators (numpy)        │    │  - backfill nightly       │
   │  - Screener / Backtest       │    │  - index eod daily        │
   │  - Pydantic v2               │    │  - alert check 60s        │
   └────────┬─────────────────────┘    └───────────────────────────┘
            │ HTTPS
   ┌────────▼────────────────────────────────────┐
   │  External: DPS, AhleTrade, TradingView      │
   └─────────────────────────────────────────────┘
```

**Future additions** (introduced in later phases):
- Stripe API for payments (Phase 8)
- Sentry for error monitoring (Phase 9)
- Resend (or SendGrid) for transactional email (Phase 4 for notifications, Phase 7 for password reset)
- GitHub Actions for CI/CD (Phase 9)

---

## 4. Complete User Journey

### 4.1 First-time visitor (anonymous)

1. **Lands on `/`** — Landing page (`index.tsx`, 2168 lines)
   - Hero with animated ticker tape (`TICKER_ITEMS` from `data.ts`, replace with `useMarketTickers(8)` in Phase 3)
   - "How it Works" 3-step explanation
   - Haqeeqi Daulat™ flip-card demo (currently static — Phase 5 makes it live)
   - Testimonials carousel, FAQ accordion, Footer
   - CTA buttons: "Get Started" → `/auth?redirect=/app`, "Sign In" → `/auth`
2. **Clicks "Get Started"** → goes to `/auth` (signup mode)
3. **/auth** (signup):
   - Optional Google OAuth (`signInWithGoogle`)
   - Email + password + display name (split into first/last)
   - Password strength meter (4 checks)
   - Submits → `supabase.auth.signUp()` → `on_auth_user_created` trigger creates `profiles` row
   - Email confirmation required → shows "check your inbox" screen
   - Clicks confirmation link → `emailRedirectTo=/auth` → `/auth?redirect=/app` (now in signin mode)
4. **Signs in** → navigates to `/app` (Dashboard)
5. **/app** (Dashboard) — first-time empty state
   - Greeter card with first name from `profiles.display_name`
   - AI recommendation card (Phase 6: live; Phase 1: welcome message)
   - Empty portfolio + empty watchlist placeholders with CTAs
   - "Add your first holding" CTA opens modal
6. **Clicks "PSX Terminal" in sidebar** → `/psx` (no auth required in local dev; Phase 2 protects in prod)
7. **Browses** the screener, sector heatmap, top movers
8. **Clicks a stock** → `/stock/HBL` (or any ticker)
9. **Adds HBL to watchlist** → Supabase `user_watchlist` row inserted; PSX routes still work without auth
10. **Sets price alert** at PKR 142.00 above → Supabase `price_alerts` row; `job_check_alerts` will eventually trigger it
11. **Logs out** → returns to `/` (landing)

### 4.2 Returning user (authenticated)

1. **Lands on `/`** → clicks "Sign In" → `/auth`
2. **Signs in** with Google → OAuth callback → session set → `useAuth` populates `profile`
3. **Lands on `/app`** → dashboard populated
4. **Navigates** via sidebar to: Portfolio, Finance, Learn, PSX, Alerts, Settings
5. **Uses the AI Tutor** in Learn Hub → `askTutor` server function → Lovable Gateway → Gemini
6. **Closes tab** — session persists in localStorage; refresh keeps them logged in
7. **Receives a price alert** (Phase 4) → email / push / in-app toast

### 4.3 Subscription / payment journey (Phase 8)

1. **User on Free plan** hits a feature gated for Pro (e.g., unlimited AI reports)
2. **Sees paywall card** → CTA to `/plans?from=feature_name`
3. **Chooses Pro tier** (monthly PKR 1,499 or yearly PKR 14,388)
4. **Stripe Checkout** opens in new tab (or embedded)
5. **Completes payment** → Stripe webhook → backend updates `subscriptions` table
6. **Redirected to `/app?welcome=1`** with success toast
7. **Plan-gated features now unlocked**

### 4.4 Password reset (Phase 7)

1. **On `/auth`**, clicks "Forgot password?" → `/auth/reset` (new page)
2. **Enters email** → `supabase.auth.resetPasswordForEmail(email, { redirectTo: '/auth/update' })`
3. **Receives email** with magic link
4. **Clicks link** → `/auth/update?token=...` → enters new password
5. **Updates password** → `supabase.auth.updateUser({ password })` → redirected to `/app`

### 4.5 Email verification (already works)

- After signup, if `needsConfirmation` is true, `/auth` shows the "check your inbox" screen
- User clicks the email link → returns to `/auth` (signin mode) → signs in normally

### 4.6 Onboarding (new in Phase 7)

For first-time users post-signup, show a 3-step guided tour on `/app`:
1. **"Add your first holding"** — pre-fills with 1 stock suggestion
2. **"Add a watchlist"** — prompts to add HBL or another popular symbol
3. **"Explore Learn Hub"** — opens the first lesson

Track completion in `profiles.onboarding_complete BOOLEAN DEFAULT FALSE`.

### 4.7 Profile management (new in Phase 7)

New page `/settings/account` (sub-route of existing `/settings`):
- Avatar upload (Supabase Storage)
- Display name edit
- Email change (with re-confirmation)
- Phone number (optional, for SMS alerts)
- Connected accounts (Google unlink)
- Danger zone: delete account (CASCADE removes all user data)

---

## 5. User Roles & Account Types

### 5.1 Free user (default)

- **Plan:** `Free` (`profiles.plan` column)
- **Permissions:**
  - PSX terminal: all features
  - Watchlist: up to **10 symbols**
  - Price alerts: up to **5 active alerts**
  - AI Tutor: 20 messages/day (Phase 6: real quota via Supabase counter)
  - AI Reports: 1/week (Phase 6)
  - Learn Hub: full access
  - Finance: full access (Phase 4)
  - Portfolio: up to **1 portfolio, 20 holdings**
  - Haqeeqi Daulat: basic (1 currency)
  - Push notifications: ❌ Pro only
- **Locked features:**
  - Email digest of daily movers
  - Export CSV/JSON of holdings/watchlist/alerts
  - Multiple portfolios
  - Real-time Haqeeqi Daulat multi-currency
  - Custom screener save
- **Upgrade flow:** "Upgrade to Pro" button on locked features → `/plans`

### 5.2 Pro user (PKR 1,499/month or PKR 14,388/year)

- **Plan:** `Pro` (`profiles.plan = 'Pro'`)
- **Permissions:** Everything in Free, plus:
  - Unlimited watchlist (100 symbols)
  - Unlimited price alerts
  - AI Tutor: unlimited
  - AI Reports: 1/day
  - Portfolios: up to 5, 100 holdings each
  - Haqeeqi Daulat: multi-currency (USD/AED/SAR/EUR/GBP)
  - Email notifications
  - CSV/JSON export
  - Save up to 5 screener queries

### 5.3 Premium user (PKR 4,999/month — business tier)

- **Plan:** `Premium` (`profiles.plan = 'Premium'`)
- **Permissions:** Everything in Pro, plus:
  - Unlimited portfolios and holdings
  - AI Reports: unlimited
  - Custom screener: unlimited saves
  - Webhook integrations (Slack, Discord)
  - API access (future — Phase 10+)
  - Priority support (out of scope for v1)
  - "Verified" badge on social share images

### 5.4 Admins (optional, Phase 9+)

- **Plan:** `Admin` (`profiles.plan = 'Admin'`)
- For internal use, not advertised
- All Free/Pro/Premium features plus:
  - Database dashboard (read-only Supabase studio)
  - User impersonation (with audit log)
  - Feature flag toggles
  - Manual ML model retraining trigger
  - Maintenance mode toggle

### 5.5 Feature gating implementation

**Backend:** New migration adds a `plan_features` table:
```sql
CREATE TABLE plan_features (
  plan TEXT PRIMARY KEY CHECK (plan IN ('Free','Pro','Premium','Admin')),
  max_watchlist INT NOT NULL,
  max_alerts INT NOT NULL,
  max_portfolios INT NOT NULL,
  max_holdings_per_portfolio INT NOT NULL,
  ai_tutor_daily_limit INT,           -- NULL = unlimited
  ai_reports_period TEXT,             -- 'day' | 'week' | NULL
  ai_reports_per_period INT,
  has_email_alerts BOOLEAN NOT NULL DEFAULT FALSE,
  has_export BOOLEAN NOT NULL DEFAULT FALSE,
  has_multi_currency BOOLEAN NOT NULL DEFAULT FALSE,
  has_screener_save BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO plan_features VALUES
  ('Free',     10,    5,   1,  20,  20, 'week', 1, FALSE, FALSE, FALSE, FALSE),
  ('Pro',     100, 1000,   5, 100, NULL, 'day',  1, TRUE,  TRUE,  TRUE,  TRUE),
  ('Premium',1000,10000,100,1000, NULL, NULL,  NULL, TRUE,  TRUE,  TRUE,  TRUE),
  ('Admin',   1e9,  1e9, 1e9, 1e9, NULL, NULL,  NULL, TRUE,  TRUE,  TRUE,  TRUE);
```

**Frontend:** `usePlanFeatures()` hook reads profile + joins to `plan_features`:
```ts
export function usePlanFeatures() {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['plan-features', profile?.plan],
    queryFn: async () => {
      const { data } = await supabase
        .from('plan_features')
        .select('*')
        .eq('plan', profile?.plan ?? 'Free')
        .single();
      return data!;
    },
    enabled: !!profile,
  });
}
```

**Enforcement:**
- Watchlist add button checks `max_watchlist`; if reached, shows paywall
- Price alert count check at submit
- Portfolio creation checks `max_portfolios`
- AI Tutor sends through a Supabase Edge Function that increments a counter in `ai_usage` table and rejects on overflow
- All gates fail-open in local dev (env flag `VITE_DISABLE_GATES=true`)

### 5.6 Subscription management

For Phase 8, use Stripe. Schema additions:
- `subscriptions` table (one row per user)
- `stripe_events` audit log
- `invoices` (optional — Stripe is the source of truth)

**Plan changes:**
- Upgrade: immediate prorated charge
- Downgrade: takes effect at period end
- Cancel: still has access until period end, then drops to Free

---

## 6. Database Design Plan

### 6.1 Existing tables (15) — what's there

```
auth.users (managed by Supabase)
│
├──< profiles (1:1, FREE + auth data)
│
├──< psx_watchlist (v1, RLS gap)         ─┐
├──< user_watchlist (v2, correct RLS)     │  Watchlist
│                                          │
├──< psx_alerts (v1, RLS gap)            ─┤
├──< price_alerts (v2, correct RLS)       │  Price alerts
│                                          │
├──< psx_portfolios                       │  Portfolio (1:N)
│       └──< psx_holdings                 │  Holdings
│                                          ┘
│
psx_market_snapshot (public read)         ─┐
psx_ohlcv                                 │
psx_fundamentals                          │
psx_profile                               │  PSX market data
psx_announcements                         │  (service_role writes only)
psx_dividends                             │
psx_index_eod                             │
psx_ticks                                 │
psx_signals                               │
plan_features (public read — new P8)      │
subscriptions (user — new P8)            ─┘
```

### 6.2 New tables to add (across phases)

| Phase | Table | Purpose | RLS | Indexes |
|---|---|---|---|---|
| 1 | (none — RLS gap fix on existing) | Add `WITH CHECK` clauses to 4 policies | — | Add `idx_psx_portfolios_user_id` |
| 4 | `finance_accounts` | Bank/cash/wallet accounts (per user) | own-data | (user_id) |
| 4 | `finance_categories` | User-defined + default categories | own-data | (user_id) |
| 4 | `finance_transactions` | All income/expense records | own-data | (user_id, occurred_at DESC) |
| 4 | `finance_budgets` | Monthly budget per category | own-data | (user_id, month) UNIQUE |
| 4 | `finance_bills` | Recurring bills | own-data | (user_id, next_due) |
| 4 | `finance_goals` | Savings goals | own-data | (user_id) |
| 4 | `finance_contributions` | Goal contribution history | own-data | (goal_id) |
| 4 | `finance_zakat_calculations` | Saved Zakat computations | own-data | (user_id, year) |
| 4 | `in_app_notifications` | In-app notification history | own-data | (user_id, read, created_at) |
| 4 | `push_subscriptions` | Web Push subscription keys | own-data | (user_id) |
| 4 | `user_notification_prefs` | Per-category email/push/in-app toggles | own-data | (user_id) UNIQUE |
| 5 | `fx_rates` | Currency rates (PKR vs USD/AED/...) | public read | (base, quote, date) UNIQUE |
| 6 | `ai_usage` | Daily LLM call counter per user | own-data | (user_id, day) UNIQUE |
| 6 | `ai_chat_history` | Per-lesson AI tutor transcripts | own-data | (user_id, lesson_id, created_at DESC) |
| 6 | `ai_reports` | Generated portfolio/finance reports | own-data | (user_id, kind, created_at DESC) |
| 7 | (none — extend profiles) | Add columns: `onboarding_complete`, `phone`, `mfa_enabled` | — | — |
| 8 | `subscriptions` | Stripe subscription state | own-data | (user_id) UNIQUE, (stripe_customer_id) |
| 8 | `stripe_events` | Webhook audit log | none (service_role) | (stripe_event_id) UNIQUE |
| 8 | `plan_features` | Plan→features lookup | public read | (plan) PK |
| 8 | `invoices` | Invoice mirror | own-data | (user_id, created_at DESC) |
| 9 | `audit_log` | Admin action log | none (admin only) | (actor_id, created_at DESC) |
| 9 | `feature_flags` | Per-user/per-global flags | public read | (key) |
| 9 | `error_events` | Optional Sentry mirror | none (admin) | (created_at DESC) |

### 6.3 Per-table schema sketches (new tables)

#### `finance_transactions` (Phase 4)
```sql
CREATE TABLE finance_transactions (
  id          BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  account_id  BIGINT NOT NULL REFERENCES finance_accounts(id) ON DELETE CASCADE,
  category_id BIGINT NOT NULL REFERENCES finance_categories(id) ON DELETE RESTRICT,
  amount      NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  direction   TEXT NOT NULL CHECK (direction IN ('income','expense','transfer')),
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  description TEXT,
  merchant    TEXT,
  tags        TEXT[],
  receipt_url TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_finance_tx_user_date ON finance_transactions(user_id, occurred_at DESC);
CREATE INDEX idx_finance_tx_category ON finance_transactions(category_id, occurred_at DESC);
CREATE INDEX idx_finance_tx_tags ON finance_transactions USING GIN(tags);
-- RLS: own-data
```

#### `subscriptions` (Phase 8)
```sql
CREATE TABLE subscriptions (
  id                    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  user_id               UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  stripe_customer_id    TEXT UNIQUE,
  stripe_subscription_id TEXT UNIQUE,
  plan                  TEXT NOT NULL CHECK (plan IN ('Free','Pro','Premium')),
  status                TEXT NOT NULL CHECK (status IN (
    'active','trialing','past_due','canceled','incomplete','incomplete_expired','unpaid'
  )),
  current_period_start  TIMESTAMPTZ,
  current_period_end    TIMESTAMPTZ,
  cancel_at_period_end  BOOLEAN NOT NULL DEFAULT FALSE,
  canceled_at           TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- RLS: own-data
```

#### `ai_chat_history` (Phase 6)
```sql
CREATE TABLE ai_chat_history (
  id          BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  lesson_id   TEXT,        -- nullable: free-form chat allowed
  role        TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
  content     TEXT NOT NULL,
  tokens_used INT,
  model       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_chat_user_lesson ON ai_chat_history(user_id, lesson_id, created_at DESC);
-- RLS: own-data
```

### 6.4 Migrations directory convention

Place new files in `supabase/migrations/` with timestamp prefix. New migrations:
- `20260714090000_rls_hardening.sql` (Phase 1)
- `20260714090001_drop_v1_tables.sql` (Phase 1)
- `20260715090000_finance_module.sql` (Phase 4)
- `20260715090001_notifications.sql` (Phase 4)
- `20260715090002_portfolio_and_fx.sql` (Phase 5)
- `20260716090000_ai_usage_and_history.sql` (Phase 6)
- `20260717090000_subscriptions_and_features.sql` (Phase 8)
- `20260718090000_audit_and_feature_flags.sql` (Phase 9)

### 6.5 Security considerations

- All user-data tables have **both** `USING` and `WITH CHECK` clauses
- All numeric money columns use `NUMERIC(14,2)` (no floats for money)
- All `TIMESTAMPTZ` (not `TIMESTAMP`) — never lose TZ info
- All FKs use `ON DELETE CASCADE` for owned data; `ON DELETE RESTRICT` for referential integrity (categories, etc.)
- All `ENUM`/check-constrained columns indexable for fast filtering
- RLS on `audit_log` and `stripe_events` is **disabled** (service_role only)

---

## 7. Backend Architecture Plan

### 7.1 Existing backend: `services/psx-api/` (Python FastAPI)

- 17 endpoints, 3 scrapers, 8 scheduler jobs, ML signal engine
- Already documented in detail in `plan.md`, `project.md`, `explaination.md`

### 7.2 What to add / change in the Python service

| Phase | Change | File(s) |
|---|---|---|
| 0 | Rotate the leaked service-role key, purge from git history | (ops) |
| 1 | Add `/api/health/db` with actual Postgres ping | `app/api/health.py` |
| 2 | Add bearer-token auth on all `/api/*` except `/api/health` and `/api/symbols` (public) | `app/main.py`, new `app/api/deps.py` |
| 2 | Add rate limiting (slowapi: 60 req/min per IP for public, 600/min for authed) | `app/main.py` |
| 2 | Singleton `CacheLayer` via `lru_cache` | `app/api/market.py:12-13` |
| 2 | Make `psx/client.ts:20` read `import.meta.env.VITE_PSX_API_URL` | `src/lib/psx/client.ts` |
| 3 | Train the ML model and save artifacts | `scripts/train_signal_model.py` |
| 3 | Fix label mapping to use `model.classes_` | `app/services/signal_engine.py:18` |
| 3 | Fix env var name mismatch (use `SUPABASE_*` consistently) | `scripts/train_signal_model.py:31` |
| 3 | Implement true walk-forward (chronological splits, no row reordering) | `scripts/train_signal_model.py:fold` |
| 3 | Unify RSI implementation (use Wilder's in both `features.py` and `indicators.py`) | `app/ml/features.py:97`, `app/services/indicators.py:48` |
| 3 | Wire `/api/screener` to `psx.tsx` UI | `src/routes/psx.tsx` |
| 3 | Implement the backtest engine: KSE-100 baseline, `filter_spec` applied, transaction costs, proper median | `app/services/backtest.py` |
| 3 | Add `job_realtime_signal_refresh` — recompute signals for top 50 movers on a 15-min cycle | `app/jobs/scheduler.py` |
| 4 | Add `app/api/finance.py` (10 endpoints for finance CRUD) | new `app/api/finance.py` |
| 4 | Add `app/api/alerts.py` (create/list/toggle/delete price alerts via API, not via Supabase) | new `app/api/alerts.py` |
| 4 | Add notification delivery (email via Resend, push via Web Push API) | new `app/services/notifier.py` |
| 4 | Add `in_app_notifications` + `push_subscriptions` + `user_notification_prefs` tables | migration |
| 5 | Add `app/api/fx.py` (currency rates) and integrate with `finance_transactions` for Haqeeqi Daulat | new `app/api/fx.py` |
| 5 | Add `app/api/portfolio.py` (portfolio CRUD + live P&L calculation server-side) | new `app/api/portfolio.py` |
| 6 | Add `app/api/ai.py` (LLM proxy to Lovable Gateway, with usage tracking) | new `app/api/ai.py` |
| 6 | Add `app/services/quota.py` (plan-checked quota enforcement) | new `app/services/quota.py` |
| 6 | Add `app/services/prompts.py` (prompt templates for all AI features) | new `app/services/prompts.py` |
| 8 | Add `app/api/billing.py` (Stripe webhook handler + subscription mirror) | new `app/api/billing.py` |
| 9 | Add `/metrics` (Prometheus) and request correlation IDs | new `app/observability.py` |
| 9 | Remove `tenacity` from `pyproject.toml` or use it | `pyproject.toml` |
| 9 | Add `Dockerfile` improvements (non-root user, HEALTHCHECK, multi-stage) | `Dockerfile` |

### 7.3 Auth on the Python API

Approach: **HMAC-signed JWT** issued by Supabase. The frontend already has the user's session JWT (from `supabase.auth.getSession()`). The API validates it using the **Supabase JWT secret** (`SUPABASE_JWT_SECRET` env var) via PyJWT.

```python
# app/api/deps.py
import jwt
from fastapi import Header, HTTPException, Depends
from app.config import settings

async def require_user(authorization: str = Header(...)) -> dict:
    try:
        token = authorization.split(" ", 1)[1]
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"user_id": payload["sub"], "email": payload["email"]}
    except (jwt.PyJWTError, IndexError, KeyError) as e:
        raise HTTPException(401, f"Invalid token: {e}")

async def optional_user(authorization: str | None = Header(None)) -> dict | None:
    if not authorization:
        return None
    try:
        return await require_user(authorization)
    except HTTPException:
        return None
```

For unauthenticated public endpoints (`/api/health`, `/api/symbols`, `/api/market/snapshot`, `/api/sectors`, `/api/index/{code}`), the API uses the Supabase **anon key** for reads (via `get_supabase(anon=True)`). The `service_role` key is reserved for internal scheduler jobs only — the API client uses anon for reads, and writes go through user JWTs (RLS-enforced).

### 7.4 Rate limiting

Use **`slowapi`** (FastAPI-friendly wrapper over `limits`):
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# in main.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# in router
@router.get("/api/market/snapshot")
@limiter.limit("60/minute")
async def market_snapshot(request: Request): ...
```

Tiered limits:
- Public endpoints: 60 req/min per IP
- Authed endpoints: 600 req/min per user (use `require_user` for key_func)
- ML signal: 10 req/min per user (expensive compute)

### 7.5 Notification delivery

**Email (Resend):**
```python
# app/services/notifier.py
import resend
resend.api_key = settings.resend_api_key

async def send_price_alert_email(to: str, symbol: str, price: float, condition: str):
    resend.Emails.send({
        "from": "alerts@nafaiq.app",
        "to": to,
        "subject": f"{symbol} {condition} PKR {price}",
        "html": render_alert_template(symbol, price, condition),
    })
```

**Push (Web Push API):**
- Frontend subscribes via `serviceWorker.pushManager.subscribe({ userVisibleOnly: true })`
- Subscription stored in `push_subscriptions` table (new, RLS: own-data)
- Backend calls `pywebpush` with VAPID keys to deliver

### 7.6 AI proxy

The Python service (not the TanStack server function) becomes the AI gateway for cost and rate-limit reasons. Each call:
1. Checks `ai_usage(user_id, today) < plan.ai_tutor_daily_limit`
2. Calls Lovable Gateway (or direct to Gemini) with prompt + history
3. Records `ai_chat_history` row + increments `ai_usage` counter
4. Returns response

This gives us **server-side conversation history** (not just local), **quota enforcement**, and **prompt auditing**.

### 7.7 Background job improvements

- **Friday early close handling** in `_is_market_open` (`scheduler.py`) — PSX trades 09:30-12:00 on Friday, not 09:30-15:30
- **`job_poll_ahletrade` partial-data overwrite** — merge `price` and `volume` into existing row instead of overwriting (keeps `day_high`/`day_low`/`change`/`change_pct`)
- **Stale-source detection** — if a job hasn't succeeded in N cycles, mark the dataset stale in a `data_health` table
- **Market calendar** — load PKT holidays, skip jobs on holidays

### 7.8 Observability

- **`/metrics` endpoint** exposing Prometheus-format counters:
  - `psx_api_requests_total{route, status}`
  - `psx_api_request_duration_seconds_bucket{...}`
  - `psx_scrape_failures_total{source, kind}`
  - `psx_signal_predictions_total{outcome}`
  - `psx_scheduler_job_duration_seconds{job}`
- **Request ID** — middleware generates a UUID, attaches to `structlog.contextvars`, includes in response header `X-Request-ID`
- **Health check** — `/api/health` (basic) + `/api/health/db` (Postgres ping) + `/api/health/scrapers` (per-source last-success age)

---

## 8. Frontend Integration Plan

### 8.1 What each page needs (data dependencies)

| Page | Real backend today? | What it needs (post-Phase 1-9) |
|---|---|---|
| `/` (Landing) | Mostly static | Live ticker tape (Phase 1), live KSE-100 number, live testimonials, AI recommendation CTA |
| `/auth` | ✅ Real | — |
| `/auth/reset` (new P7) | ❌ Doesn't exist | `supabase.auth.resetPasswordForEmail` |
| `/auth/update` (new P7) | ❌ Doesn't exist | `supabase.auth.updateUser` |
| `/app` (Dashboard) | ⚠️ Mocked | `useFinanceStore` → real Supabase, `useWatchlist`, `useMarketMovers`, AI recommendation (Phase 6) |
| `/psx` | ✅ Mostly real | Screener signals (Phase 3), live watchlist (Phase 1), AI Analysis text (Phase 6) |
| `/stock/$ticker` | ✅ Mostly real | 52W high/low (Phase 1), Portfolio add button (Phase 5), AI technical analysis (Phase 6) |
| `/portfolio` | ⚠️ Mocked | Real holdings from Supabase, live P&L calc, live Haqeeqi Daulat, real AI report (Phase 5,6) |
| `/finance` | ⚠️ Mocked | Real Supabase persistence for transactions/budgets/bills/goals (Phase 4) |
| `/learn` | ✅ Real | — |
| `/learn/lesson/$id` | ✅ Real | — (AI tutor is real today) |
| `/plans` | ⚠️ UI only | Stripe checkout (Phase 8) |
| `/settings` | ✅ Real | Account sub-page (Phase 7) |
| `/alerts` | ⚠️ UI only | Backend delivery (Phase 4) |
| `/team`, `/urdu-qa` | Static | — |
| `/sitemap[.]xml` | ✅ Real | — |

### 8.2 State management topology

```
                    ┌──────────────────────────┐
                    │  Supabase (DB + Auth)    │
                    │  - Postgres (RWL)        │
                    │  - Realtime              │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────▼─────┐   ┌──────▼─────┐   ┌──────▼─────┐
       │ React Query│   │  Supabase  │   │  Context   │
       │ (PSX data) │   │ Realtime   │   │  (UI only) │
       │            │   │ (live tick)│   │            │
       └──────┬─────┘   └──────┬─────┘   └──────┬─────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │         React components        │
              └─────────────────────────────────┘
```

Currently the app uses:
- **React Query** (good) for PSX data
- **useSyncExternalStore** (in `use-finance-store.ts` and `use-lang.ts`) — fine for small state
- **Context** (in `use-auth.tsx`, `use-landing-theme.tsx`, `use-learn.tsx`) — fine for these

**Recommendation:** keep this topology. Do NOT introduce Redux or Zustand unless we hit a specific need (unlikely).

### 8.3 Caching strategy (per data type)

| Data | Source | staleTime | refetchInterval | Realtime? |
|---|---|---|---|---|
| PSX market snapshot | Python API → Supabase | 5s | 8s | ✅ (channel `psx:market`) |
| Single quote | Python API | 5s | — | ✅ |
| OHLCV history | Python API | 1h | — | ❌ |
| Fundamentals | Python API | 24h | — | ❌ |
| Profile (name/sector) | Python API | 7d | — | ❌ |
| Index EOD | Python API | 1h | — | ❌ |
| ML signal | Python API | 4h | — | ❌ |
| Sectors | Python API | 15s | 30s | ❌ |
| User watchlist | Supabase | 30s | on mount | ✅ (channel `psx:user_watchlist`) |
| Price alerts | Supabase | 30s | on mount | ✅ (channel `psx:price_alerts`) |
| Finance transactions | Supabase | 60s | 5min | ❌ |
| Portfolios/holdings | Supabase | 60s | 5min | ❌ |
| AI chat history | Supabase | 30s | on action | ❌ |
| Profile | Supabase | 5min | on auth change | ✅ |
| Subscription | Supabase | 60s | on action | ❌ |
| Currency rates | Python API | 1h | 6h | ❌ |

### 8.4 Loading / empty / error / success states (standardize)

Define a `<DataState>` component:

```tsx
<QueryState
  isLoading={isLoading}
  isError={isError}
  error={error}
  isEmpty={!data || data.length === 0}
  emptyMessage="No transactions yet"
  emptyAction={{ label: "Add your first transaction", onClick: () => openAddModal() }}
>
  {/* render data */}
</QueryState>
```

Used everywhere we render lists. The skeleton, error icon, and empty-CTA come from a single source.

### 8.5 Navigation flow

```
/ (landing)
├── /auth?redirect=...        Sign in / Sign up
│   ├── /auth/reset           Forgot password (new P7)
│   └── /auth/update?token=…  Reset password (new P7)
│
├── /app                      Dashboard (auth)
├── /portfolio                Portfolio (auth)
├── /finance                  Personal finance (auth)
├── /learn                    Learn Hub (auth)
│   └── /learn/lesson/$id     Lesson detail (auth)
├── /psx                      PSX Terminal (public, rate-limited)
│   └── /stock/$ticker        Stock detail (public, rate-limited)
├── /alerts                   Notification center (auth)
├── /settings                 Settings (auth)
│   └── /settings/account     Account details (new P7)
│   └── /settings/billing     Billing portal (new P8)
├── /plans                    Pricing (public)
└── /team, /urdu-qa           Static info (public)
```

**Auth gate (Phase 7):** All routes except `/`, `/auth/*`, `/plans`, `/team`, `/urdu-qa`, `/psx`, `/stock/*` (still public, rate-limited).

### 8.6 Realtime subscriptions (new)

Add Realtime channels for:
- `psx:user_watchlist` — invalidates `['user_watchlist']` on change
- `psx:price_alerts` — invalidates `['price_alerts']` and shows toast on new `triggered_at`
- `psx:user_profile` — invalidates `['profile']` on plan change
- `psx:finance_tx` — invalidates `['finance_transactions']` on insert/update/delete (multi-tab sync)
- `psx:ai_reports` — invalidates `['ai_reports']` on insert
- `psx:notifications` — pushes new in-app notifications to the notification panel

---

## 9. Feature-by-Feature Implementation Plan

### 9.1 PSX Terminal (`/psx` and `/$ticker`) — current gaps

| # | Gap | Phase | Plan |
|---|---|---|---|
| 1 | Screener signals are hardcoded "HOLD" everywhere | 3 | Wire to `usePsxScreener()` → POST `/api/screener`; replace `signal: "HOLD"` and `rsi: 50` and `marketCap: "—"` with real values |
| 2 | Watchlist prices use static `STOCKS[tk].price` | 1 | Replace with `live[tk]?.price ?? 0` (lookup in `usePsxLiveMarket()` cache) |
| 3 | AI Analysis text is hardcoded typewriter | 6 | Replace with `useAiMarketBrief()` → calls `askMarketBrief()` server function (Gemini with current snapshot as context) |
| 4 | "Add Stock" popover uses `Object.keys(STOCKS)` | 1 | Replace with `usePsxSymbols()` data |
| 5 | "52W Low" is hardcoded `"—"` | 1 | New `/api/quote/{sym}/range?days=252` endpoint; display real value |
| 6 | "Add to Portfolio" button has no handler | 5 | Wire to `useAddHolding()` mutation |
| 7 | Stock-detail AI technical analysis is hardcoded | 6 | Replace with `useAiStockAnalysis(ticker)` |
| 8 | Screener filters don't actually call `/api/screener` | 3 | Wire `signalFilter` UI to mutation |
| 9 | 7-day signal confidence chart on stock detail | 3 | New `/api/signal/{sym}/history?days=7` endpoint |
| 10 | Sector heatmap "Other" sector label | 1 | TradingView already returns sectors; just rename the fallback label |

### 9.2 Finance Module (`/finance`) — full rebuild

| Sub-feature | Tables | Endpoints | Frontend changes |
|---|---|---|---|
| Accounts | `finance_accounts` | `GET/POST/PATCH/DELETE /api/finance/accounts` | "Accounts" tab (new) in `/finance` |
| Categories | `finance_categories` | `GET/POST/PATCH/DELETE /api/finance/categories` | "Categories" modal in settings |
| Transactions | `finance_transactions` | `GET/POST/PATCH/DELETE /api/finance/transactions` (with `?from=&to=&category=&q=`) | New "Transactions" tab — replace mock data with real |
| Budgets | `finance_budgets` | `GET/POST/PATCH/DELETE /api/finance/budgets` | "Budgets" tab — calculate % spent live |
| Bills | `finance_bills` | `GET/POST/PATCH/DELETE /api/finance/bills` | "Bills" tab — show next due date, mark as paid |
| Goals | `finance_goals` + `finance_contributions` | `GET/POST/PATCH/DELETE /api/finance/goals` | "Goals" tab — progress bar, contribute button |
| Zakat | `finance_zakat_calculations` | `GET/POST /api/finance/zakat` | "Zakat" tab — calculator with history |

**Migration from localStorage to Supabase** (one-time, on first login):
- Detect `localStorage.nafaiq:finance:v1` data
- If non-default, prompt "Import your data to NafaIQ Cloud?" (Phase 4)
- On confirm, bulk-insert into Supabase, then clear localStorage

### 9.3 Portfolio Module (`/portfolio` and `/app` "holdings" widget) — full rebuild

**New table usage:**
- `psx_portfolios` — one row per named portfolio (default: "Main")
- `psx_holdings` — shares + avg_cost + purchased_at
- `psx_market_snapshot` (live join) — current price
- `psx_ohlcv` (historical) — for the performance chart
- `psx_index_eod` (KSE-100) — for benchmark overlay
- `fx_rates` (new) — for Haqeeqi Daulat multi-currency

**Live P&L calculation:**
```sql
-- v_user_portfolio_value (view)
SELECT
  p.id AS portfolio_id,
  p.user_id,
  p.name,
  SUM(h.shares * s.price) AS market_value,
  SUM(h.shares * h.avg_cost) AS cost_basis,
  SUM(h.shares * s.price) - SUM(h.shares * h.avg_cost) AS unrealized_pnl,
  CASE WHEN SUM(h.shares * h.avg_cost) > 0
    THEN ((SUM(h.shares * s.price) - SUM(h.shares * h.avg_cost)) / SUM(h.shares * h.avg_cost)) * 100
    ELSE 0
  END AS pnl_pct
FROM psx_portfolios p
JOIN psx_holdings h ON h.portfolio_id = p.id
JOIN psx_market_snapshot s ON s.symbol = h.symbol
WHERE p.user_id = auth.uid()  -- RLS handles this
GROUP BY p.id, p.user_id, p.name;
```

**Haqeeqi Daulat live calc:**
- `total_pkr = SUM(shares * price * fx_pkr_to_usd)` for each holding
- `nominal_return = (current_value - cost_basis) / cost_basis * 100`
- `usd_value = current_value / pkr_per_usd_today`
- `usd_cost_basis = cost_basis / pkr_per_usd_at_purchase`
- `real_return = (usd_value - usd_cost_basis) / usd_cost_basis * 100`
- `devaluation_shield = max(0, pkr_devaluation_pct - nominal_return)` — shown as a number 0-100
- Display: "PSX: +12.73%  ·  Real (USD): -3.2%"

**Multi-currency support** (Pro+): Fetch FX rates from SBP API (State Bank of Pakistan publishes daily rates).

### 9.4 AI Features (Phase 6)

| Feature | Current | New |
|---|---|---|
| AI Tutor in Learn | ✅ Real (server function → Gemini) | Keep as is; persist to `ai_chat_history` |
| AI Market Brief on `/psx` | ❌ Hardcoded | `useAiMarketBrief()` calls `askMarketBrief()` with snapshot context |
| AI Stock Analysis on `/stock/$ticker` | ❌ Hardcoded | `useAiStockAnalysis(ticker)` |
| AI Portfolio Report on `/portfolio` | ❌ Hardcoded (2s setTimeout) | `useAiPortfolioReport()` → real LLM with portfolio + holdings + P&L |
| AI Finance Report on `/finance` | ❌ Hardcoded (2s setTimeout) | `useAiFinanceReport()` |
| AI Recommendation on `/app` | ❌ Hardcoded | `useAiDailyRecommendation()` |

**Server function structure (Python side, not TanStack server function):**
```python
# app/api/ai.py
@router.post("/api/ai/market-brief")
async def market_brief(user=Depends(optional_user)):
    snapshot = await cache.get_market_snapshot()
    top_movers = sorted(snapshot, key=lambda s: abs(s.change_pct), reverse=True)[:5]
    brief = await llm.complete(
        system=PSX_BRIEF_PROMPT,
        user=format_snapshot_for_prompt(snapshot, top_movers),
    )
    await track_ai_usage(user["user_id"] if user else "anon", "market_brief")
    return {"brief": brief}
```

**LLM prompt conventions** (in `app/services/prompts.py`):
- `PSX_BRIEF_PROMPT` — "You are an analyst. Given this PSX market summary, write a 2-3 sentence daily brief. Be factual. No financial advice."
- `STOCK_ANALYSIS_PROMPT` — "Given OHLCV + indicators + fundamentals, write a balanced 4-5 sentence analysis. Highlight risk and uncertainty."
- `PORTFOLIO_REPORT_PROMPT` — "Given portfolio composition, P&L, and Haqeeqi Daulat values, write a 6-section report: 1) Summary, 2) Top performers, 3) Underperformers, 4) Diversification, 5) Devaluation exposure, 6) Suggested actions."
- `FINANCE_REPORT_PROMPT` — similar for finance data

All outputs **must include a disclaimer**: "This is AI-generated analysis for educational purposes only. Not financial advice."

### 9.5 Auth completion (Phase 7)

| Feature | Plan |
|---|---|
| Password reset | New `/auth/reset` + `/auth/update` pages, using `supabase.auth.resetPasswordForEmail` + `updateUser` |
| MFA (TOTP) | Enable Supabase MFA; add `mfa_enabled` column to `profiles`; add QR enrollment in settings |
| Email change | `supabase.auth.updateUser({ email })` triggers re-confirmation |
| Profile editing | New `/settings/account` sub-route — name, avatar (Supabase Storage), phone |
| Onboarding flow | 3-step tour on first `/app` visit; `profiles.onboarding_complete` flag |
| Account deletion | `auth.admin.deleteUser` via Supabase Edge Function (CASCADE removes all user data) |

### 9.6 Payments (Phase 8)

**Stripe integration (using Stripe Checkout + webhooks):**

1. **Frontend:** Plans page "Upgrade" button → `POST /api/billing/checkout` → returns `checkout_url` → `window.location = checkout_url`
2. **Stripe Checkout:** Hosted page; on success, redirects to `https://nafaiq.app/app?welcome=1`
3. **Stripe Webhook:** `https://api.nafaiq.app/api/billing/webhook` (no auth) — handles:
   - `checkout.session.completed` → create `subscriptions` row
   - `customer.subscription.updated` → update `status`, `plan`, `cancel_at_period_end`
   - `customer.subscription.deleted` → set `plan = 'Free'`, `status = 'canceled'`
   - `invoice.paid` → optional `invoices` row
4. **Subscription state:** `useSubscription()` hook reads `subscriptions` table; gate UI with `usePlanFeatures()`
5. **Proration:** Handled by Stripe; UI shows prorated amount on upgrade

**New tables:** `subscriptions`, `plan_features`, `stripe_events`, `invoices` (all defined in section 6.3)

**New files:**
- `src/hooks/use-subscription.ts` — reads `subscriptions` + `plan_features`
- `src/lib/stripe-client.ts` — redirect to checkout, manage portal

### 9.7 Notifications (Phase 4)

**Price alert delivery:**
- `job_check_alerts` (60s) — on trigger, dispatch via notifier
- Notifier writes to `in_app_notifications` (new table) and optionally sends email (Resend) and/or push (Web Push)
- Frontend's `<NotificationPanel>` subscribes to `psx:notifications` Realtime channel

**Finance/bill/goal notifications:**
- `job_check_bills` (daily 08:00 PKT) — for bills due in 1/3/7 days
- `job_check_budgets` (every 15min during 9-23 PKT) — for budgets at 80%+ spent

**Channels per user:**
- `user_notification_prefs` (new) — `email_enabled`, `push_enabled`, `in_app_enabled` per category

### 9.8 Search & global command palette

A `/` keyboard shortcut opens a `cmdk` palette (the `cmdk` package is already in `package.json`):
- **Search symbols:** `HBL`, `KSE100`, etc. → navigates to `/stock/$ticker`
- **Search pages:** "Settings", "Portfolio" → navigates
- **Run actions:** "Add to watchlist" → opens modal with HBL pre-filled
- **AI query:** "Ask the tutor" → opens AI chat
- All actions rate-limited server-side

---

## 10. API Planning

### 10.1 Current 17 endpoints (PSX) — preserve, harden

| Endpoint | Method | Public? | Rate limit | Phase changes |
|---|---|---|---|---|
| `/api/health` | GET | yes | none | 1: add `/db` and `/scrapers` variants |
| `/api/market/snapshot` | GET | yes | 60/min | 2: auth, 2: ratelimit |
| `/api/quote/{sym}` | GET | yes | 120/min | 2: auth, 2: ratelimit |
| `/api/quote/{sym}/history?days=` | GET | yes | 30/min | — |
| `/api/quote/{sym}/range?days=252` | GET | yes | 30/min | 1: NEW (52W high/low) |
| `/api/symbols` | GET | yes | 60/min | — |
| `/api/fundamentals/{sym}` | GET | yes | 60/min | — |
| `/api/profile/{sym}` | GET | yes | 60/min | — |
| `/api/announcements` | GET | yes | 60/min | — |
| `/api/dividends/{sym}` | GET | yes | 60/min | — |
| `/api/index/{code}` | GET | yes | 60/min | — |
| `/api/indicators/{sym}` | POST | yes | 30/min | 1: wire to UI |
| `/api/screener` | POST | yes | 10/min | 3: implement, 3: wire to UI |
| `/api/backtest` | POST | yes | 10/min | 3: implement properly |
| `/api/sectors` | GET | yes | 60/min | — |
| `/api/signal/{sym}` | GET | yes | 10/min | 3: real predictions |
| `/api/signals/batch` | POST | yes | 5/min | 3: real predictions |

### 10.2 New endpoints (Phase 1-9)

**Phase 1 — DB cleanup:** None (SQL only)

**Phase 1 — PSX polish (small):**
- `GET /api/quote/{sym}/range?days=252` — 52W high/low

**Phase 2 — Auth:**
- All endpoints gain auth/rate limit headers

**Phase 3 — ML hardening:**
- `GET /api/signal/{sym}/history?days=N` — signal history
- (no new endpoints; existing ones now return real predictions)

**Phase 4 — Finance module:**
- `GET/POST /api/finance/accounts`
- `GET/POST /api/finance/categories`
- `GET/POST/PATCH/DELETE /api/finance/transactions` (with filters)
- `GET/POST/PATCH/DELETE /api/finance/budgets`
- `GET/POST/PATCH/DELETE /api/finance/bills`
- `GET/POST/PATCH/DELETE /api/finance/goals`
- `POST /api/finance/goals/{id}/contributions`
- `GET/POST /api/finance/zakat`
- `GET/POST/PATCH/DELETE /api/alerts` (price alerts via API)
- `POST /api/notifications/subscribe` (Web Push subscription)

**Phase 5 — Portfolio:**
- `GET/POST/PATCH/DELETE /api/portfolios`
- `GET/POST/PATCH/DELETE /api/portfolios/{id}/holdings`
- `GET /api/portfolios/{id}/value` — live P&L
- `GET /api/portfolios/{id}/performance?range=1M|3M|1Y` — historical
- `GET /api/portfolios/{id}/haqeeqi-daulat?currency=USD|AED|SAR|EUR|GBP` — multi-currency

**Phase 6 — AI:**
- `POST /api/ai/market-brief` — daily PSX brief
- `POST /api/ai/stock-analysis` — single stock analysis
- `POST /api/ai/portfolio-report` — portfolio report
- `POST /api/ai/finance-report` — finance report
- `POST /api/ai/daily-recommendation` — dashboard card
- `GET /api/ai/usage` — current quota usage

**Phase 7 — Auth completion:** All on Supabase, no API endpoint needed (except account deletion):
- `POST /api/auth/delete-account` — calls Supabase admin API to delete user

**Phase 8 — Billing:**
- `POST /api/billing/checkout` — creates Stripe session, returns URL
- `POST /api/billing/portal` — opens Stripe customer portal
- `POST /api/billing/webhook` — Stripe webhook handler (no auth)
- `GET /api/billing/subscription` — current state
- `GET /api/billing/invoices` — invoice history

**Phase 9 — Observability:**
- `GET /metrics` — Prometheus
- `GET /api/health/db` — DB ping
- `GET /api/health/scrapers` — per-source last-success

### 10.3 Total endpoint count after all phases

- PSX: 17 (existing) + 2 (Phase 1) = 19
- Finance: 10
- Portfolio: 5
- AI: 6
- Billing: 5
- Auth: 1
- Health/Observability: 4
- **Total: ~50 endpoints**

### 10.4 OpenAPI documentation

FastAPI auto-generates `/docs` (Swagger UI) and `/redoc`. The Python service already has this. We should:
- Add request/response examples
- Add a top-level description
- Mark deprecated endpoints
- Group by tag (`psx`, `finance`, `portfolio`, `ai`, `billing`, `health`)

### 10.5 API versioning

For v1, no `/v1/` prefix — current routes are v1 by default. When v2 ships, prefix both (`/api/v1/...` and `/api/v2/...`) with a 6-month overlap.

---

## 11. Security Considerations

### 11.1 Immediate (Phase 0 — 1 day)

1. **Rotate the leaked Supabase service-role key** in the Supabase dashboard (Settings → API → Roll service_role JWT secret)
2. **Purge the `.env` from git history:**
   ```bash
   git filter-repo --invert-paths --path services/psx-api/.env --path .env
   git push --force
   ```
3. **Add to `.gitignore` (root):**
   ```
   .env
   .env.local
   .env.*.local
   services/**/.env
   ```
4. **Add to `services/psx-api/.gitignore`:**
   ```
   .env
   app/ml/*.joblib
   app/ml/*.json
   ```
5. **Re-deploy** the Python service with new env vars
6. **Verify** the old key is revoked by attempting to use it (should 401)

### 11.2 Auth on the API (Phase 2)

- All write endpoints and authed read endpoints require `Authorization: Bearer <jwt>`
- Public read endpoints (market snapshot, symbols, sectors, indices) allow unauthenticated access but are rate-limited
- JWT validation via `SUPABASE_JWT_SECRET` (PyJWT)
- `service_role` key is server-internal only (env var, never logged)

### 11.3 RLS hardening (Phase 1)

Add `WITH CHECK` to 4 existing policies:
```sql
-- psx_watchlist, psx_alerts, psx_portfolios, psx_holdings
ALTER POLICY "Users own their watchlist" ON psx_watchlist
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
-- repeat for alerts, portfolios
-- for holdings: USING/WITH CHECK via EXISTS subquery
```

### 11.4 CORS

Production: replace `allow_origins=["*"]` with `allow_origins=["https://nafaiq.app", "https://www.nafaiq.app", "http://localhost:8080"]`. Dev: keep `*` but with a loud comment that it's for local only.

### 11.5 Rate limiting

- slowapi: 60 req/min per IP for public, 600/min per user for authed
- 10 req/min for expensive (screener, backtest, signals)
- 429 responses include `Retry-After` header

### 11.6 Input validation

- Pydantic v2 with strict types (no `Any`)
- Numeric fields: `conint(ge=0)`, `confloat(ge=0)`
- String fields: `min_length`, `max_length`, `pattern` for emails
- Symbol parameter: `^[A-Z]{1,10}$` regex

### 11.7 Logging

- structlog JSON output in production
- PII scrubbing: never log JWT, never log full email (mask: `u***@example.com`)
- Request correlation ID in every log line
- Log retention: 30 days (Sentry/CloudWatch)

### 11.8 Secret management

- Frontend: only `VITE_*` (public) env vars
- Python service: `SUPABASE_*`, `STRIPE_*`, `RESEND_*`, `VAPID_*` — all from env, never committed
- Vercel/Railway: secrets set in dashboard, not in repo
- Rotate secrets quarterly

### 11.9 Supply chain

- Dependabot (or Renovate) for Python and npm
- `npm audit` + `pip-audit` in CI (Phase 9)
- Pin major versions in `pyproject.toml` and `package.json`

### 11.10 OWASP top 10 coverage

| Risk | Mitigation |
|---|---|
| A01 Broken Access Control | RLS + JWT validation + per-feature gating |
| A02 Cryptographic Failures | HTTPS, JWT signing, bcrypt for any passwords (Supabase handles) |
| A03 Injection | Pydantic validation, parameterized queries (PostgREST), no raw SQL |
| A04 Insecure Design | Threat model documented; feature gating enforced server-side |
| A05 Security Misconfig | CORS locked down in prod, env vars only |
| A06 Vulnerable Components | Dependabot, `npm audit`, `pip-audit` |
| A07 Auth Failures | Supabase Auth (battle-tested), rate limiting on auth endpoints |
| A08 Software/Data Integrity | Stripe webhooks verified, Supabase migrations reviewed |
| A09 Logging Failures | structlog + Sentry, request correlation IDs |
| A10 SSRF | Scrapers hit only fixed URLs (whitelist); user input not used in URLs |

### 11.11 PSX data integrity

- All scraper errors are logged with the source URL
- Cache writes are atomic (single bulk upsert)
- If a scrape returns malformed data, the previous cache is preserved (no overwrite with garbage)
- Sanity checks: `price > 0`, `volume >= 0`, `date <= today`

---

## 12. Data Storage Strategy

### 12.1 What's public (no RLS)

- `psx_market_snapshot`, `psx_ohlcv`, `psx_fundamentals`, `psx_profile`, `psx_announcements`, `psx_dividends`, `psx_index_eod`, `psx_ticks`, `psx_signals` — anyone can read (market data is public by law)
- `plan_features`, `fx_rates` — public reference data

### 12.2 What's per-user (RLS)

- All `finance_*` tables, `subscriptions`, `invoices`, `ai_chat_history`, `ai_reports`, `ai_usage`, `user_watchlist`, `price_alerts`, `psx_watchlist`, `psx_alerts`, `psx_portfolios`, `psx_holdings`, `user_notification_prefs`, `push_subscriptions`, `in_app_notifications`, `audit_log`

### 12.3 What the Python service writes (service_role only)

- All `psx_*` public tables — periodic refresh jobs
- `psx_signals` — ML predictions
- `subscriptions` — Stripe webhook handler (uses service_role since it runs as backend, not user)
- `stripe_events` — webhook audit log
- `audit_log` — admin actions
- `error_events` — Sentry mirror

### 12.4 What the frontend writes (user JWT, RLS-enforced)

- `user_watchlist`, `price_alerts`, `psx_portfolios`, `psx_holdings`, `finance_*` tables, `ai_chat_history` (via server function)
- All writes go through React Query mutations that include the user JWT

### 12.5 Backup & retention

- **Supabase Pro** has automatic daily backups with 7-day retention (Phase 9: upgrade to Team for 30-day)
- **Point-in-time recovery** enabled
- `psx_ticks` — TTL of 30 days (Phase 9: add cron job to delete `created_at < now() - interval '30 days'`)
- `error_events` — TTL of 90 days
- `audit_log` — indefinite (for compliance)
- `ai_chat_history` — indefinite (user-owned)

### 12.6 Privacy / GDPR

- Users can request all their data: `GET /api/auth/export-data` (new in Phase 9) — returns a JSON dump
- Users can delete their account: cascades via `ON DELETE CASCADE` on all FKs
- No third-party tracking (no Google Analytics, no Facebook Pixel in v1)
- `analytics` (if added in future) must be opt-in

---

## 13. Testing Strategy

### 13.1 Unit tests (Python — pytest)

| File | Test cases |
|---|---|
| `tests/test_dps_scraper.py` | Each endpoint method with mocked HTML fixtures; parse edge cases (missing columns, weird dates) |
| `tests/test_ahletrade.py` | Pipe-delimited response parsing; symbol not in feed; error response |
| `tests/test_tradingview.py` | 478-row response, sector map fallback |
| `tests/test_cache.py` | Read-through flow, TTL expiry, scrape-on-miss, write failure |
| `tests/test_indicators.py` | Known values (e.g., `sma([1,2,3,4,5], 3) == [2, 3, 4]`); edge cases (empty, NaN, single value) |
| `tests/test_signal_engine.py` | Mock model file, predict happy path, fallback path, error path |
| `tests/test_screener.py` | Each filter, combinations, sort orders |
| `tests/test_backtest.py` | Date ranges, transaction costs, KSE-100 baseline, median calculation |
| `tests/test_notifier.py` | Email send, push send, channel preference respect |
| `tests/test_auth.py` | Valid JWT, expired JWT, malformed JWT, missing token |
| `tests/test_rate_limit.py` | 61st request returns 429 |

### 13.2 Integration tests (Python — pytest + httpx.AsyncClient)

| Test | What it does |
|---|---|
| `test_end_to_end_market_snapshot.py` | Hits `/api/market/snapshot`; if Supabase unreachable, falls back to scrape; response shape matches |
| `test_end_to_end_signal.py` | Hits `/api/signal/{sym}`; reads from `psx_signals` cache; if miss, calls `predict`; verifies cache write |
| `test_stripe_webhook.py` | Posts a mock Stripe webhook; verifies `subscriptions` row is created/updated |

### 13.3 Unit tests (TypeScript — Vitest)

Add Vitest config to `package.json`. Test:
- `usePsxLiveMarket()` cache invalidation
- `useFinanceStore` actions
- `useLearn` progress calculation
- `usePlanFeatures()` plan limit checks
- `useSubscription()` plan transitions

### 13.4 Component tests (Vitest + Testing Library)

For shadcn/ui wrappers and feature components:
- `AppShell` renders all nav items when authenticated
- `NotificationPanel` shows unread count
- `<DataState>` renders all 4 states
- `useAuth` provider flows

### 13.5 E2E tests (Playwright)

| Test | What it does |
|---|---|
| `auth.spec.ts` | Sign up → email confirm (mocked) → sign in → land on `/app` |
| `psx.spec.ts` | Visit `/psx` → verify live data renders → click stock → verify chart loads |
| `portfolio.spec.ts` | Add holding → verify appears in list → edit → delete |
| `finance.spec.ts` | Add transaction → verify it appears → add to budget → verify % |
| `alerts.spec.ts` | Create price alert → verify in DB → mock trigger → verify notification |
| `plans.spec.ts` | Click upgrade → Stripe checkout (mocked) → return → verify plan upgraded |

### 13.6 Coverage targets

- Python: 80% line coverage, 70% branch coverage
- TypeScript: 70% line coverage (hooks only; component tests optional)
- E2E: every critical path (auth, PSX, portfolio, finance, alerts, plans)

### 13.7 CI integration (Phase 9)

- GitHub Actions runs all tests on every PR
- Lint + typecheck on every commit
- Build artifact on `main` branch

---

## 14. Production Readiness Checklist

### 14.1 Security
- [ ] `.env` rotated and purged from git (Phase 0)
- [ ] `service_role` key in env only, never in client (Phase 0)
- [ ] HTTPS enforced (HSTS header)
- [ ] CSP header set (allow self + Supabase + Google fonts + Gemini)
- [ ] X-Frame-Options: DENY
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Rate limiting on all auth endpoints (5/min on sign-in, 3/min on password reset)
- [ ] Rate limiting on all API endpoints (per section 7.4)
- [ ] RLS `WITH CHECK` on all user-data policies (Phase 1)
- [ ] CORS restricted to production domains (Phase 2)
- [ ] All forms use reCAPTCHA / Cloudflare Turnstile (Phase 9)
- [ ] PII scrubbing in logs (Phase 9)
- [ ] Sentry enabled (Phase 9)

### 14.2 Performance
- [ ] `psx_market_snapshot` query < 50ms (indexed)
- [ ] `usePsxLiveMarket()` < 100KB JSON payload
- [ ] Realtime debounced to max 1 update per second
- [ ] Frontend bundle < 500KB gzipped (code-split per route)
- [ ] Images lazy-loaded, served as WebP
- [ ] Service worker for offline (PWA) — caching static assets + last-known PSX data
- [ ] Database connection pool sized for peak load

### 14.3 Database
- [ ] All indexes in place (including missing `idx_psx_portfolios_user_id`)
- [ ] Drop redundant `idx_psx_ms_sym` and `idx_user_watchlist_user`
- [ ] `VACUUM ANALYZE` weekly (pg_cron)
- [ ] Realtime publication: add `psx_ticks` (or drop the table if not used)
- [ ] Add `psx_announcements` to Realtime (so UI updates without refresh)
- [ ] Consider `psx_signals` in Realtime (so the screener refreshes)
- [ ] TimescaleDB extension if `psx_ticks` grows (defer to Phase 9+)
- [ ] All money in `NUMERIC(14,2)` (no floats)
- [ ] All timestamps in `TIMESTAMPTZ` (no `TIMESTAMP`)

### 14.4 Observability
- [ ] Sentry for frontend errors
- [ ] Sentry for Python errors
- [ ] `/metrics` endpoint (Prometheus format)
- [ ] Request correlation IDs in all logs
- [ ] Uptime monitoring (e.g., BetterStack, UptimeRobot)
- [ ] Status page (e.g., status.nafaiq.app)
- [ ] PagerDuty / Slack alerts on critical errors

### 14.5 Backup & DR
- [ ] Supabase Pro for daily backups
- [ ] Verify restore procedure (test on staging)
- [ ] Document RTO/RPO targets
- [ ] Python service: stateless — no backup needed (all data in Supabase)
- [ ] Stripe is source of truth for subscriptions

### 14.6 CI/CD
- [ ] GitHub Actions: lint + typecheck + test on PR
- [ ] Auto-deploy to Vercel preview on PR
- [ ] Auto-deploy to production on `main` merge
- [ ] Python service: auto-deploy to Railway/Fly on `services/**` change
- [ ] Database migrations: require manual approval before applying to production
- [ ] Tag releases (`v1.0.0`, `v1.1.0`, ...)

### 14.7 Analytics (optional, Phase 9+)
- [ ] PostHog (self-hosted, no third-party) for product analytics
- [ ] Funnels: signup → first stock view → first watchlist add → first alert
- [ ] Track AI usage per plan

### 14.8 User feedback
- [ ] "Send Feedback" button in settings → opens email
- [ ] In-app NPS survey after 7 days of use
- [ ] Bug report form (Typeform or similar)

### 14.9 Documentation
- [ ] README (overview, quick start, deploy)
- [ ] API reference (auto-generated from FastAPI `/docs`)
- [ ] Component storybook (Storybook) — Phase 9
- [ ] Architecture diagram (update from this plan)
- [ ] Changelog
- [ ] Privacy policy
- [ ] Terms of service

### 14.10 Legal
- [ ] Disclaimer on all AI-generated content: "For educational purposes only. Not financial advice."
- [ ] PSX data attribution: "Market data provided by Pakistan Stock Exchange via DPS"
- [ ] Privacy policy compliant with Pakistan's PECA act
- [ ] Cookie consent banner (Phase 9)
- [ ] GDPR data export + delete (Phase 9)

---

## 15. Phase-by-Phase Development Roadmap

### Phase 0 — Security Incidents (1 day, urgent)

**Objectives:** Stop the bleeding from the leaked service-role key.

**Tasks:**
- [ ] **0.1** Rotate the Supabase service-role key (dashboard → Settings → API)
- [ ] **0.2** Purge `.env` from git history using `git filter-repo` and force-push
- [ ] **0.3** Add `.env` to root `.gitignore` and `services/psx-api/.gitignore`
- [ ] **0.4** Remove any other committed secrets (search for `eyJ...` JWT patterns)
- [ ] **0.5** Re-deploy the Python service with new env vars
- [ ] **0.6** Verify the old service-role key returns 401
- [ ] **0.7** Add a `SECURITY.md` with responsible disclosure process

**Completion criteria:** No `.env` files in git; old key revoked; new key in use.

**Dependencies:** None.

---

### Phase 1 — Database Cleanup & Hardening (1 week)

**Objectives:** Fix the 4 RLS gaps, regenerate `types.ts`, drop dead code, add missing indexes.

**Tasks:**

1.1. **RLS hardening** — New migration `20260714090000_rls_hardening.sql`:
- Add `WITH CHECK (user_id = auth.uid())` to 4 policies
- Drop redundant indexes (`idx_psx_ms_sym`, `idx_user_watchlist_user`)
- Add `idx_psx_portfolios_user_id`
- Add `idx_psx_fundamentals_sector` (sector-based queries)

1.2. **types.ts regeneration** — Run `supabase gen types typescript --project-id gmonfgxmjgzipnbhgimv > src/integrations/supabase/types.ts`. Commit the new file.

1.3. **Realtime publication** — Add `psx_announcements` to `supabase_realtime` publication.

1.4. **Frontend polish** (small fixes):
- `src/routes/psx.tsx:610-642` — replace `STOCKS[tk].price` with `live[tk]?.price ?? 0`
- `src/routes/psx.tsx:580-606` — replace `Object.keys(STOCKS)` with `usePsxSymbols()` data
- `src/routes/stock.$ticker.tsx:101` — add `/api/quote/{sym}/range?days=252` for real 52W high/low
- `src/lib/psx/client.ts:20` — read `import.meta.env.VITE_PSX_API_URL` with localhost default

1.5. **Dead code** — Delete `src/lib/psx/functions.ts` (unreferenced) — or keep as documentation of the original pattern.

1.6. **V1 tables** — Drop `psx_watchlist` and `psx_alerts` (superseded by v2) — but only after verifying no app code references them. Migration: `20260714090001_drop_v1_tables.sql`.

1.7. **Environment** — Create `.env.example` for frontend with all `VITE_*` keys.

**Completion criteria:**
- All 4 RLS gaps fixed
- `types.ts` covers all 15 tables
- V1 tables dropped
- No `.env` in git

**Dependencies:** Phase 0.

---

### Phase 2 — API Auth & Rate Limiting (1 week)

**Objectives:** Lock down the Python API.

**Tasks:**

2.1. **Auth middleware** — `app/api/deps.py` with `require_user` and `optional_user` (Section 7.3).

2.2. **CORS lock-down** — `app/main.py:53` — production origins only.

2.3. **Rate limiting** — `slowapi` per Section 7.4.

2.4. **Singleton CacheLayer** — `lru_cache` on `_cache()` factory in `market.py:12-13`.

2.5. **Auth on write endpoints** — `POST /api/screener`, `/api/backtest`, `/api/indicators/...`, `/api/signals/batch` require user JWT.

2.6. **Auth on read endpoints** — Optional auth; if present, higher rate limit.

2.7. **Frontend auth header** — `psx/client.ts` reads session JWT from `useAuth()` and adds `Authorization: Bearer ...` header.

2.8. **Health check expansion** — `/api/health/db` and `/api/health/scrapers`.

2.9. **Test** — Add `tests/test_auth.py` and `tests/test_rate_limit.py`.

**Completion criteria:**
- Unauthenticated requests to write endpoints return 401
- 61st request from one IP in a minute returns 429
- `/api/health/db` returns 200 with Supabase ping

**Dependencies:** Phase 1.

---

### Phase 3 — ML Model & Screener (2 weeks)

**Objectives:** Train the ML model, fix consistency bugs, wire screener to UI.

**Tasks:**

3.1. **Train the model** — Run `python services/psx-api/scripts/train_signal_model.py` after `job_backfill_history` has populated OHLCV. Artifacts: `signal_model.joblib`, `scaler.joblib`, `feature_list.json`, `metrics.json`.

3.2. **Fix label mapping** — `signal_engine.py:18` → use `model.classes_` instead of hardcoded dict.

3.3. **Fix env var mismatch** — `train_signal_model.py:31` → use `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (consistent with `config.py`).

3.4. **True walk-forward** — Replace cumulative folds with chronological splits (Section 7.1 + 7.2 row fixes).

3.5. **Unify RSI** — `features.py:_rsi` use Wilder's smoothing (same as `indicators.py`).

3.6. **Backtest engine** — Implement properly: KSE-100 baseline, `filter_spec` applied, transaction costs (0.5% brokerage + 0.1% CDC), proper median.

3.7. **Wire screener to UI** — `src/routes/psx.tsx:223-224, 247-248` → use `usePsxScreener()` mutation; display real signals/RSI/market cap.

3.8. **Signal history endpoint** — `GET /api/signal/{sym}/history?days=7` — store historical predictions in `psx_signals_history` (new table).

3.9. **Add backtest UI** — New "Backtest" tab in PSX page.

3.10. **ML metrics display** — `psx_signals.metrics` JSONB column with class distribution, model version, last trained date.

3.11. **Test** — `tests/test_signal_engine.py` with mock model, `tests/test_backtest.py` with known scenarios.

**Completion criteria:**
- Screener shows real signals for at least 80% of top-50 stocks
- Backtest returns real alpha numbers
- Model is trained with walk-forward (true) validation

**Dependencies:** Phase 2 (for `require_user` on screener endpoint).

---

### Phase 4 — Finance Module (3 weeks)

**Objectives:** Replace `useFinanceStore` mock data with real Supabase persistence.

**Tasks:**

4.1. **Migration** — `20260715090000_finance_module.sql` creates 7 tables (Section 6.3).

4.2. **Python API** — `app/api/finance.py` with 10 endpoints (Section 10.2). Reuses auth from Phase 2.

4.3. **Frontend types** — Regenerate `types.ts`.

4.4. **Hooks** — `useFinanceAccounts()`, `useFinanceCategories()`, `useFinanceTransactions()`, `useFinanceBudgets()`, `useFinanceBills()`, `useFinanceGoals()`, `useZakat()`.

4.5. **Migration utility** — `importFromLocalStorage()` runs once on first login, reads `nafaiq:finance:v1` from localStorage, bulk-inserts to Supabase, clears localStorage.

4.6. **Page refactor** — `src/routes/finance.tsx`:
- Remove all `useFinanceStore` calls
- Use the new hooks
- Add Accounts, Categories tabs (new)
- Compute KPIs live (sum of transactions)
- Charts: real income/expense from Supabase

4.7. **Dashboard refactor** — `src/routes/app.tsx`:
- Watchlist widget: use `useWatchlist()` (real)
- Goals widget: use `useFinanceGoals()`
- Bills widget: use `useFinanceBills()`
- Transactions: use `useFinanceTransactions()` (top 5)

4.8. **Alerts refactor** — `src/routes/alerts.tsx`:
- Price alerts: read from `useWatchlist()` (real) instead of `STOCKS` hardcoded
- Bill/Budget/Goal alerts: real from `useFinanceBills/Budgets/Goals()`

4.9. **Notifications** — `app/api/alerts.py`, `app/services/notifier.py` (Resend for email, Web Push for push). Add `in_app_notifications` table.

4.10. **Test** — Vitest for the new hooks; E2E for the add/transaction flow.

**Completion criteria:**
- `useFinanceStore` deleted
- All finance data persists in Supabase
- Cross-device sync works
- Price alerts send email + in-app notification on trigger

**Dependencies:** Phase 2.

---

### Phase 5 — Portfolio Module (2 weeks)

**Objectives:** Real portfolio P&L, real Haqeeqi Daulat, real AI report.

**Tasks:**

5.1. **View** — `v_user_portfolio_value` (SQL in Section 9.3).

5.2. **FX rates** — New `app/api/fx.py` and `fx_rates` table. Daily cron `job_refresh_fx` from SBP API.

5.3. **Python API** — `app/api/portfolio.py` with 5 endpoints (Section 10.2).

5.4. **Frontend hooks** — `usePortfolios()`, `usePortfolio(id)`, `useAddHolding()`, `useUpdateHolding()`, `useDeleteHolding()`, `useHaqeeqiDaulat(portfolioId, currency)`.

5.5. **Page refactor** — `src/routes/portfolio.tsx`:
- KPIs: live from `usePortfolio(id).value`
- Performance chart: from `usePortfolioPerformance(id, '1Y')` (joins `psx_ohlcv`)
- Sector allocation: live aggregation
- Haqeeqi Daulat: real USD calc
- "Add to Portfolio" button (5.6)

5.6. **Add-holding flow** — New `<AddHoldingModal>` component, opened from `stock.$ticker.tsx:326-328` (the dead button) and from `portfolio.tsx`.

5.7. **Stock detail 52W data** — `src/routes/stock.$ticker.tsx:101` — display real 52W high/low from new endpoint (also done in Phase 1.4).

5.8. **Multi-currency (Pro+)** — `useHaqeeqiDaulat` with currency param; gate behind plan check.

5.9. **Test** — E2E for add/edit/delete holding.

**Completion criteria:**
- Portfolio P&L updates within 8s of market refresh
- Haqeeqi Daulat shows correct USD return
- "Add to Portfolio" works from stock detail

**Dependencies:** Phase 4 (so finance notifications use the same notifier).

---

### Phase 6 — AI Features (2 weeks)

**Objectives:** Replace hardcoded AI strings with real LLM calls.

**Tasks:**

6.1. **Migration** — `20260716090000_ai_usage_and_history.sql` (3 tables).

6.2. **Python API** — `app/api/ai.py` with 6 endpoints (Section 10.2). Uses Lovable Gateway (or direct Gemini API).

6.3. **Prompt library** — `app/services/prompts.py` with the 5 prompt templates (Section 9.4).

6.4. **Quota tracking** — `app/services/quota.py` reads `ai_usage`, increments on each call, raises 429 on overflow.

6.5. **Plan gating** — `usePlanFeatures()` (Section 5.5) hooks into AI endpoints.

6.6. **Frontend hooks** — `useAiMarketBrief()`, `useAiStockAnalysis(ticker)`, `useAiPortfolioReport()`, `useAiFinanceReport()`, `useAiDailyRecommendation()`, `useAiUsage()`.

6.7. **Page refactors:**
- `psx.tsx:425-430` — `useAiMarketBrief()`
- `stock.$ticker.tsx:268-280` — `useAiStockAnalysis(ticker)`
- `portfolio.tsx:632-711` — `useAiPortfolioReport()`
- `finance.tsx:876-955` — `useAiFinanceReport()`
- `app.tsx:150-178` — `useAiDailyRecommendation()`

6.8. **AI Tutor persistence** — Save messages to `ai_chat_history` from `learn-ai.functions.ts`. Currently it just calls Gemini without persistence.

6.9. **Disclaimer** — Add "AI-generated. Not financial advice." footer to every AI report.

6.10. **Streaming** (optional) — Server-Sent Events for the AI tutor so users see responses as they generate.

6.11. **Test** — Mock LLM responses; verify quota enforcement; verify rate limit; verify plan gating.

**Completion criteria:**
- All 5 AI features use real LLM
- Quota enforced per plan
- "Not financial advice" disclaimer on all outputs

**Dependencies:** Phase 4 (for plan_features table and notifier for email quota warnings).

---

### Phase 7 — Auth Completion (1 week)

**Objectives:** Password reset, MFA, profile editing, onboarding.

**Tasks:**

7.1. **New pages:**
- `/auth/reset` — Forgot password form
- `/auth/update` — Reset password (post-email-link)
- `/settings/account` — Profile, avatar, email, MFA

7.2. **useAuth expansion** — Add `resetPassword(email)`, `updatePassword(newPw)`, `updateProfile({ display_name, avatar_url })`, `enrollMfa()`, `verifyMfa(code)`, `disableMfa()`.

7.3. **Avatar upload** — Supabase Storage bucket `avatars` (public read, own-write via RLS).

7.4. **MFA (TOTP)** — Supabase supports TOTP via `supabase.auth.mfa.enroll({ factorType: 'totp' })`. Store `mfa_enabled` flag in `profiles`.

7.5. **Onboarding tour** — 3-step modal on first `/app` visit. Set `profiles.onboarding_complete = true` on completion.

7.6. **Account deletion** — Supabase Edge Function `delete-user` that calls `auth.admin.deleteUser(uid)`. CASCADE removes all user data.

7.7. **Email change** — `supabase.auth.updateUser({ email })` triggers re-confirmation flow.

7.8. **Test** — E2E for sign-up, reset, MFA.

**Completion criteria:**
- Password reset works end-to-end
- MFA can be enabled and used to log in
- Profile editing persists
- Account deletion removes all user data

**Dependencies:** Phase 1 (RLS on `profiles`).

---

### Phase 8 — Payments (2 weeks)

**Objectives:** Real Stripe integration, plan gating, billing portal.

**Tasks:**

8.1. **Stripe account setup** — Create products for Pro and Premium, get API keys.

8.2. **Migration** — `20260717090000_subscriptions_and_features.sql` (4 tables: subscriptions, plan_features, stripe_events, invoices).

8.3. **Python API** — `app/api/billing.py` with 5 endpoints (Section 10.2).

8.4. **Webhook handler** — Verifies Stripe signature (`STRIPE_WEBHOOK_SECRET`), handles events (Section 9.6).

8.5. **Frontend hooks** — `useSubscription()`, `usePlanFeatures()`, `useStartCheckout(plan)`, `useOpenPortal()`.

8.6. **Pages:**
- `/plans` — wire CTAs to `useStartCheckout(plan)`. On success → `useNavigate({ to: '/app?welcome=1' })`.
- `/settings/billing` (new) — show current plan, payment method, invoice history, manage button.

8.7. **Plan gating** — Apply to:
- Watchlist size
- Alert count
- AI Tutor quota
- AI Reports
- Portfolio count
- Haqeeqi Daulat multi-currency
- Export

8.8. **Paywall cards** — `<PaywallCard feature="..." requiredPlan="Pro">` shown when limit hit.

8.9. **Test** — Mock Stripe webhooks; verify subscription state; verify plan transitions.

**Completion criteria:**
- User can upgrade to Pro via Stripe checkout
- Subscription state syncs to `subscriptions` table
- Plan-gated features are locked for Free users
- Customer portal accessible for cancel/update

**Dependencies:** Phase 6 (for AI quota integration).

---

### Phase 9 — Production Hardening (2 weeks)

**Objectives:** Tests, monitoring, CI/CD, deployment.

**Tasks:**

9.1. **Tests** — Implement all tests from Section 13. Targets: 80% Python coverage, 70% TS coverage.

9.2. **Sentry** — Add `@sentry/react` to frontend, `sentry-sdk[fastapi]` to Python. Capture unhandled errors.

9.3. **CI/CD** — GitHub Actions:
- Lint + typecheck + test on PR
- Auto-deploy to Vercel preview on PR
- Auto-deploy to production on `main`
- Python service: auto-deploy on `services/**` change

9.4. **Migrations** — Require manual approval before applying to production. Use `supabase db push --dry-run` in CI.

9.5. **Environment** — Production env vars set in Vercel + Railway dashboards. Document in `README.md`.

9.6. **Observability** — `/metrics` endpoint, request correlation IDs, structured logs to stdout.

9.7. **Status page** — Statuspage.io or BetterStack Status Page. Surface:
- API uptime
- Database uptime
- Supabase status
- Recent incidents

9.8. **Security headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy. Configure in `vite.config.ts` and Nginx/Caddy.

9.9. **reCAPTCHA / Turnstile** — Add to `/auth` sign-in, sign-up, password reset.

9.10. **PII scrubbing** — Custom structlog processor that masks emails and JWTs.

9.11. **PWA** — Service worker (Workbox) for offline support, app install prompt.

9.12. **Error events table** — Optional: Sentry mirror for queries.

9.13. **Data export + delete UI** — `/settings/privacy` — export all data as JSON, request deletion.

9.14. **Cookie consent** — Banner for any future analytics/tracking (Phase 9+ if added).

9.15. **Test E2E in production** — Playwright runs nightly against production to catch regressions.

9.16. **Documentation** — Update `README.md` with deploy instructions, `ARCHITECTURE.md` with system diagram, `API.md` with endpoint list.

**Completion criteria:**
- All tests pass in CI
- Sentry receives errors from both frontend and backend
- Production deployments are automated
- Uptime monitoring alerts on incidents

**Dependencies:** All previous phases.

---

### Phase 10 — Post-Launch (continuous, optional)

- **News feed** — PSX company news, scraped from DPS
- **Sentiment analysis** — FinBERT or similar on news
- **Backtesting UI** — Visualize equity curve
- **API access** — Premium tier API keys for external integrations
- **Mobile app** — React Native, sharing components with web
- **Localization** — Add Urdu to the auth page, not just the UI
- **Push notifications** — Web Push fully working on iOS Safari (16.4+)
- **Advanced indicators** — Ichimoku, Keltner, Parabolic SAR
- **Screener save & share** — Save queries, share via link
- **Community features** — Public watchlists, signal leaderboard (opt-in)

---

## 16. Final Launch Checklist

### Pre-launch
- [ ] All Phase 0-9 tasks complete
- [ ] All tests pass in CI (Python + TypeScript + E2E)
- [ ] No `TODO`, `FIXME`, `XXX`, `HACK` comments in shipped code
- [ ] All secrets in env, none in repo
- [ ] `.env.example` files exist for frontend and backend
- [ ] `README.md` is current with run/deploy instructions
- [ ] `LICENSE` is set (MIT recommended for an open-source-friendly repo)
- [ ] `SECURITY.md` defines responsible disclosure
- [ ] Privacy policy published
- [ ] Terms of service published
- [ ] Domain registered (`nafaiq.app` or chosen name)
- [ ] SSL cert provisioned (Let's Encrypt via Vercel/Railway)
- [ ] DNS configured
- [ ] Email domain verified in Resend
- [ ] Stripe account verified, products created
- [ ] Sentry project created
- [ ] Status page created
- [ ] Backup verified (test restore on staging)
- [ ] DR runbook documented

### Launch day
- [ ] Run all migrations on production Supabase
- [ ] Deploy Python service to Railway/Fly
- [ ] Deploy frontend to Vercel
- [ ] Verify `/api/health` returns 200
- [ ] Verify `/api/market/snapshot` returns 495 stocks
- [ ] Verify `/psx` page loads in <3s
- [ ] Verify auth flow (sign-up, sign-in, password reset)
- [ ] Verify Stripe checkout (test mode first, then live)
- [ ] Verify Sentry receives an intentional test error
- [ ] Verify status page is green
- [ ] Post announcement on social media
- [ ] Email beta list

### Post-launch (first 7 days)
- [ ] Monitor Sentry hourly for new errors
- [ ] Monitor uptime hourly
- [ ] Check Stripe dashboard for failed payments
- [ ] Respond to user feedback
- [ ] Fix any critical bugs within 24h
- [ ] Write a post-mortem for any incident

### First 30 days
- [ ] Analyze PostHog funnels
- [ ] Survey users (NPS)
- [ ] Plan first post-launch feature
- [ ] Review security advisories
- [ ] Rotate any exposed secrets

---

## Appendix A — File-Level Action Plan

For developers picking this up: a flat list of files to create or modify, by phase.

### Phase 0 (1 day)
- (operational, not in repo)
- Update `.gitignore` (root + `services/psx-api/`)
- Add `SECURITY.md`

### Phase 1 (1 week)
- New: `supabase/migrations/20260714090000_rls_hardening.sql`
- New: `supabase/migrations/20260714090001_drop_v1_tables.sql`
- Modify: `src/integrations/supabase/types.ts` (regenerate)
- Modify: `src/routes/psx.tsx` (lines 610-642, 580-606)
- Modify: `src/routes/stock.$ticker.tsx` (line 101)
- Modify: `src/lib/psx/client.ts` (line 20)
- Delete: `src/lib/psx/functions.ts` (or keep as documentation)
- New: `.env.example` (root)

### Phase 2 (1 week)
- New: `services/psx-api/app/api/deps.py`
- Modify: `services/psx-api/app/main.py` (CORS, rate limit)
- Modify: `services/psx-api/app/api/market.py` (singleton CacheLayer, auth/ratelimit on routes)
- Modify: `services/psx-api/app/api/health.py` (add `/db` and `/scrapers`)
- Modify: `src/lib/psx/client.ts` (auth header)
- New: `services/psx-api/tests/test_auth.py`
- New: `services/psx-api/tests/test_rate_limit.py`

### Phase 3 (2 weeks)
- Modify: `services/psx-api/scripts/train_signal_model.py` (env vars, walk-forward, labels)
- Modify: `services/psx-api/app/services/signal_engine.py` (label mapping, race fix)
- Modify: `services/psx-api/app/ml/features.py` (Wilder's RSI)
- Modify: `services/psx-api/app/services/indicators.py` (alignment with features)
- Modify: `services/psx-api/app/services/backtest.py` (real implementation)
- Modify: `services/psx-api/app/jobs/scheduler.py` (Friday close, signal refresh job)
- New: `services/psx-api/app/api/signal_history.py` (or extend `signals.py`)
- New: `services/psx-api/tests/test_signal_engine.py`
- New: `services/psx-api/tests/test_backtest.py`
- Modify: `src/routes/psx.tsx` (screener wiring, lines 223-263)
- New: `src/components/SignalHistory.tsx`
- New: `src/components/BacktestForm.tsx` (new PSX tab)

### Phase 4 (3 weeks)
- New: `supabase/migrations/20260715090000_finance_module.sql`
- New: `supabase/migrations/20260715090001_notifications.sql`
- New: `services/psx-api/app/api/finance.py`
- New: `services/psx-api/app/api/alerts.py`
- New: `services/psx-api/app/services/notifier.py` (Resend + Web Push)
- New: `services/psx-api/app/services/webpush.py`
- Modify: `services/psx-api/app/jobs/scheduler.py` (add `job_check_bills`, `job_check_budgets`)
- New: `services/psx-api/tests/test_finance.py`
- New: `services/psx-api/tests/test_notifier.py`
- New: `src/hooks/use-finance-*.ts` (7 hooks)
- New: `src/hooks/use-in-app-notifications.ts`
- New: `src/hooks/use-push-subscription.ts`
- Modify: `src/routes/finance.tsx` (full rewrite)
- Modify: `src/routes/app.tsx` (use real hooks)
- Modify: `src/routes/alerts.tsx` (real data)
- Delete: `src/hooks/use-finance-store.ts`

### Phase 5 (2 weeks)
- New: `supabase/migrations/20260715090002_portfolio_and_fx.sql`
- New: `supabase/migrations/20260715090003_v_user_portfolio_value.sql` (view)
- New: `services/psx-api/app/api/portfolio.py`
- New: `services/psx-api/app/api/fx.py`
- Modify: `services/psx-api/app/jobs/scheduler.py` (add `job_refresh_fx`)
- New: `services/psx-api/tests/test_portfolio.py`
- New: `src/hooks/use-portfolios.ts`
- New: `src/components/AddHoldingModal.tsx`
- New: `src/components/HaqeeqiDaulatCard.tsx`
- Modify: `src/routes/portfolio.tsx` (full rewrite)
- Modify: `src/routes/stock.$ticker.tsx` (Add to Portfolio button at line 326-328)

### Phase 6 (2 weeks)
- New: `supabase/migrations/20260716090000_ai_usage_and_history.sql`
- New: `services/psx-api/app/api/ai.py`
- New: `services/psx-api/app/services/llm.py` (Lovable Gateway client)
- New: `services/psx-api/app/services/prompts.py`
- New: `services/psx-api/app/services/quota.py`
- New: `services/psx-api/tests/test_ai.py`
- New: `src/hooks/use-ai.ts` (5 hooks)
- New: `src/lib/ai-types.ts`
- Modify: `src/lib/learn/ai-functions.ts` (persist to `ai_chat_history`)
- Modify: `src/routes/psx.tsx:425-430` (AI brief)
- Modify: `src/routes/stock.$ticker.tsx:268-280` (stock analysis)
- Modify: `src/routes/portfolio.tsx:632-711` (portfolio report)
- Modify: `src/routes/finance.tsx:876-955` (finance report)
- Modify: `src/routes/app.tsx:150-178` (daily recommendation)

### Phase 7 (1 week)
- New: `src/routes/auth.reset.tsx`
- New: `src/routes/auth.update.tsx`
- New: `src/routes/settings.account.tsx`
- Modify: `src/hooks/use-auth.tsx` (add reset/update/MFA methods)
- New: `supabase/functions/delete-user/index.ts` (Edge Function)
- Modify: `supabase/migrations/*.sql` (add `mfa_enabled`, `onboarding_complete`, `phone` to `profiles`)

### Phase 8 (2 weeks)
- New: `supabase/migrations/20260717090000_subscriptions_and_features.sql`
- New: `services/psx-api/app/api/billing.py`
- New: `services/psx-api/app/services/stripe_client.py`
- New: `services/psx-api/tests/test_billing.py`
- New: `src/hooks/use-subscription.ts`
- New: `src/hooks/use-plan-features.ts`
- New: `src/lib/stripe-client.ts`
- New: `src/components/PaywallCard.tsx`
- New: `src/routes/settings.billing.tsx`
- Modify: `src/routes/plans.tsx` (wire to Stripe)
- Modify: `src/hooks/use-watchlist.ts` (plan-gate additions)
- Modify: `src/hooks/use-ai.ts` (plan-gate calls)
- Modify: `src/hooks/use-finance-*.ts` (plan-gate creation)

### Phase 9 (2 weeks)
- New: `services/psx-api/app/observability.py` (request IDs, /metrics)
- New: `services/psx-api/Dockerfile.improved`
- New: `services/psx-api/.dockerignore`
- New: `.github/workflows/ci.yml`
- New: `.github/workflows/deploy.yml`
- New: `vitest.config.ts` (frontend)
- New: `services/psx-api/pytest.ini`
- New: `playwright.config.ts`
- New: `e2e/*.spec.ts` (10 specs from Section 13.5)
- Modify: `services/psx-api/pyproject.toml` (remove tenacity or use it)
- Modify: `services/psx-api/Dockerfile` (non-root, HEALTHCHECK, multi-stage)
- Modify: `vite.config.ts` (security headers via plugin)
- New: `src/lib/sentry.ts`
- New: `services/psx-api/app/sentry.py`
- New: `src/lib/cookie-consent.tsx`

---

## Appendix B — Glossary

- **DPS** — Data Dissemination Portal (`dps.psx.com.pk`), the official PSX data source (15min delay)
- **AhleTrade** — Real-time PSX feed at `feed.ahletrade.com`
- **TradingView Scanner** — Public REST API for sector data
- **Nitro** — Universal server engine powering TanStack Start
- **Shadcn/ui** — Copy-paste React component library built on Radix UI
- **Haqeeqi Daulat** — "Real Wealth" — NafaIQ's core feature showing PKR returns adjusted for USD devaluation
- **KSE-100** — Karachi Stock Exchange 100 index, the main PSX benchmark
- **PKT** — Pakistan Standard Time (UTC+5)
- **Service role** — Supabase's bypass-RLS key for server-side writes
- **Anon key** — Supabase's public, RLS-enforced key
- **RLS** — Row-Level Security, PostgreSQL feature for per-row access control
- **JWT** — JSON Web Token, used for Supabase auth
- **GBC** — Gradient Boosting Classifier, the ML model class
- **OHLCV** — Open, High, Low, Close, Volume — candlestick data
- **DPS scraper** — the Python class that fetches data from DPS

---

## Appendix C — Document History

- **2026-07-07** — Initial plan created from full project audit
