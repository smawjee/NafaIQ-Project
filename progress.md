# NafaIQ — Progress Tracker

> **Always read this file first** before starting any task. Update after completing work.
> **Last updated:** 2026-07-08 (Monorepo structure per mentor's spec — pushed to develop)

---

## Architecture Decision (2026-07-08) — RESOLVED

**Pattern:** Layered Architecture with BaaS-Backed Microservices and Read-Through Cache
**Data access:** Hybrid — Supabase REST (bulk writes) + SQLAlchemy Core (complex queries)
**ORM:** SQLAlchemy Core (Python service only, via Supavisor transaction pooler)
**Spec:** `docs/superpowers/specs/2026-07-08-architecture-orm-design.md`
**Decision log:** `recall/explaination.md` — entry #41 (updated with pooler details)

### SQLAlchemy Core — connected and working
- [x] `app/db/sqlalchemy.py` — async engine via **Supavisor transaction pooler** (`aws-1-ap-southeast-1.pooler.supabase.com:6543`). Uses NullPool (pooler handles pooling) + `statement_cache_size=0` (pgbouncer compat)
- [x] `app/db/orm.py` — auto-reflects schema from live DB (no manual schema drift)
- [x] `app/config.py` — `SUPABASE_POOLER_HOST/PORT/USER` settings, multi-path `.env` lookup
- [x] `tests/test_sqlalchemy_queries.py` — **7 pass, 1 skip** (`fx_rates` not yet created, Phase 5)
- [x] `/api/market/sectors/avg` — example SQLAlchemy Core endpoint (test passes)

### What stays on Supabase REST
- Bulk upserts (market refresh, 495 rows in 3s)
- Simple lookups (one symbol, one row)
- All frontend data access (Supabase JS)
- Realtime subscriptions

### What uses SQLAlchemy Core (Phase 4+)
- Finance module joins + aggregations
- Portfolio P&L calculations
- Analytics queries (window functions, CTEs)
- `/api/health/db` Postgres ping

---

## Phase Status Overview

| # | Phase | Status |
|---|-------|--------|
| 0 | Security incidents + .env rotation | ✅ Complete |
| 1 | DB cleanup + types.ts sync + RLS hardening | ✅ Complete (see notes) |
| 2 | PSX API auth + rate limiting + dead code removal | ✅ Complete (2026-07-08) |
| 3 | ML model training + screener UI wiring + backtest fix | ⬜ Pending |
| 4 | Finance module: Supabase persistence + real transactions | ⬜ Pending |
| 5 | Portfolio module: real holdings + Haqeeqi Daulat live calc | ⬜ Pending |
| 6 | AI features: real LLM calls for Reports, Tutor, Recommendations | ⬜ Pending |
| 7 | Auth completion: password reset, MFA, profile editing | ⬜ Pending |
| 8 | Payments: Stripe integration + plan gating | ⬜ Pending |
| 9 | Production hardening: tests, monitoring, CI/CD, deployment | ⬜ Pending |

---

## Phase 0 — Security (✅ Complete)

- [x] `.gitignore` updated — excludes `.env` / `.env.*`, allows `.env.example`
- [x] Service-role key rotated in Supabase Dashboard
- [x] `config.py` updated with 4-key convention (`SECRET_KEY` / `PUBLISHABLE_KEY` / etc.)
- [x] `.env.example` (root + psx-api) updated with placeholders
- [x] `supabase.py` uses new `supabase_service_key` property
- [x] `.gitattributes` added for LF line endings

## Phase 1 — DB Cleanup + Types + RLS (✅ Complete)

- [x] RLS `WITH CHECK` migration: `20260707100000_rls_with_check_fix.sql`
  - Adds `WITH CHECK` to: `user_watchlist`, `price_alerts`, `psx_portfolios`, `psx_holdings`
- [x] `types.ts` regenerated — covers all **17 tables** (was 4/16)
- [x] `AGENTS.md` updated with phase status, conventions, commands
- [x] Config refactored to 4-key convention
- [x] Dead `integrations/nafaiq/` removed (Lovable OAuth module)
- [x] `.opencode/` skills removed from tracking
- [x] `bun.lock`/`bunfig.toml` removed (uses npm)
- [x] **Index added** (2026-07-08): `idx_psx_portfolios_user_id` (migration `20260708011922_add_idx_psx_portfolios_user_id.sql`)
- [x] **Dead code removed** (2026-07-08): `src/lib/psx/functions.ts` (zero references, typecheck passes)

**⚠️ Carried forward (deferred per user request — do NOT drop):**
- [ ] ~~Drop v1 tables: `psx_watchlist`, `psx_alerts`~~ — DEFERRED (user: "dont remove any table right now")
- [ ] v1 tables remain in DB; documented in `recall/explaination.md` decision #34

## Phase 2 — PSX API Auth + Rate Limiting + DB Access (✅ Complete — 2026-07-08)

### ✅ Already done (from Phase 1 carryovers)
- [x] Add `idx_psx_portfolios_user_id` (migration written + applied via SQLAlchemy)
- [x] Remove dead `psx/functions.ts` (zero references, deleted, typecheck passes)
- [ ] Drop v1 tables — DEFERRED per user request

### ✅ Phase 2 active tasks (completed 2026-07-08)
- [x] Bearer-token auth on Python API endpoints (`app/middleware/auth.py` + `app/config.py`)
  - Public endpoints exempt: `/api/health`, `/api/health/db`, `/docs`, `/openapi.json`, `/redoc`
  - Token: `PSX_API_TOKEN` in `.env` (generated with `secrets.token_urlsafe(32)`)
  - Verified: 401 without token, 200 with valid token, 401 with wrong token
- [x] Rate limiting via slowapi (`app/middleware/rate_limit.py`)
  - 60 req/min public (snapshot, quote), 30 req/min heavy (sectors, symbols, history)
  - Registered in `app.main.py`: `app.state.limiter` + exception handler
- [x] Singleton `CacheLayer` via `lru_cache` in `app/api/market.py`
  - Replaced per-request `CacheLayer(DPSScraper())` with `@lru_cache(maxsize=1)` singleton
- [x] `psx/client.ts:20` reads `VITE_PSX_API_URL` + `VITE_PSX_API_TOKEN`
  - Frontend `get()` and `post()` send `Authorization: Bearer <token>` header
  - `npx tsc --noEmit` passes
- [x] `/api/health/db` with actual Postgres ping at `app/api/health.py:36`
  - Uses SQLAlchemy Core `SELECT 1` with latency measurement
  - Verified: `{"status": "ok", "latency_ms": 1121.88}`
- [x] `ensure_reflected()` called at startup in `app/main.py` lifespan

## Phase 3 — ML + Screener + Backtest (⬜ Pending)

- [ ] Train ML model + save artifacts
- [ ] Fix label mapping to use `model.classes_`
- [ ] Fix env var name mismatch (`PSX_SUPABASE_*` → `SUPABASE_*`)
- [ ] Implement true walk-forward (chronological splits)
- [ ] Unify RSI (Wilder's in both `features.py` and `indicators.py`)
- [ ] Wire `/api/screener` to `psx.tsx` UI
- [ ] Implement real backtest engine
- [ ] Add `job_realtime_signal_refresh` (top 50 movers, 15min)

## Phase 4 — Finance Module (⬜ Pending)

Tables to create: `finance_accounts`, `finance_categories`, `finance_transactions`, `finance_budgets`, `finance_bills`, `finance_goals`, `finance_contributions`, `finance_zakat_calculations`, `in_app_notifications`, `push_subscriptions`, `user_notification_prefs`

- [ ] Create API endpoints (10+)
- [ ] Migrate from localStorage to Supabase
- [ ] Add notification delivery (email via Resend, push via Web Push)

## Phase 5 — Portfolio Module (⬜ Pending)

- [ ] Real holdings from Supabase
- [ ] Live P&L calculation (SQL view)
- [ ] Live Haqeeqi Daulat (multi-currency)
- [ ] `fx_rates` table + SBP API

## Phase 6 — AI Features (⬜ Pending)

- [ ] Real LLM calls for Market Brief, Stock Analysis, Portfolio Report
- [ ] Server-side conversation history + quota enforcement
- [ ] Tables: `ai_usage`, `ai_chat_history`, `ai_reports`

## Phase 7 — Auth Completion (⬜ Pending)

- [ ] Password reset pages
- [ ] MFA (TOTP)
- [ ] Profile editing (`/settings/account`)
- [ ] Onboarding flow

## Phase 8 — Payments (⬜ Pending)

- [ ] Stripe Checkout integration
- [ ] Webhook handler
- [ ] `subscriptions` table + plan gating

## Phase 9 — Production Hardening (⬜ Pending)

- [ ] Sentry error monitoring
- [ ] Rate limiting (carried from Phase 2)
- [ ] CI/CD (GitHub Actions)
- [ ] Docker improvements (non-root, HEALTHCHECK)
- [ ] Prometheus metrics

---

## Known Technical Debt (from `recall/Complete Project Plan.md`)

| # | Issue | Location | Severity |
|---|-------|----------|----------|
| 1 | ~~Service-role key committed to git~~ | ✅ Rotated + gitignored | ~~🔴 Critical~~ |
| 2 | CORS `allow_origins=["*"]` | `main.py:53` | 🔴 High |
| 3 | ~~4 RLS policies missing `WITH CHECK`~~ | ✅ Fixed in migration | ~~🟠 High~~ |
| 4 | ~~`types.ts` covers 4/15 tables~~ | ✅ Regenerated (17 tables) | ~~🟠 High~~ |
| 5 | `CacheLayer` instantiated per request | `market.py:12-13` | 🟠 High |
| 6 | `signal_engine.py` hardcoded class labels | `signal_engine.py:18` | 🟠 High |
| 7 | Env var name mismatch (`PSX_SUPABASE_*`) | `train_signal_model.py:31` | 🟠 High |
| 8 | Two RSI implementations (train vs serve) | `features.py:97` vs `indicators.py:48` | 🟠 High |
| 9 | "Walk-forward" folds are cumulative | `train_signal_model.py` | 🟠 High |
| 10 | Backtest endpoint is a stub | `backtest.py` | 🟡 Medium |
| 11 | `psx_ticks` not in realtime publication | migration `20260706130000` | 🟡 Medium |
| 12 | 13 silent `except Exception: pass` | multiple files | 🟡 Medium |
| 13 | `tenacity` dep declared but unused | `pyproject.toml` | 🟢 Low |
| 14 | Docker runs as root, no HEALTHCHECK | `Dockerfile` | 🟢 Low |
| 15 | `psx/functions.ts` dead code | `src/lib/psx/functions.ts` | 🟢 Low |
| 16 | v1 tables `psx_watchlist`/`psx_alerts` dead | migrations | 🟢 Low |
| 17 | `_loaded` race in `signal_engine.py` | `signal_engine.py:30-39` | 🟢 Low |
| 18 | `announcement_id` collision risk | `dps.py:401` | 🟢 Low |
| 19 | Friday early close not handled | `scheduler.py` | 🟢 Low |
| 20 | Redundant indexes | migration `20260706130000` | 🟢 Low |
| 21 | Missing `idx_psx_portfolios_user_id` | migration `20260706120000` | 🟢 Low |
| 22 | 3 mock data sources still imported by 6 files | `data.ts`, `finance/data.ts` | 🟡 Medium |
| 23 | `psx/client.ts:20` hardcodes `localhost:8000` | `psx/client.ts` | 🟡 Medium |

---

## Recent Commits (chronological)

| Date | Commit | Description |
|------|--------|-------------|
| 2026-07-07 | `498cd3c` | Refactor config to 4-key convention |
| 2026-07-07 | `18ca480` | Add legacy `SUPABASE_PUBLISHABLE_KEY` alias |
| 2026-07-07 | `6461872` | Regenerate `types.ts` from live schema |
| 2026-07-07 | `f802a02` | Add `.gitattributes`, LF line endings |
| 2026-07-07 | `dd4853f` | Update `AGENTS.md` — types regen, RLS, phase status |
| 2026-07-07 | `868ca87` | Gitignore `.env`, env examples, RLS migration |
| 2026-07-07 | `ab8d319` | Add `requirements.txt`, `.env.example`, fix `__init__.py` |
| 2026-07-07 | `9afa1d7` | Restructure src/, remove dead code, fix config |
