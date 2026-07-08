<p align="center">
  <br>
  <img src="frontend/packages/web/src/assets/logo.png" alt="NafaIQ" height="80">
  <br>
  <br>
</p>

<h3 align="center"><b>NafaIQ</b> — Smart Trading, Smarter Wealth</h3>
<p align="center">
  Pakistan Stock Exchange terminal, AI-powered investment signals,<br>
  and inflation-aware personal finance — all in one Progressive Web App.
</p>

---

## Features

### Market Terminal
Live ticker strip, interactive charts, stock screener, sector heatmap, and real-time price tracking for every listed stock.

### AI Trading Signals
Machine learning model analyzes price trends, momentum, volatility, and fundamentals to generate buy/sell/hold signals across the entire market.

### Portfolio & Watchlist
Track your holdings with live P&L, set custom price alerts, and curate personalized watchlists — all persisted and synced across devices.

### Haqeeqi Daulat (True Wealth)
Multi-currency net worth calculator that adjusts for Pakistan's real effective exchange rate, inflation, and gold/silver prices so you see your purchasing power, not just a rupee number.

### Personal Finance
Budgets, expense tracking, savings goals, bill reminders, and Zakat calculator — replace your spreadsheet with tools that understand PKR realities.

### Financial Education
**Urdu-first** interactive lessons covering stocks, mutual funds, saving strategies, and Islamic finance, with bilingual (English/Urdu RTL) support across the entire app.

### AI Financial Tutor
Ask questions about the market, a specific stock, or your own portfolio — get intelligent, contextual answers powered by LLM.

---

## Tech Stack

<table>
  <tr>
    <th>Layer</th>
    <th>Technology</th>
  </tr>
  <tr>
    <td><b>Frontend</b></td>
    <td>React 19, TanStack Start, Vite, TailwindCSS, shadcn/ui, TanStack Query, TanStack Router, Recharts</td>
  </tr>
  <tr>
    <td><b>Backend API</b></td>
    <td>Python FastAPI, scikit-learn, numpy, SQLAlchemy Core, APScheduler</td>
  </tr>
  <tr>
    <td><b>Database</b></td>
    <td>Supabase Postgres (Auth, RLS, Realtime, REST)</td>
  </tr>
  <tr>
    <td><b>Mobile</b></td>
    <td>React Native + Expo (shared types and API with PWA)</td>
  </tr>
  <tr>
    <td><b>Infrastructure</b></td>
    <td>Docker, Turborepo, pnpm workspaces, GitHub Actions</td>
  </tr>
</table>

---

## Project Structure

```
nafaiq-monorepo/
├── frontend/
│   └── packages/
│       ├── web/            # React 19 PWA (TanStack Start)
│       ├── mobile/         # React Native app
│       └── shared/         # Shared API types
├── backend/
│   ├── src/app/            # FastAPI (market data, signals, finance)
│   ├── scripts/            # ML model training
│   ├── tests/              # pytest suite
│   ├── database/migrations/# Supabase SQL migrations
│   ├── Dockerfile
│   └── pyproject.toml
├── docs/                   # ERD, schema guides, route maps
├── turbo.json              # Turborepo pipeline
└── pnpm-workspace.yaml     # Monorepo configuration
```

---

## Getting Started

### Prerequisites
- Node.js ≥ 20, pnpm ≥ 9
- Python ≥ 3.12
- Supabase project (Auth + Postgres + Realtime)

### Install

```bash
pnpm install
cd backend && pip install -e ".[dev]"
```

### Environment

Copy `.env.example` to `.env` in both `frontend/packages/web/` and `backend/`, then fill in your Supabase keys.

### Run

```bash
# Terminal 1 — PWA (http://localhost:8080)
pnpm run dev

# Terminal 2 — API (http://localhost:8000)
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

### Verify

```bash
pnpm run typecheck          # TypeScript
pnpm run lint               # ESLint
cd backend && pytest -v     # Python tests
```

---

## Team

| Person | Focus |
|---|---|
| **Usman** | Architecture, ML signals, cross-cutting |
| **Shakir** | Finance module |
| **Tayyab** | Mobile app |
| **Misbah** | TBD |

---

## License

Built with dedication for Pakistani investors. All rights reserved.
