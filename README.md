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
2. **AI signals & guidance** — a machine-learning model for buy/sell/hold
   signals, plus an LLM tutor that answers questions about the market or your own
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
| **AI Trading Signals** | ML model over price trend, momentum, volatility, and fundamentals generates buy/sell/hold signals across the market. |
| **Portfolio & Watchlist** | Holdings with live P&L, custom price alerts, and personalized watchlists — persisted and synced across devices. |
| **Haqeeqi Daulat™** | Devaluation-adjusted net-worth engine that surfaces purchasing power, not just a nominal PKR number. |
| **Personal Finance** | Budgets, expense tracking, savings goals, bill reminders, and a Zakat calculator built around PKR realities. |
| **Financial Education** | Urdu-first interactive lessons on stocks, funds, saving, and Islamic finance. |
| **AI Financial Tutor** | Contextual, LLM-powered answers about the market, a stock, or your portfolio. |
| **Bilingual & Themed** | Full English/Urdu (RTL) support and light/dark themes across the app. |

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
        ┌──────────────┐          ┌──────────────┐
        │   Web PWA    │          │  Mobile App  │
        │  (TanStack   │          │   (React     │
        │  Start / SSR)│          │   Native)    │
        └──────┬───────┘          └──────┬───────┘
               │                         │
               │   HTTPS (Bearer JWT)    │
               └────────────┬────────────┘
                            ▼
                  ┌────────────────────┐
                  │   FastAPI Backend  │  market data · ML signals · finance
                  │      (Python)      │  scheduled scrapers & jobs
                  └─────────┬──────────┘
                            │
                  ┌─────────▼──────────┐
                  │ Supabase Postgres  │  Auth · RLS · Realtime · PostgREST
                  └────────────────────┘
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
│   ├── psx/  finance/  portfolio/  learn/  auth/  alerts/  stock/
├── components/        # Cross-feature UI
│   ├── layout/        #   app shell, sidebar, header, nav
│   ├── charts/  market/  search/  icons/  shared/  ui/  (shadcn primitives)
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
├── api/            # Route handlers (market, signals, finance, alerts, …)
├── schemas/        # Pydantic request/response models
├── services/       # Business logic (calculations, signal generation)
├── ml/             # Machine-learning model & feature pipeline
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

- **Node.js** ≥ 20 and **pnpm** ≥ 9
- **Python** ≥ 3.12
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
# Web PWA      → http://localhost:8080
pnpm run dev

# Backend API  → http://localhost:8000  (interactive docs at /docs)
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

- **Web app** — a TanStack Start / Nitro build (deployed to a serverless host).
  Set production environment variables (notably `VITE_API_URL`) in the hosting
  provider; local `.env` files are not shipped.
- **Backend API** — containerized via the provided `Dockerfile` and deployed to a
  container host (`railway.json` is included for that platform). Ensure
  `CORS_ORIGINS` allows your web app's origin.
- **Database** — a managed Supabase project.

---

## Development Workflow

- **Branches** — each contributor works on their own branch and opens a pull
  request into the shared integration branch; releases are cut from `main`.
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
