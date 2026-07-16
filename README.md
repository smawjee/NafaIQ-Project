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
  personal finance â€” in one bilingual, installable Progressive Web App.
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

1. **A market terminal** for the Pakistan Stock Exchange (PSX) â€” live prices,
   charts, screeners, and heatmaps.
2. **AI signals & guidance** â€” a machine-learning model for buy/sell/hold
   signals, plus an LLM tutor that answers questions about the market or your own
   portfolio.
3. **Inflation-aware personal finance** â€” budgets, goals, Zakat, and the flagship
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
| **AI Trading Signals** | ML model over price trend, momentum, volatility, and fundamentals generates buy/sell/hold signals across the market. |
| **Portfolio & Watchlist** | Holdings with live P&L, custom price alerts, and personalized watchlists â€” persisted and synced across devices. |
| **Haqeeqi Daulatâ„¢** | Devaluation-adjusted net-worth engine that surfaces purchasing power, not just a nominal PKR number. |
| **Personal Finance** | Budgets, expense tracking, savings goals, bill reminders, and a Zakat calculator built around PKR realities. |
| **Financial Education** | Urdu-first interactive lessons on stocks, funds, saving, and Islamic finance. |
| **AI Financial Tutor** | Contextual, LLM-powered answers about the market, a stock, or your portfolio. |
| **Bilingual & Themed** | Full English/Urdu (RTL) support and light/dark themes across the app. |


## New Data Sources (Workstream D — July 2026)

- **SBP Macro Rates** — KIBOR, FX rates, and policy rate from the State Bank of Pakistan
- **Business Recorder News** — Market news feed
- **PSX Filings** — Company announcements with full-text search (FTS) 
- **Unusual Volume Activity** — Volume spike detection (3× 30-day average)
- **5-Year Financials** — Annual and quarterly financial data from financials.psx.com.pk
- **MUFAP Mutual Funds** — Fund catalog and NAV history from the Mutual Funds Association of Pakistan

## Recent Improvements (Workstream E — July 2026)

- **Stock Splits** — OHLCV adjustment for historical stock splits (columns: is_adjusted, djustment_factor, split_date)
- **Shariah Screening** — is_shariah flag on psx_profile derived from PSX Shariah Index constituents
- **PSX Index Expansion** — From 4 to 18 indices tracked (BKTI, OGTI, PSXDIV20, and more)
- **Sector Taxonomy Fix** — TV sectors mapped to DPS taxonomy for consistency
- **Treemap Heatmap** — Google-Finance-style market heatmap by sector
- **Realtime Scope** — Supabase channel filtered to watchlist symbols only
---

## Tech Stack

| Layer | Technology |
|---|---|
| **Web frontend** | React 19, TanStack Start (SSR), TanStack Router & Query, Vite, TailwindCSS, shadcn/ui, Recharts, Framer Motion, Redux Toolkit (demo/client state) |
| **Mobile** | React Native + Expo (shares types & API contracts with the web app) |
| **Backend API** | Python, FastAPI, SQLAlchemy Core, scikit-learn, NumPy, APScheduler |
| **Data & Auth** | Supabase (Postgres, Auth, Row-Level Security, Realtime, PostgREST) |
| **Tooling** | Turborepo, pnpm workspaces, TypeScript, ESLint, Prettier, pytest, Docker |

---

## Architecture

