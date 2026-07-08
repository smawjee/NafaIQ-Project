# NafaIQ — Project Architecture & Flow

> **Last updated:** 2026-07-07
> **Status:** PSX Module — Phase 6 (User Features complete, Phase 7 Hardening pending)

## Project Overview

**NafaIQ** is a Pakistan Stock Exchange trading terminal + personal finance manager delivered as a web app (PWA). It combines live PSX market data, AI-powered trading signals, devaluation-adjusted wealth tracking (Haqeeqi Daulat), financial education, and portfolio management.

**Stack:**
- **Frontend:** TanStack Start (React 19 + Vite), Supabase Auth, TailwindCSS, Recharts, shadcn/ui, TanStack Query, TanStack Router
- **Backend:** Python FastAPI microservice → scrapes DPS, TradingView scanner, AhleTrade → caches in Supabase
- **Database:** Supabase Postgres (auth, user data, PSX cache, realtime)
- **Hosting:** Frontend on Vercel/Lovable Cloud; Python service on Railway/Fly/Render

---

## Module Roadmap

| Phase | Module | Status | Scope |
|---|---|---|---|
| **1** | Python Backend Foundation | ✅ Complete | FastAPI scaffold, DPS scrapers, Supabase schema, cache layer, background jobs |
| **2** | REST API Surface | ✅ Complete | 17 endpoints (see below), all tested with real data |
| **3** | Realtime Data Layer | ✅ Complete | AhleTrade poller wired to psx_market_snapshot, Supabase Realtime enabled |
| **4** | Frontend Integration | ✅ Complete | Direct fetch hooks (usePsxLiveMarket, usePsxHistory, etc.), single-source-of-truth architecture |
| **5** | ML Signal Engine | ✅ Complete | 27-feature GBC model, walk-forward validation, SignalEngine service (not yet trained) |
| **6** | User Features | ✅ Complete | Watchlist CRUD (Supabase RLS), price alerts CRUD (Supabase RLS), screener filter UI, sector heatmap |
| **7** | Hardening | ⬜ Pending | Error monitoring (Sentry), rate limiting, load testing, model training |
| **8** | Finance Module | ⬜ Pending | Budgets, expenses, goals, Zakat calculator |

---

## Data Sources

| Source | Type | Coverage | Latency | URL |
|---|---|---|---|---|
| DPS (PSX Portal) | HTML/JSON scraping | 495 stocks, OHLCV, announcements, dividends, index EOD | 15+ min | `https://dps.psx.com.pk` |
| TradingView Scanner | REST JSON API | 478 stocks with sectors, market caps | Near real-time | `https://scanner.tradingview.com/pakistan/scan` (POST) |
| AhleTrade Feed | Pipe-delimited HTTP | Real-time trade tape | Real-time | `http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher` |

---

## Database Schema (15 tables)

All PSX tables live in Supabase Postgres (`gmonfgxmjgzipnbhgimv`).

| Table | Purpose | RLS |
|---|---|---|
| `psx_market_snapshot` | Live prices (495 stocks, 5s refresh) | Public read, service_role write |
| `psx_ohlcv` | Daily OHLCV history | Public read, service_role write |
| `psx_fundamentals` | P/E, EPS, P/B, ROE, dividend yield | Public read, service_role write |
| `psx_profile` | Symbol, name, sector (TradingView + DPS) | Public read, service_role write |
| `psx_announcements` | Corporate announcements | Public read, service_role write |
| `psx_dividends` | Dividend history | Public read, service_role write |
| `psx_index_eod` | KSE-100/KSE-30/ALL-SHARE EOD | Public read, service_role write |
| `psx_signals` | ML signal cache (4h TTL) | Public read, service_role write |
| `psx_portfolios` | User portfolios | Authenticated (own) |
| `psx_holdings` | Holdings within portfolios | Authenticated (via portfolio) |
| `user_watchlist` | User watchlist symbols | Authenticated (own) |
| `price_alerts` | User price alert rules | Authenticated (own) |
| `psx_ticks` | Real-time tick data placeholder | (future) |

Realtime enabled on: `psx_market_snapshot`

---

## REST API Surface (17 endpoints)

