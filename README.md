<p align="center">
  <br>
  <img src="frontend/packages/web/src/assets/logo.png" alt="NafaIQ" height="84">
  <br>
  <br>
</p>

<h2 align="center">NafaIQ</h2>
<p align="center">
  <b>Smart Trading, Smarter Wealth.</b><br>
  A Pakistan Stock Exchange terminal, AI investment signals, and inflation-aware
  personal finance — in one bilingual, installable Progressive Web App.
</p>

<p align="center">
  <img alt="React" src="https://img.shields.io/badge/React-19-149eca?logo=react&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.x-3178c6?logo=typescript&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776ab?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Supabase" src="https://img.shields.io/badge/Supabase-3ecf8e?logo=supabase&logoColor=white">
  <img alt="PWA" src="https://img.shields.io/badge/PWA-ready-5a0fc8?logo=pwa&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-Proprietary-lightgrey">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Frontend Architecture](#frontend-architecture)
- [Backend Architecture](#backend-architecture)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Available Scripts](#available-scripts)
- [Database & Migrations](#database--migrations)
- [Testing & Quality](#testing--quality)
- [Deployment](#deployment)
- [Development Workflow](#development-workflow)
- [Team](#team)
- [License](#license)

---

## Overview

NafaIQ combines three things most Pakistani investors juggle across separate apps
and spreadsheets into a single terminal:

1. **A market terminal** for the Pakistan Stock Exchange (PSX) — live prices,
   charts, screeners, and heatmaps.
2. **AI signals & guidance** — Signals V2, a machine-learning engine that emits
   tiered buy/hold/sell signals (STRONG BUY ... STRONG SELL) across multiple
   horizons, plus an LLM tutor that answers questions about the market or your own
   portfolio.
3. **Inflation-aware personal finance** — budgets, goals, Zakat, and the flagship
   **Haqeeqi Daulat** engine that shows your *real*, devaluation-adjusted wealth
   rather than a nominal rupee figure.

The web app is a **Progressive Web App** (installable on mobile and desktop),
fully **bilingual** (English + Urdu with RTL support), and ships **light and
dark** themes.

---

## Features

| Area | What it does |
|---|---|
| **Market Terminal** | Live ticker strip, interactive candlestick charts, stock screener, sector heatmap, and top movers for every listed symbol. |
| **AI Trading Signals (Signals V2)** | A model tournament (LightGBM / XGBoost / CatBoost + scikit-learn) over trend, momentum, volatility, and fundamentals emits tiered buy/hold/sell signals per horizon (5D / 20D / 60D), gated by a shadow-mode promotion check so only validated models ever drive production. |
| **Portfolio & Watchlist** | Holdings with live P&L, custom price alerts, and personalized watchlists — persisted and synced across devices. |
| **Haqeeqi Daulat (TM)** | Devaluation-adjusted net-worth engine that surfaces purchasing power, not just a nominal PKR number. |
| **Personal Finance** | Budgets, expense tracking, savings goals, bill reminders, and a Zakat calculator built around PKR realities. |
| **Financial Education** | Urdu-first interactive lessons on stocks, funds, saving, and Islamic finance. |
| **LearnHub AI Studio** | Creates source-grounded PSX lessons, notes, flashcards, practice quizzes, tutor answers, and optional narrated videos from a typed topic or a private text-based PDF. Generated work reuses the native lesson experience and never changes official XP or progress. |
| **AI Financial Tutor** | Contextual, LLM-powered answers about the market, a stock, or your portfolio. |
| **Bilingual & Themed** | Full English/Urdu (RTL) support and light/dark themes across the app. |


## New Data Sources (Workstream D — July 2026)

- **SBP Macro Rates** — KIBOR, FX rates, and policy rate from the State Bank of Pakistan
- **Business Recorder News** — Market news feed
- **PSX Filings** — Company announcements with full-text search (FTS)
- **Unusual Volume Activity** — Volume spike detection (3x 30-day average)
- **5-Year Financials** — Annual and quarterly financial data from financials.psx.com.pk
- **MUFAP Mutual Funds** — Fund catalog and NAV history from the Mutual Funds Association of Pakistan

## Recent Improvements (Workstream E — July 2026)

- **Signals V2 (ML buy/hold/sell)** — Triple-barrier ATR labeling, purged walk-forward CV, probability calibration, and a best-per-horizon model tournament across 5D/20D/60D, running in shadow mode behind a promotion gate (ML never drives production until it beats the technical baseline).
- **Stock Splits** — OHLCV adjustment for historical stock splits (columns: is_adjusted, adjustment_factor, split_date)
- **Shariah Screening** — is_shariah flag on psx_profile derived from PSX Shariah Index constituents
- **PSX Index Expansion** — From 4 to 18 indices tracked (BKTI, OGTI, PSXDIV20, and more)
- **Sector Taxonomy Fix** — TV sectors mapped to DPS taxonomy for consistency
- **Treemap Heatmap** — Google-Finance-style market heatmap by sector
- **Realtime Scope** — Supabase channel filtered to watchlist symbols only
- **Index Freshness** — PSX index cards and charts now reject stale readings and prefer refreshed trading-day data.
- **PSX Market Layout** — Market chart, screener, index cards, and heatmap containers were tuned for desktop, mobile, light theme, and dark theme.
- **Heatmap Expand & Zoom** — Sector heatmap now supports an expanded inspection view with zoom, pan, sector focus, keyboard escape, and accessible controls.
- **Mobile AI Reports** — Mobile app surfaces now consume AI report APIs for dashboard, PSX, finance, portfolio, and stock views, backed by Jest Expo tests.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Web frontend** | React 19, TanStack Start (SSR), TanStack Router & Query, Vite, TailwindCSS, shadcn/ui, Recharts, Framer Motion, Redux Toolkit (demo/client state) |
| **Mobile** | React Native + Expo (shares types & API contracts with the web app) |
| **Backend API** | Python, FastAPI, SQLAlchemy Core, scikit-learn / LightGBM / XGBoost / CatBoost, NumPy, APScheduler |
| **Data & Auth** | Supabase (Postgres, Auth, Row-Level Security, Realtime, PostgREST) |
| **Tooling** | Turborepo, pnpm workspaces, TypeScript, ESLint, Prettier, pytest, Docker |

---

## Architecture

```
  +--------------+          +--------------+
  |   Web PWA    |          |  Mobile App  |
  |  (TanStack   |          |   (React     |
  |  Start/SSR)  |          |   Native)    |
  +------+-------+          +------+-------+
         |                         |
         |    HTTPS (Bearer JWT)   |
         +------------+------------+
                      v
            +--------------------+
            |   FastAPI Backend  |   market data | ML signals | finance
            |      (Python)      |   scheduled scrapers & jobs
            +---------+----------+
                      |
            +---------v----------+
            | Supabase Postgres  |   Auth | RLS | Realtime | PostgREST
            +--------------------+
```

- **Auth** is issued by Supabase; the frontend attaches the user's JWT as a
  Bearer token on API calls, and the backend validates it (RLS-scoped queries).
- **Public market endpoints** (snapshots, indicators) are read without a user
  token; **user data** (portfolio, finance, alerts) is authenticated.
- The web app keeps **server state** in TanStack Query and a small amount of
  **demo/client state** in Redux Toolkit.
- **LearnHub AI Studio** runs pack and media generation on a leased Postgres
  queue. Typed topics retrieve only from the approved LearnHub corpus. Private
  PDFs are validated, stored in a private bucket, extracted into owner-bound
  sources, and removed through a durable cleanup queue when their project is
  deleted. Generated media is served only through short-lived signed URLs.

---

## Repository Structure

A Turborepo + pnpm monorepo:

```
NafaIQ-MainProject/
├── frontend/
│   └── packages/
│       ├── web/          # React 19 PWA — TanStack Start (primary app)
│       ├── mobile/       # React Native + Expo app
│       └── shared/       # Types & API contracts shared with mobile
├── backend/
│   ├── src/app/          # FastAPI application (see Backend Architecture)
│   ├── scripts/          # ML training / data utilities
│   ├── tests/            # pytest suite
│   ├── database/
│   │   └── migrations/   # Supabase SQL migrations
│   ├── Dockerfile
│   ├── pyproject.toml    # Python package + dependencies
│   └── requirements.txt
├── supabase/             # Supabase local config
├── docs/                 # Design specs & documentation
├── turbo.json            # Turborepo task pipeline
├── pnpm-workspace.yaml   # Workspace definition
└── tsconfig.base.json    # Shared TypeScript config
```

---

## Frontend Architecture

The web app (`frontend/packages/web`) uses a **feature-based** structure: route
files stay thin (just the route definition), and each page's implementation lives
in its own feature module.

```
src/
├── routes/            # Thin TanStack route definitions only
├── features/          # One self-contained module per page
│   ├── dashboard/     #   <Page>.tsx + components/ + *.data.ts / *.utils.ts
│   ├── landing/       #   (public marketing page)
│   ├── psx/ finance/ portfolio/ learn/ auth/ alerts/ stock/ signals/
├── components/        # Cross-feature UI
│   ├── layout/        #   app shell, sidebar, header, nav
│   ├── charts/ market/ search/ icons/ shared/ ui/  (shadcn primitives)
├── hooks/             # Shared React hooks (data + client)
├── store/             # Redux Toolkit slices (demo/client state)
├── services/          # Pure calculation layer (mirrors backend logic)
├── integrations/      # Supabase clients (browser + server)
├── lib/               # Utilities: api client, formatters, errors, i18n
└── styles.css         # Design tokens (light/dark) + global styles
```

**Conventions**

- Route files stay thin so the generated route tree never churns on refactors.
- Each feature owns its components, data, and helpers; one component per file.
- UI adapts to **light/dark** via semantic design tokens (never hard-coded theme
  colours) and is **RTL-safe** for Urdu.

---

## Backend Architecture

The FastAPI service (`backend/src/app`) is organized by responsibility:

```
app/
├── api/            # Route handlers (market, signals, finance, alerts, ...)
├── schemas/        # Pydantic request/response models
├── services/       # Business logic (calculations, signal generation)
│   └── signals_v2/ # ML buy/hold/sell engine (tournament, fusion, shadow gate)
├── ml/             # Trained model artifacts & feature pipeline
├── repositories/   # Data access
├── models/         # Domain models
├── db/             # Database connection & session management
├── scrapers/       # PSX market-data collectors
├── jobs/           # Scheduled tasks (APScheduler)
├── middleware/     # Auth (JWT/Bearer), timing, error handling
└── main.py         # App entrypoint, CORS, middleware wiring
```

---

## Getting Started

### Prerequisites

- **Node.js** >= 20 and **pnpm** >= 9
- **Python** >= 3.12
- A **Supabase** project (Postgres + Auth + Realtime)

### 1. Install

```bash
# JavaScript workspace (web, mobile, shared)
pnpm install

# Python backend (editable install with dev extras)
cd backend && pip install -e ".[dev]"
```

### 2. Configure environment

Copy the example files and fill in your own values (see
[Environment Variables](#environment-variables)):

```bash
cp frontend/packages/web/.env.example frontend/packages/web/.env
cp backend/.env.example backend/.env
```

### 3. Run

```bash
# Web PWA      -> http://localhost:8080
pnpm run dev

# Backend API  -> http://localhost:8000  (interactive docs at /docs)
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

To run the web app against a **deployed** backend instead of a local one, point
`VITE_API_URL` at that backend's URL in `frontend/packages/web/.env`.

---

## Environment Variables

Never commit real secrets — `.env` files are git-ignored. The checked-in
`.env.example` files are the source of truth. Variable **names** only:

**`frontend/packages/web/.env`** — all values are browser-safe / public

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Base URL of the FastAPI backend |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable (anon) key |
| `VITE_PSX_API_TOKEN` | Token for public PSX market endpoints |
| `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD` | Credentials for the "Try Demo" account |

> Only publishable/anon keys belong in the frontend. Never place a service-role
> or secret key in a `VITE_*` variable — it ships to the browser.

**`backend/.env`** — server-side secrets, keep private

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Privileged server keys |
| `SUPABASE_DATABASE_*` / `SUPABASE_POOLER_*` | Direct Postgres / pooler connection |
| `PSX_SUPABASE_URL` / `PSX_SUPABASE_SERVICE_ROLE_KEY` | PSX market-data Supabase project |
| `PSX_API_TOKEN` | Token for the PSX data source |
| `EMAIL_DELIVERY_PROVIDER` | Outbound alert email provider (`auto`, `brevo`, `resend`) |
| `BREVO_API_KEY` / `BREVO_FROM_EMAIL` | Preferred no-domain/testing provider for alert email delivery |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | Optional Resend provider settings |
| `SARAFA_API_KEY` | Backend-only Sarafa.pk key for Pakistan gold/silver rates |
| `SARAFA_CITY_SLUG` / `SARAFA_CLIENT_PLATFORM` | Sarafa city/default platform metadata |
| `CORS_ORIGINS` | Comma-separated allowed origins (`*` allows all) |

---

## Available Scripts

Run from the repository root (Turborepo fans out to the workspaces):

| Command | Description |
|---|---|
| `pnpm run dev` | Start the web app (and workspace dev servers) |
| `pnpm run build` | Production build of all packages |
| `pnpm run typecheck` | TypeScript checks across the monorepo |
| `pnpm run lint` | ESLint across the monorepo |
| `pnpm run format` | Prettier write across the repo |

Backend (from `backend/`):

| Command | Description |
|---|---|
| `python -m uvicorn app.main:app --reload --port 8000` | Run the API in dev |
| `pytest -v` | Run the test suite |
| `.\scripts\signals\run_signals_v2_pipeline.ps1 -Mode Lite` | Train/backtest/evaluate Signals V2 (see `backend/docs/signals-v2-handoff.md`) |

---

## Database & Migrations

- Schema and data live in **Supabase Postgres**, secured with **Row-Level
  Security**.
- SQL migrations are versioned in `backend/database/migrations/` and applied via
  the Supabase Dashboard SQL editor (or the Supabase CLI).
- After a schema change, regenerate the frontend's typed database client:

```bash
npx supabase gen types typescript --project-id <your-project-id> --schema public \
  > frontend/packages/web/src/integrations/supabase/types.ts
```

---

## Testing & Quality

```bash
pnpm run typecheck             # TypeScript (all packages)
pnpm run lint                  # ESLint
cd backend && pytest -v        # Python API tests
```

The frontend enforces Prettier formatting and React Hooks lint rules; the backend
is covered by a pytest suite.

---

## Deployment

- **Web app** — a TanStack Start / Nitro build (deployed to a serverless host).
  Set production environment variables (notably `VITE_API_URL`) in the hosting
  provider; local `.env` files are not shipped.
- **Backend on Railway** — deploy two services from the same `backend/` root and
  the same Dockerfile/config:
  - API service: set `PROCESS_ROLE=web`, generate the public Railway domain, and
    set `CORS_ORIGINS` to the web app origin.
  - Scheduler service: set `PROCESS_ROLE=worker`, do not use it as the public API
    URL, and set `API_KEEPALIVE_URL` to the API service's Railway URL after the
    domain is generated.
  Both services need the shared backend secrets (`SUPABASE_*`,
  `PSX_SUPABASE_*`, `SUPABASE_POOLER_*`, AI/email keys as enabled). The scheduler
  is advisory-lock gated, so the split cannot run duplicate jobs.
  The advanced ML libraries (LightGBM/XGBoost/CatBoost) are not in the deployed
  `requirements.txt`; production serves signals from the technical baseline while
  ML runs in shadow mode.
- **Database** — a managed Supabase project.

---

## Development Workflow

- **Branches** — each contributor works on their own branch and opens a pull
  request into the shared integration branch (`dev`); releases are cut from `main`.
- **Commits** — Conventional-Commit-style prefixes:
  `feat(scope):`, `fix(scope):`, `refactor(scope):`, `docs(scope):`, etc.
- **Before opening a PR** — `pnpm run typecheck && pnpm run lint` (and `pytest`
  for backend changes) should pass.

---

## Team

| Focus area | Owner |
|---|---|
| Architecture · ML signals · cross-cutting | Usman |
| Personal finance module | Shakir |
| Mobile app | Tayyab |
| Product & QA | Misbah |

---

## License

© NafaIQ. All rights reserved. Proprietary — built for Pakistani investors.