```
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚   Web PWA    â”‚          â”‚  Mobile App  â”‚
        â”‚  (TanStack   â”‚          â”‚   (React     â”‚
        â”‚  Start / SSR)â”‚          â”‚   Native)    â”‚
        â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜          â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚                         â”‚
               â”‚   HTTPS (Bearer JWT)    â”‚
               â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                            â–¼
                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                  â”‚   FastAPI Backend  â”‚  market data Â· ML signals Â· finance
                  â”‚      (Python)      â”‚  scheduled scrapers & jobs
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                            â”‚
                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                  â”‚ Supabase Postgres  â”‚  Auth Â· RLS Â· Realtime Â· PostgREST
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

- **Auth** is issued by Supabase; the frontend attaches the user's JWT as a
  Bearer token on API calls, and the backend validates it (RLS-scoped queries).
- **Public market endpoints** (snapshots, indicators) are read without a user
  token; **user data** (portfolio, finance, alerts) is authenticated.
- The web app keeps **server state** in TanStack Query and a small amount of
  **demo/client state** in Redux Toolkit.

---

## Repository Structure

A Turborepo + pnpm monorepo:

```
NafaIQ-MainProject/
â”œâ”€â”€ frontend/
â”‚   â””â”€â”€ packages/
â”‚       â”œâ”€â”€ web/          # React 19 PWA â€” TanStack Start (primary app)
â”‚       â”œâ”€â”€ mobile/       # React Native + Expo app
â”‚       â””â”€â”€ shared/       # Types & API contracts shared with mobile
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ src/app/          # FastAPI application (see Backend Architecture)
â”‚   â”œâ”€â”€ scripts/          # ML training / data utilities
â”‚   â”œâ”€â”€ tests/            # pytest suite
â”‚   â”œâ”€â”€ database/
â”‚   â”‚   â””â”€â”€ migrations/   # Supabase SQL migrations
â”‚   â”œâ”€â”€ Dockerfile
â”‚   â”œâ”€â”€ pyproject.toml    # Python package + dependencies
â”‚   â””â”€â”€ requirements.txt
â”œâ”€â”€ supabase/             # Supabase local config
â”œâ”€â”€ docs/                 # Design specs & documentation
â”œâ”€â”€ turbo.json            # Turborepo task pipeline
â”œâ”€â”€ pnpm-workspace.yaml   # Workspace definition
â””â”€â”€ tsconfig.base.json    # Shared TypeScript config
```

---

## Frontend Architecture

The web app (`frontend/packages/web`) uses a **feature-based** structure: route
files stay thin (just the route definition), and each page's implementation lives
in its own feature module.

```
src/
â”œâ”€â”€ routes/            # Thin TanStack route definitions only
â”œâ”€â”€ features/          # One self-contained module per page
â”‚   â”œâ”€â”€ dashboard/     #   <Page>.tsx + components/ + *.data.ts / *.utils.ts
â”‚   â”œâ”€â”€ landing/       #   (public marketing page)
â”‚   â”œâ”€â”€ psx/  finance/  portfolio/  learn/  auth/  alerts/  stock/
â”œâ”€â”€ components/        # Cross-feature UI
â”‚   â”œâ”€â”€ layout/        #   app shell, sidebar, header, nav
â”‚   â”œâ”€â”€ charts/  market/  search/  icons/  shared/  ui/  (shadcn primitives)
â”œâ”€â”€ hooks/             # Shared React hooks (data + client)
â”œâ”€â”€ store/             # Redux Toolkit slices (demo/client state)
â”œâ”€â”€ services/          # Pure calculation layer (mirrors backend logic)
â”œâ”€â”€ integrations/      # Supabase clients (browser + server)
â”œâ”€â”€ lib/               # Utilities: api client, formatters, errors, i18n
â””â”€â”€ styles.css         # Design tokens (light/dark) + global styles
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
â”œâ”€â”€ api/            # Route handlers (market, signals, finance, alerts, â€¦)
â”œâ”€â”€ schemas/        # Pydantic request/response models
â”œâ”€â”€ services/       # Business logic (calculations, signal generation)
â”œâ”€â”€ ml/             # Machine-learning model & feature pipeline
â”œâ”€â”€ repositories/   # Data access
â”œâ”€â”€ models/         # Domain models
â”œâ”€â”€ db/             # Database connection & session management
â”œâ”€â”€ scrapers/       # PSX market-data collectors
â”œâ”€â”€ jobs/           # Scheduled tasks (APScheduler)
â”œâ”€â”€ middleware/     # Auth (JWT/Bearer), timing, error handling
â””â”€â”€ main.py         # App entrypoint, CORS, middleware wiring
```

---

## Getting Started

### Prerequisites

- **Node.js** â‰¥ 20 and **pnpm** â‰¥ 9
- **Python** â‰¥ 3.12
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
# Web PWA      â†’ http://localhost:8080
pnpm run dev

# Backend API  â†’ http://localhost:8000  (interactive docs at /docs)
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

To run the web app against a **deployed** backend instead of a local one, point
`VITE_API_URL` at that backend's URL in `frontend/packages/web/.env`.

---

## Environment Variables

Never commit real secrets â€” `.env` files are git-ignored. The checked-in
`.env.example` files are the source of truth. Variable **names** only:

**`frontend/packages/web/.env`** â€” all values are browser-safe / public

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Base URL of the FastAPI backend |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable (anon) key |
| `VITE_PSX_API_TOKEN` | Token for public PSX market endpoints |
| `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD` | Credentials for the "Try Demo" account |

> Only publishable/anon keys belong in the frontend. Never place a service-role
> or secret key in a `VITE_*` variable â€” it ships to the browser.

**`backend/.env`** â€” server-side secrets, keep private

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Privileged server keys |
| `SUPABASE_DATABASE_*` / `SUPABASE_POOLER_*` | Direct Postgres / pooler connection |
| `PSX_API_TOKEN` | Token for the PSX data source |
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

- **Web app** â€” a TanStack Start / Nitro build (deployed to a serverless host).
  Set production environment variables (notably `VITE_API_URL`) in the hosting
  provider; local `.env` files are not shipped.
- **Backend API** â€” containerized via the provided `Dockerfile` and deployed to a
  container host (`railway.json` is included for that platform). Ensure
  `CORS_ORIGINS` allows your web app's origin.
- **Database** â€” a managed Supabase project.

---

## Development Workflow

- **Branches** â€” each contributor works on their own branch and opens a pull
  request into the shared integration branch; releases are cut from `main`.
- **Commits** â€” Conventional-Commit-style prefixes:
  `feat(scope):`, `fix(scope):`, `refactor(scope):`, `docs(scope):`, etc.
- **Before opening a PR** â€” `pnpm run typecheck && pnpm run lint` (and `pytest`
  for backend changes) should pass.

---

## Team

| Focus area | Owner |
|---|---|
| Architecture Â· ML signals Â· cross-cutting | Usman |
| Personal finance module | Shakir |
| Mobile app | Tayyab |
| Product & QA | Misbah |

---

## License

Â© NafaIQ(PK). All rights reserved. Proprietary â€” built for Pakistani investors.