| Method | Path | Description | Cached? |
|---|---|---|---|
| GET | `/api/health` | Health check | No |
| GET | `/api/symbols` | Symbol master (symbol, name, sector) | 24h |
| GET | `/api/market/snapshot` | Full market snapshot (495 stocks) | 5s |
| GET | `/api/quote/{symbol}` | Single quote | 5s |
| GET | `/api/quote/{symbol}/history?days=` | Daily OHLCV | 6h |
| GET | `/api/fundamentals/{symbol}` | P/E, EPS, P/B, ROE, div yield | 24h |
| GET | `/api/profile/{symbol}` | Company profile, sector, shares | 7d |
| GET | `/api/announcements?symbol=&limit=` | Corporate announcements | 15min |
| GET | `/api/dividends/{symbol}` | Dividend history | 24h |
| GET | `/api/index/{code}` | Index EOD (KSE100/KSE30/KMI30/ALLSHR) | 1h |
| POST | `/api/indicators/{symbol}` | Compute RSI, MACD, SMA, Bollinger, ATR, etc. | Per-request |
| POST | `/api/screener` | Multi-criteria stock filter | Per-request |
| POST | `/api/backtest` | Backtest simulation | Per-request |
| GET | `/api/sectors` | Sector heatmap aggregates (19+ sectors) | Refresh on TV job |
| GET | `/api/signal/{symbol}` | ML signal prediction | 4h TTL |
| POST | `/api/signals/batch` | Bulk signals for screener | 4h TTL |

---

## Frontend Data Flow (Direct Fetch)

The frontend calls the Python API directly from the browser (no `createServerFn` proxy). CORS is enabled on the API.

```
Browser fetch("http://localhost:8000/api/...")
  → Python FastAPI
    → Supabase cache (read-through)
      → [cache miss] → DPS scraper / TradingView scanner
      → [cache hit]  → return cached data
```

### Real-time (Supabase Realtime)

```
Browser subscribes to: supabase.channel("psx:market")
  .on("postgres_changes", {table: "psx_market_snapshot"})
    → invalidates ["psx","live"] query key
      → usePsxLiveMarket() refetches once
```

### React Query Hooks (`src/hooks/psx/use-psx.ts`)

| Hook | Fetches | staleTime | refetchInterval |
|---|---|---|---|
| `usePsxLiveMarket()` | `/api/market/snapshot` | 5s | 8s |
| `usePsxHistory(sym, days)` | `/api/quote/{sym}/history` | 60min | — |
| `usePsxSymbols()` | `/api/symbols` | 30s | — |
| `usePsxFundamentals(sym)` | `/api/fundamentals/{sym}` | 60s | — |
| `usePsxProfile(sym)` | `/api/profile/{sym}` | 5min | — |
| `usePsxAnnouncements(sym?, limit)` | `/api/announcements` | 60s | — |
| `usePsxDividends(sym)` | `/api/dividends/{sym}` | 5min | — |
| `usePsxIndexData(code)` | `/api/index/{code}` | 60s | — |
| `usePsxSectors()` | `/api/sectors` | 15s | 30s |
| `usePsxSignal(sym)` | `/api/signal/{sym}` | 5min | — |
| `usePsxBatchSignals(limit)` | `/api/signals/batch` | 5min | — |

### Derived Hooks (single-source-of-truth helpers)

| Hook | Purpose |
|---|---|
| `usePsxLiveMarket()` | All 7 UI surfaces share this one cache key `["psx","live"]` |
| `usePsxRealtime()` | Subscribes to Supabase Realtime, patches the same cache |
| `useMarketTickers(limit)` | Top N by volume for ticker strip |
| `useMarketMovers(sort, limit)` | Gainers/Losers/Volume leaders |
| `useIndexCards()` | KSE-100/KSE-30/KMI-30/All-Share aggregates from EOD |

---

## Background Jobs (8 scheduled)

| Job | Interval | Purpose |
|---|---|---|
| `job_refresh_market` | 5s | DPS market-watch → `psx_market_snapshot` (bulk upsert) |
| `job_poll_ahletrade` | 5s | AhleTrade trade tape → `psx_market_snapshot` (live prices) |
| `job_refresh_announcements` | 15min | DPS announcements → `psx_announcements` (bulk) |
| `job_backfill_history` | 02:00 PKT | DPS historical → `psx_ohlcv` (all symbols, bulk) |
| `job_refresh_fundamentals` | Sun 04:00 PKT | DPS company pages → `psx_fundamentals` + `psx_profile` |
| `job_refresh_index_eod` | 01:00 PKT | DPS timeseries EOD → `psx_index_eod` (KSE100/KSE30/KMI30/ALLSHR, bulk) |
| `job_refresh_tv_data` | 5min | TradingView scanner → `psx_profile` (sectors, all 478 stocks, bulk) |
| `job_check_alerts` | 60s | Evaluate `price_alerts` rules, trigger + disable |

---

## ML Signal Engine

**Model:** sklearn GradientBoostingClassifier (5-class: STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
**Features:** 27 (price-derived, trend, momentum, volatility, volume, fundamentals)
**Labeling:** Forward 20-trading-day return (≥+5% → STRONG BUY, +0%..+5% → BUY, -3%..0% → HOLD, -3%..-8% → SELL, ≤-8% → STRONG SELL)
**Validation:** Walk-forward over 3 time folds (not random k-fold)
**Training:** `python scripts/train_signal_model.py` (requires OHLCV backfill first)
**Artifacts:** `app/ml/signal_model.joblib`, `app/ml/scaler.joblib`, `app/ml/feature_list.json`

**Status:** Code complete. Model not yet trained — awaiting OHLCV backfill data.

---

## File Layout (Actual — not planned)

```
.
├── recall/                              # Architecture, plans, decisions
│   ├── project.md                       # This file
│   ├── explaination.md                  # Decision log (39 entries)
│   ├── plan.md                          # Data source documentation
│   └── Complete Project Plan.md         # Master implementation plan
├── .env                                 # Supabase + PSX_API_URL
├── src/
│   ├── router.tsx                       # TanStack Router
│   ├── hooks/
│   │   ├── psx/use-psx.ts              # 15 React Query hooks
│   │   ├── psx/use-watchlist.ts         # Supabase-persisted watchlist
│   │   ├── use-auth.tsx                 # Auth context (bypassed for PSX)
│   │   └── ...
│   ├── lib/
│   │   ├── data.ts                      # Types + dummy fallback data
│   │   ├── psx/types.ts                 # 14 API response interfaces
│   │   ├── psx/client.ts                # Direct fetch functions (18)
│   │   └── ...
│   ├── routes/
│   │   ├── __root.tsx                   # Auth gate (PSX routes bypass)
│   │   ├── psx.tsx                      # PSX terminal (wired to real data)
│   │   ├── stock.$ticker.tsx            # Stock detail (real data + alerts)
│   │   └── ...
│   └── integrations/supabase/
│       ├── client.ts                    # Browser Supabase client
│       ├── types.ts                     # Database types (incl. new tables)
│       └── ...
├── supabase/
│   └── migrations/
│       ├── 20260706120000_psx_module.sql    # 12 PSX tables
│       └── 20260706130000_psx_realtime_and_fix.sql  # Realtime + signals + watchlist + alerts
└── services/psx-api/
    ├── pyproject.toml
    ├── .env
    ├── app/
    │   ├── main.py                      # FastAPI entrypoint
    │   ├── config.py                    # Pydantic settings
    │   ├── api/
    │   │   ├── health.py
    │   │   ├── market.py                # 14 market endpoints
    │   │   └── signals.py               # 2 signal endpoints
    │   ├── models/
    │   │   └── __init__.py              # Pydantic models (14 types)
    │   ├── scrapers/
    │   │   ├── dps.py                   # DPS HTML/JSON scraper
    │   │   ├── ahletrade.py             # AhleTrade HTTP poller
    │   │   └── tradingview.py           # TradingView scanner API
    │   ├── services/
    │   │   ├── cache.py                 # Read-through Supabase cache
    │   │   ├── indicators.py            # Pure numpy indicators (11 types)
    │   │   ├── screener.py              # Multi-criteria screener
    │   │   ├── backtest.py              # Backtest engine
    │   │   └── signal_engine.py         # ML signal prediction
    │   ├── ml/
    │   │   └── features.py              # 27 features for ML model
    │   ├── jobs/
    │   │   └── scheduler.py             # 8 APScheduler jobs
    │   ├── db/
    │       ├── supabase.py              # Supabase service_role client (REST)
    │       ├── sqlalchemy.py            # SQLAlchemy Core async engine (pooler)
    │       └── orm.py                   # Auto-reflected table definitions
    └── scripts/
        └── train_signal_model.py        # ML training (walk-forward GBC)
```

---

## Build & Run

### Python API
```bash
cd services\psx-api
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

### Frontend
```bash
cd .
npm run dev
# → http://localhost:8080/psx
```

### Supabase
Migrations are run via Supabase Dashboard SQL Editor.

### ML Training (when ready)
```bash
cd services\psx-api
python scripts\train_signal_model.py
```

---

## Environment Variables

### Frontend (`.env`)
| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/publishable key |
| `VITE_PSX_API_URL` | Python API URL (`http://localhost:8000` for dev) |

### Python (`services/psx-api/.env`)
| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |
| `DPS_BASE_URL` | `https://dps.psx.com.pk` |
| `AHLETRADE_BASE_URL` | `http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher` |
| `LOG_LEVEL` | `INFO` or `DEBUG` |
| `PORT` | `8000` |
