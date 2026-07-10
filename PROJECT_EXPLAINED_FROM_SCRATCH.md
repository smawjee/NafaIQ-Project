# NafaIQ — The Complete Project Explanation (From Scratch)

> **Read this if you know *nothing* about the project and have a presentation tomorrow.**
> It explains every big word, every folder, every file, the full request journey, the database,
> migrations, scraping, ORM, HTTP status codes, and how to do things by hand.
> Take your time — each section builds on the previous one.

---

## Table of Contents

1. [What is NafaIQ, in one paragraph](#1-what-is-nafaiq-in-one-paragraph)
2. [The 30,000-foot view (the whole system on one page)](#2-the-30000-foot-view)
3. [The architecture pattern we chose — and why (and why not the others)](#3-the-architecture-pattern-we-chose)
4. [Why FastAPI and not Flask / Django / Node](#4-why-fastapi-and-not-flask--django--node)
5. ["What is the *controller* in your project?"](#5-what-is-the-controller-in-your-project)
6. [The full project tree, explained folder-by-folder](#6-the-full-project-tree-explained)
7. [The backend explained layer-by-layer, file-by-file](#7-the-backend-explained-layer-by-layer)
8. [The life of a request (read flow + write/CRUD flow), step by step](#8-the-life-of-a-request)
9. [ORM — what, where, why, how (and why SQLAlchemy)](#9-orm--what-where-why-how)
10. [The database — what is stored, and where](#10-the-database--what-is-stored-and-where)
11. [Migrations — what they are and how we run them](#11-migrations)
12. [How we fetch / scrape the data, and where it goes](#12-how-we-fetchscrape-data)
13. [Authentication — the two-tier security model](#13-authentication)
14. [Doing CRUD manually (by hand)](#14-doing-crud-manually)
15. [HTTP status codes — 2xx, 3xx, 4xx, 5xx explained](#15-http-status-codes)
16. [Background jobs (the scheduler)](#16-background-jobs)
17. [How to run the whole thing locally](#17-how-to-run-it)
18. [A glossary of every technical term](#18-glossary)
19. [Likely questions and confident answers](#19-likely-questions--answers)

---

## 1. What is NafaIQ, in one paragraph

**NafaIQ** is a **Pakistan Stock Exchange (PSX) trading terminal + personal-finance manager**, delivered as a **web app** (a PWA — a website that installs and behaves like a phone app). It shows **live PSX stock prices**, **AI trading signals** (buy/sell/hold), a **portfolio & watchlist tracker**, a **budgeting/expenses module**, a **Zakat calculator**, an **inflation-aware "real wealth" calculator (Haqeeqi Daulat)**, and an **AI financial tutor** — with full **English/Urdu** support.

It is built as **two separate programs that talk over the internet**:

- A **frontend** (what the user sees — the website) written in **React / TypeScript**.
- A **backend** (the brain — data, rules, security) written in **Python with FastAPI**.
- A shared **database** hosted on **Supabase** (managed PostgreSQL).

---

## 2. The 30,000-foot view

```
   ┌──────────────┐        HTTPS (JSON)        ┌────────────────────────┐
   │   BROWSER     │  ───────────────────────▶ │   PYTHON BACKEND        │
   │  (React PWA)  │  ◀─────────────────────── │   (FastAPI API)         │
   └──────┬───────┘        JSON responses       └───────┬──────┬────────┘
          │                                              │      │
          │  Supabase Auth (login)                       │      │ scrapes every few seconds
          │  Supabase Realtime (live push)               │      ▼
          ▼                                              │  ┌─────────────────────┐
   ┌──────────────┐                                      │  │  DATA SOURCES         │
   │   SUPABASE    │ ◀──────────────────────────────────┘  │  • DPS (psx.com.pk)   │
   │  PostgreSQL   │      backend reads & writes tables      │  • TradingView scanner│
   │  + Auth + RLS │                                         │  • AhleTrade feed     │
   └──────────────┘                                         └─────────────────────┘
```

**In plain English:**
1. The **browser** shows the UI and asks the **Python backend** for data (e.g. "give me the market snapshot").
2. The **Python backend** doesn't scrape the PSX website *on every request* (too slow). Instead, **background jobs** scrape PSX data sources every few seconds/minutes and **save it into the database**. When the browser asks, the backend just **reads the fresh copy from the database** and returns it. This is called a **cache** (a saved copy you serve instead of re-computing).
3. The **database** (Supabase Postgres) stores everything: cached market data *and* user data (portfolios, watchlists, budgets, alerts).
4. **Login** is handled by **Supabase Auth** directly from the browser. The backend only *verifies* the resulting login token.

There are **three repos-in-one** (a *monorepo*): `frontend/`, `backend/`, and docs. We'll focus mostly on the **backend**, because that's where the architecture questions (controllers, ORM, FastAPI, migrations) live.

---

## 3. The architecture pattern we chose

### The short answer to say out loud
> "The backend uses a **Layered Architecture** — specifically the **Controller → Service → Repository** pattern. Each layer has exactly one job, and a layer only talks to the layer directly below it. It's the server-side cousin of MVC, adapted for an API that returns JSON instead of HTML pages."

### The layers (top to bottom)

```
        HTTP request  (e.g. POST /api/portfolio/create)
             │
             ▼
   ┌───────────────────────────────────────────────┐
   │  1. CONTROLLER  (folder: api/)                  │  "the receptionist"
   │     - receives the HTTP request                 │
   │     - checks who you are (auth)                 │
   │     - hands the work to a service               │
   │     - returns the JSON response                 │
   └───────────────────────────────────────────────┘
             │
             ▼
   ┌───────────────────────────────────────────────┐
   │  2. SCHEMA  (folder: schemas/)                  │  "the form validator"
   │     - defines the SHAPE of valid input/output   │
   │     - rejects bad data automatically (422)      │
   └───────────────────────────────────────────────┘
             │
             ▼
   ┌───────────────────────────────────────────────┐
   │  3. SERVICE  (folder: services/)                │  "the manager / brain"
   │     - the BUSINESS RULES live here              │
   │       (e.g. 'Free plan max 3 portfolios',       │
   │        'you can only edit your own holding')    │
   │     - orchestrates one or more repositories     │
   └───────────────────────────────────────────────┘
             │
             ▼
   ┌───────────────────────────────────────────────┐
   │  4. REPOSITORY  (folder: repositories/)         │  "the librarian"
   │     - the ONLY layer that writes SQL            │
   │     - reads/writes rows in the database         │
   │     - knows nothing about HTTP or business rules │
   └───────────────────────────────────────────────┘
             │
             ▼
   ┌───────────────────────────────────────────────┐
   │  5. DATABASE  (Supabase PostgreSQL)             │  "the filing cabinet"
   └───────────────────────────────────────────────┘
```

**Real example from our code** — creating a portfolio:

| Layer | File | What it does |
|---|---|---|
| Controller | `api/portfolio.py` → `create_portfolio()` | Receives `POST /api/portfolio/create`, gets the logged-in `user`, calls the service |
| Schema | `schemas/portfolio.py` → `PortfolioCreate` | Guarantees the body has a `name` between 1 and 100 characters |
| Service | `services/portfolio/holdings.py` → `create_portfolio()` | Enforces the rule *"Free users get max 3 portfolios"* then asks the repo to insert |
| Repository | `repositories/portfolio/portfolios.py` → `insert_portfolio()` | Runs the actual `INSERT INTO psx_portfolios ...` SQL |
| Database | table `psx_portfolios` | Stores the new row |

### Why this pattern?

- **Separation of concerns** — each layer has *one reason to change*. If the database changes, only the repository changes. If a business rule changes, only the service changes. The controller (HTTP) barely ever changes.
- **Testability** — you can test the service's business logic without spinning up a real web server.
- **Team-friendly** — one person can work on `services/finance/` while another works on `services/portfolio/` without colliding.
- **Readable** — a controller file is a clean list of endpoints; you can see the whole API surface at a glance.

### Why not the alternatives? (say this if asked "why not MVC?")

| Pattern | What it is | Why we didn't use it as-is |
|---|---|---|
| **Classic MVC** (Model-View-Controller) | Controller + Model + an HTML **View** rendered on the server | We have **no server-rendered View** — our "view" is a separate React app. So the "V" of MVC lives entirely in the frontend. On the backend we kept Controller, and split "Model" into the cleaner **Service + Repository** pair. |
| **MVT** (Django's Model-View-Template) | Same idea, Django's naming | Django is a heavyweight, opinionated *full-stack* framework. We only needed a JSON API, not templates/admin/forms. |
| **Fat models / Active Record** | Business logic lives *inside* the database model objects | Mixes business rules with data access — hard to test, and it couples everything to the ORM. Our Service/Repository split keeps them apart. |
| **Everything-in-one-file** | All logic dumped in the route function | Fine for a 100-line toy; a nightmare for a 20-table product with 5 developers. |

> **One-liner for the panel:** *"We use a layered Controller–Service–Repository architecture. It's MVC without the server-side View, because our View is the React frontend. This gives us clean separation, easy testing, and lets the team work in parallel."*

---

## 4. Why FastAPI and not Flask / Django / Node

**FastAPI** is a modern Python framework for building web **APIs** (an API = a set of URLs that return data, usually JSON, instead of web pages).

### Why FastAPI

1. **It's `async` (asynchronous) by default.** Our backend spends most of its time *waiting* — waiting on the PSX website, waiting on the database. Async lets one worker handle hundreds of these "waits" at once instead of blocking. For a scraping + data API, this is a huge win.
2. **Automatic validation with Pydantic.** You declare the shape of your data once (a `schema`), and FastAPI automatically rejects malformed requests with a clear `422` error — no manual `if` checks.
3. **Free, automatic API documentation.** Visit `http://localhost:8000/docs` and you get an interactive, clickable page listing every endpoint (this is **Swagger UI / OpenAPI**). Great for demos and for the frontend team.
4. **Type hints = fewer bugs.** You write normal Python type hints (`symbol: str`, `days: int`) and FastAPI uses them for parsing, validation, and docs all at once.
5. **Fast.** It's one of the fastest Python frameworks (built on Starlette + Uvicorn), comparable to Node.js.

### Why not the others

| Option | Why not |
|---|---|
| **Flask** | Great and simple, but **synchronous by default**, has **no built-in validation** or auto-docs. You'd bolt on 4–5 extra libraries to get what FastAPI gives you out of the box. |
| **Django / DRF** | Very powerful but **heavy and opinionated** — it wants to own your database models, admin, templates, migrations. We already use **Supabase** for the DB and auth, so most of Django would sit unused. |
| **Node.js / Express** | A fine choice, but our **data/ML work is in Python** (scikit-learn for signals, pandas/numpy for indicators, BeautifulSoup for scraping). Keeping the backend in Python means the ML model, the scrapers, and the API all share one language. |

> **One-liner:** *"FastAPI because our workload is I/O-heavy scraping — async is a natural fit — and because our ML and data-science stack is Python. We also get automatic validation and interactive docs for free."*

---

## 5. "What is the controller in your project?"

A **controller** is the code that **directly handles an incoming HTTP request** and produces the response. It's the *front door* of the backend.

In our project, **controllers live in `backend/src/app/api/`**. In FastAPI language, a controller is a function decorated with `@router.get(...)`, `@router.post(...)`, etc. These functions are also called **route handlers** or **endpoints**.

**A controller should be "thin"** — it does almost no thinking. Look at this real controller:

```python
# backend/src/app/api/portfolio.py
@router.post("/portfolio/create")
async def create_portfolio(
    body: PortfolioCreate,                          # ← validated input (schema)
    user: Annotated[dict, Depends(require_user)],   # ← who is logged in (auth)
):
    return await portfolio_service.create_portfolio(user, body.name)  # ← hand off to service
```

That's the *entire* controller. Its only jobs:
1. Define the URL and HTTP method (`POST /portfolio/create`).
2. Declare what valid input looks like (`body: PortfolioCreate`).
3. Require a logged-in user (`Depends(require_user)`).
4. **Delegate** the real work to the **service** and return the result as JSON.

All the actual decision-making ("is this user allowed 3 portfolios or 10?") lives one layer down, in the **service**. That's deliberate — it keeps controllers boring, short, and easy to read. Our `main.py` **registers** all these controllers with the app via `app.include_router(...)`.

> **One-liner:** *"Our controllers are the FastAPI route handlers in the `api/` folder. They're intentionally thin — parse input, check auth, delegate to a service, return JSON. No business logic lives in a controller."*

---

## 6. The full project tree, explained

Top level (the **monorepo** — several projects in one repository):

```
NafaIQ-MainProject/
├── frontend/                # The website the user sees (React + TypeScript)
│   └── packages/
│       ├── web/             # The main PWA (browser app)
│       ├── mobile/          # React Native mobile app (shares the same backend)
│       └── shared/          # Types/utils shared between web and mobile
├── backend/                 # The brain — Python FastAPI API  ★ our focus
│   ├── src/app/             # All the backend source code
│   ├── tests/               # Automated tests (pytest)
│   ├── database/migrations/ # SQL files that define/evolve the database
│   ├── scripts/             # One-off scripts (e.g. train the ML model)
│   ├── pyproject.toml       # Python dependency list + project config
│   └── Dockerfile           # Recipe to package the backend into a container
├── docs/                    # Diagrams, ERDs, route maps
├── recall/                  # Internal design notes & decision log (very useful!)
├── supabase/                # Supabase project config
├── package.json             # Root JS config (Turborepo/pnpm workspace)
├── turbo.json               # Turborepo build pipeline
├── pnpm-workspace.yaml      # Declares the workspace packages
└── README.md
```

**Why a monorepo?** So the web app, the mobile app, and the backend all live and version together in one place, and can share code (like TypeScript types). We manage it with **pnpm workspaces** + **Turborepo** (tools that build/run all the sub-projects together).

---

## 7. The backend explained, layer-by-layer

This is the heart of what a presenter should know. Path: `backend/src/app/`.

```
backend/src/app/
├── main.py            ← THE ENTRY POINT. Creates the app, wires everything, starts jobs.
├── config.py          ← Reads settings/secrets from the .env file (keys, DB password, URLs).
│
├── api/               ← ① CONTROLLERS (the URLs / endpoints)
│   ├── health.py          "/api/health" — is the server alive?
│   ├── market.py          public market data (snapshot, quote, history, symbols...)
│   ├── market_v2.py       newer market endpoints
│   ├── signals.py         AI buy/sell/hold signal endpoints
│   ├── portfolio.py       user portfolios & holdings (CRUD)
│   ├── portfolio_extended.py  transactions, allocation, extra portfolio features
│   ├── watchlist  (in portfolio.py)  the user's saved symbols
│   ├── finance.py         budgets/expenses/goals/bills
│   ├── finance_extended.py more finance endpoints
│   ├── finance_sync.py    bulk push/pull of finance data
│   ├── alerts.py          price/bill/budget/goal alert rules (CRUD)
│   ├── notifications.py    the user's in-app notification inbox
│   ├── profile.py         user profile & plan
│   └── deps.py            SHARED dependencies — most importantly require_user (auth guard)
│
├── schemas/           ← ② INPUT/OUTPUT SHAPES (Pydantic models = "the forms")
│   ├── portfolio.py       PortfolioCreate, HoldingCreate, NetworthResponse, ...
│   ├── finance.py, alerts.py, market.py, notifications.py, profile.py, zakat.py
│
├── services/          ← ③ BUSINESS LOGIC (the rules & orchestration)
│   ├── portfolio/         holdings.py, trades.py, networth.py, watchlist.py
│   ├── finance/           budgets.py, transactions.py, goals.py, bills.py, summary.py, zakat.py
│   ├── alerts/            evaluator.py, price_alerts.py, app_alerts.py, events.py
│   ├── market/            quotes.py, history.py, screener.py, heatmap.py, signals.py, indicators.py
│   ├── psx/               dps.py, tradingview.py, prices.py, benchmark.py, sector_map.py
│   ├── auth.py            verifies the Supabase login token (JWT)  ★ security
│   ├── users.py           looks up a user's plan (Free/Pro) & feature limits
│   ├── permissions.py     enforces plan limits (e.g. max_portfolios)
│   ├── cache.py           read-through cache logic for market data
│   ├── signal_engine.py   loads the ML model and predicts a signal
│   ├── indicators.py      RSI, MACD, moving averages, Bollinger, ATR (pure math)
│   ├── screener.py, backtest.py, calculations.py, symbols.py
│   ├── notifications.py   builds & stores in-app notifications
│   └── notifier.py        actually delivers notifications (e.g. email via Resend)
│
├── repositories/      ← ④ DATA ACCESS (the ONLY place raw SQL lives)
│   ├── base.py            connect() / begin() — open a DB connection or a transaction
│   ├── portfolio/         portfolios.py, holdings.py, trades.py, valuation.py, watchlist.py
│   ├── finance/           budgets.py, transactions.py, goals.py, bills.py, settings.py, summary.py
│   ├── alerts/            price_alerts.py, app_alerts.py, evaluator.py, events.py
│   ├── market/            metrics.py, reference.py
│   ├── notifications_repo.py, signals_repo.py, user_repo.py, zakat_repo.py, health_repo.py
│
├── db/                ← ⑤ DATABASE PLUMBING (how we connect)
│   ├── sqlalchemy.py      builds the async engine + session factory (connection pool)
│   ├── orm.py             auto-reflects table definitions from the live DB
│   ├── supabase.py        the Supabase REST client (used by scraper jobs to write)
│   └── models/            typed table blueprints (market, portfolio, finance, alerts, ...)
│
├── scrapers/          ← WHERE EXTERNAL DATA COMES FROM
│   ├── dps.py             scrapes dps.psx.com.pk (HTML tables + some JSON)
│   ├── tradingview.py     TradingView scanner JSON API (sectors, market caps)
│   └── ahletrade.py       AhleTrade real-time trade feed (pipe-delimited text)
│
├── jobs/              ← SCHEDULED BACKGROUND WORK
│   ├── scheduler.py       APScheduler: 8 jobs (refresh market every 5s, check alerts every 60s...)
│   └── alert_evaluator.py alert-checking helper
│
├── middleware/        ← CODE THAT RUNS ON EVERY REQUEST, BEFORE THE CONTROLLER
│   ├── auth.py            BearerTokenMiddleware — gatekeeper for public vs user routes
│   └── rate_limit.py      slowapi — stops abuse (e.g. max 60 requests/minute)
│
├── ml/                ← MACHINE LEARNING
│   └── features.py        turns raw prices into 27 numeric features for the model
│
└── models/            ← Pydantic data classes used by scrapers (MarketSnapshotItem, OHLCVBar, ...)
```

### The golden rule of the layers
**Data flows *down* and back *up*, and each layer only knows the layer directly below it:**

```
api/  →  schemas/  →  services/  →  repositories/  →  db/  →  PostgreSQL
(HTTP)   (validate)   (rules)       (SQL)            (connect)
```

A controller **never** writes SQL. A repository **never** knows about HTTP or users' plans. This discipline is what keeps a 100-file backend understandable.

---

## 8. The life of a request

### 8a. A READ request (public market data)
**Scenario:** the browser wants the live market snapshot.

```
GET /api/market/snapshot     (with header: Authorization: Bearer <API_TOKEN>)
   │
   1. MIDDLEWARE (middleware/auth.py)
   │     → Is this a public API route? Yes → check the shared API token. Valid → continue.
   │
   2. RATE LIMIT (middleware/rate_limit.py)
   │     → Under 60 requests/minute? Yes → continue.  (else 429 Too Many Requests)
   │
   3. CONTROLLER (api/market.py → market_snapshot)
   │     → calls market_service.market_snapshot()
   │
   4. SERVICE (services/market/…)
   │     → asks the repository for the latest cached rows
   │
   5. REPOSITORY (repositories/market/…)
   │     → SELECT * FROM psx_market_snapshot  (via SQLAlchemy)
   │
   6. DATABASE returns ~500 rows → repo → service → controller
   │
   7. FastAPI serializes to JSON, GZip middleware compresses it, sends 200 OK.
```

Key idea: **the backend serves a saved copy from the database**, not a live scrape. The scraping happens separately in the background (section 16). This is why the app feels instant.

### 8b. A WRITE / CRUD request (user data)
**Scenario:** a logged-in user creates a portfolio.

```
POST /api/portfolio/create     Body: {"name": "My Halal Picks"}
                               Header: Authorization: Bearer <SUPABASE_JWT>
   │
   1. MIDDLEWARE (auth.py)
   │     → path starts with /api/portfolio → this is a USER route.
   │       Middleware lets it pass; the real check is the require_user dependency.
   │
   2. CONTROLLER (api/portfolio.py → create_portfolio)
   │     → Depends(require_user) runs FIRST:
   │         • reads the "Authorization: Bearer <JWT>" header
   │         • verifies the token's signature against Supabase's public keys (services/auth.py)
   │         • returns {user_id, email, plan, features}   (else → 401 Unauthorized)
   │     → body is validated against PortfolioCreate schema (else → 422)
   │
   3. SERVICE (services/portfolio/holdings.py → create_portfolio)
   │     → opens a DB transaction (begin())
   │     → counts the user's existing portfolios (repo)
   │     → enforces plan limit: Free = 3 max  (check_count_limit)  (else → 403 Forbidden)
   │     → asks the repo to insert
   │
   4. REPOSITORY (repositories/portfolio/portfolios.py → insert_portfolio)
   │     → INSERT INTO psx_portfolios (user_id, name) VALUES (...) RETURNING *
   │
   5. Transaction COMMITS. New row returned up the chain.
   │
   6. Response: 200 OK  { "id": 42, "name": "My Halal Picks", ... }
```

**This is the CRUD pattern.** The same 4-layer journey happens for:
- **C**reate → `POST` → `INSERT`
- **R**ead → `GET` → `SELECT`
- **U**pdate → `PATCH`/`PUT` → `UPDATE`
- **D**elete → `DELETE` → `DELETE`

Look at `api/portfolio.py` and you'll literally see one function per CRUD operation on holdings (`add_holding` = POST/insert, `list_holdings` = GET/select, `update_holding` = PATCH/update, `delete_holding` = DELETE/delete).

---

## 9. ORM — what, where, why, how

### What is an ORM?
**ORM = Object-Relational Mapping.** A database speaks **SQL** and stores **rows in tables**. Your program speaks **objects and functions**. An ORM is a **translator** between the two, so you can work with the database using your programming language instead of hand-writing SQL strings everywhere, and so the library handles connections, escaping, and safety for you.

- **Relational** = the database (PostgreSQL: tables, rows, columns).
- **Object** = your Python code (functions, dicts, objects).
- **Mapping** = the bridge between them.

### Which ORM — and why SQLAlchemy?
We use **SQLAlchemy 2.0** (the standard, most powerful Python database toolkit), with the **async** driver **asyncpg** (so database calls don't block our async server).

Why SQLAlchemy:
1. **Industry standard** for Python — battle-tested, huge community, works with any SQL database.
2. **Async support** — matches our async FastAPI backend, so a slow query doesn't freeze the server.
3. **Two modes in one library:** you can use the high-level ORM *or* drop down to hand-written SQL when you want full control. We use **SQLAlchemy Core** — meaning we write our SQL but let SQLAlchemy handle **connection pooling, parameter binding (SQL-injection safety), and async execution**.
4. **Safety** — we pass values as **named parameters** (`:pid`, `:sym`), never string-concatenation. SQLAlchemy substitutes them safely, which **prevents SQL injection**.

### How it works in our code (this is the clever part)

**We don't hand-write table definitions.** At startup, we **reflect** the schema — SQLAlchemy connects to the live database and *reads* what tables and columns exist, automatically:

```python
# db/orm.py — reflection = "read the real DB and learn its shape"
metadata.reflect(bind=sync_conn, schema="public")   # discovers every table/column
```

So the code always matches the *real* database — no manual table classes to keep in sync.

**The connection engine** (a reusable pool of DB connections) is built in `db/sqlalchemy.py`, pointing at Supabase's **transaction pooler** (an IPv4-reachable, connection-efficient front door to Postgres):

```python
postgresql+asyncpg://<user>:<password>@<pooler-host>:6543/postgres
```

**Repositories run the actual queries.** Example (real code, `repositories/portfolio/holdings.py`):

```python
result = await conn.execute(
    text("SELECT id, symbol, shares, avg_cost FROM psx_holdings WHERE portfolio_id = :pid"),
    {"pid": portfolio_id},          # ← safe, parameterized — no SQL injection
)
return [dict(r) for r in result.mappings().all()]
```

The `text(...)` + params style is **SQLAlchemy Core with raw SQL**. We get the safety and async of the ORM, while keeping our SQL explicit and readable.

### Two ways we talk to the database (important nuance)
Our backend actually has **two** database access paths, on purpose:

| Path | Library | Used by | Why |
|---|---|---|---|
| **SQLAlchemy + asyncpg** (direct Postgres) | `db/sqlalchemy.py`, all `repositories/` | **User-facing API** (portfolios, finance, alerts) | Full SQL power, transactions, joins, async |
| **Supabase REST client** | `db/supabase.py` (`get_supabase()`) | **Scraper jobs** (`jobs/scheduler.py`) | Simple bulk `upsert` of scraped rows; uses the service key that **bypasses RLS** |

> **One-liner:** *"We use SQLAlchemy Core with the async asyncpg driver. We auto-reflect the schema from the live database so our code never drifts from reality, and every query is parameterized to prevent SQL injection. Repositories are the only layer allowed to touch SQL."*

---

## 10. The database — what is stored, and where

Everything lives in **one Supabase PostgreSQL database** (project ref `gmonfgxmjgzipnbhgimv`). Supabase is "Postgres + batteries" — it gives us the database **plus** authentication, row-level security, and realtime push, all managed for us.

The tables fall into **two families:**

### A) Cached PSX market data (public, read-only to users; written by background jobs)
| Table | What's in it |
|---|---|
| `psx_market_snapshot` | Live price/change/volume for ~500 stocks (refreshed every 5s) |
| `psx_ohlcv` | Daily Open/High/Low/Close/Volume history per stock |
| `psx_fundamentals` | P/E, EPS, P/B, ROE, dividend yield per stock |
| `psx_profile` | Company name, sector, share counts, logo |
| `psx_announcements` | Corporate announcements |
| `psx_dividends` / payouts | Dividend & bonus history |
| `psx_index_eod` | KSE-100 / KSE-30 / KMI-30 / ALL-SHARE index closing values |
| `psx_signals` | Cached AI buy/sell/hold predictions (refreshed every ~4h) |

### B) User data (private — each user sees only their own rows)
| Table | What's in it |
|---|---|
| `psx_portfolios` | A user's portfolios |
| `psx_holdings` | Stocks inside each portfolio (shares, average cost) |
| `stock_transactions` | Buy/sell transaction history |
| `user_watchlist` | Symbols a user is watching |
| `price_alerts` | "Tell me when HBL crosses 120" rules |
| `user_alerts` | Bill/budget/goal/stock alert rules |
| `alert_events` | A log of every time an alert fired |
| `in_app_notifications` | The user's notification inbox |
| `user_notification_prefs` | Email/push/in-app on/off toggles |
| Finance tables (budgets, transactions, goals, bills, settings, zakat) | The personal-finance module |
| `profiles` | User profile + plan (Free/Pro) |

### How "each user sees only their own data" is enforced: **RLS**
**RLS = Row-Level Security.** It's a PostgreSQL feature (exposed by Supabase) where the database itself refuses to return rows that aren't yours. Every user table has a policy like:

```sql
CREATE POLICY "Users own their alerts" ON public.user_alerts
    FOR ALL TO authenticated
    USING (user_id = auth.uid())        -- can only read your own rows
    WITH CHECK (user_id = auth.uid());  -- can only write rows tagged as yours
```

So even if there were a bug in the app, the *database* would still stop user A from seeing user B's portfolio. (Our backend's scraper jobs use a special **service key that bypasses RLS**, because they legitimately write global market data.)

---

## 11. Migrations

### What is a migration?
A database isn't created by clicking around — it's built by running **SQL scripts** that create/alter tables. A **migration** is one such script, saved as a file with a **timestamped name** so they always run **in order**. Together, the migration files are the **complete, version-controlled history of the database's shape**. Anyone can rebuild the exact database by running them top to bottom.

### Where they live
```
backend/database/migrations/
├── 20260618092009_....sql               ← earliest
├── 20260706120000_psx_module.sql        ← created the 12 core PSX tables
├── 20260709010000_user_alerts_and_notifications.sql
├── 20260710000000_user_finance.sql
├── 20260711000400_alert_events.sql
├── 20260712...  (latest)                ← most recent
```

The numeric prefix is a timestamp (`YYYYMMDDHHMMSS`) → files sort chronologically → they apply in the right order.

### What a migration looks like (real excerpt)
```sql
CREATE TABLE IF NOT EXISTS public.in_app_notifications (
    id         BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    read       BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ... ;                         -- makes lookups fast
ALTER TABLE ... ENABLE ROW LEVEL SECURITY; -- turn on RLS
CREATE POLICY ... ;                        -- "users see only their own rows"
```

Each migration typically: **creates a table → adds indexes (for speed) → enables RLS → adds the ownership policy → grants access.**

### How we run them
Migrations are applied through the **Supabase Dashboard → SQL Editor** (paste the file and run), or via the Supabase CLI (`supabase db push`). They are written to be **idempotent** where possible (`CREATE TABLE IF NOT EXISTS`), so re-running one won't crash.

> **One-liner:** *"Migrations are timestamped SQL files in `backend/database/migrations/`. They're the version history of our schema — run in order they recreate the entire database, including tables, indexes, and row-level-security policies. We apply them via the Supabase SQL editor."*

---

## 12. How we fetch / scrape data

The PSX has **no free real-time API**, so we gather data from three public sources and cache it. All scrapers live in `backend/src/app/scrapers/`.

| Source | File | Format | What we get | How |
|---|---|---|---|---|
| **DPS** (`dps.psx.com.pk`, PSX's own portal) | `dps.py` | HTML tables + some JSON | Prices, OHLCV history, fundamentals, announcements, dividends, index closes | We fetch the page with **httpx**, then parse the HTML tables with **BeautifulSoup** |
| **TradingView scanner** | `tradingview.py` | JSON API | Sectors, market caps for ~478 stocks | Plain JSON POST request |
| **AhleTrade feed** | `ahletrade.py` | Pipe-delimited text | Real-time last-trade tape | HTTP poll, split on `\|` |

### How the DPS scraper works (the interesting one)
1. **Politeness:** `asyncio.Semaphore(2)` limits us to **2 concurrent requests** so we don't hammer PSX's servers.
2. **Fetch:** an async **httpx** client GETs/POSTs the page (with retries and a browser-like User-Agent).
3. **Parse:** **BeautifulSoup** reads the returned HTML, finds the `<table>`, and reads each `<tr>`/`<td>`. Crucially, it **finds columns by their header name** ("SYMBOL", "CURRENT", "VOLUME") rather than by fixed position — so if PSX reorders columns, the scraper still works.
4. **Normalize:** helper functions (`_f`, `_i`) clean strings like `"1,234.50"` into real numbers.
5. **Return** clean Python objects (`MarketSnapshotItem`, `OHLCVBar`, ...).

### Where the scraped data goes
The scrapers **don't** save anything themselves. The **scheduled jobs** (`jobs/scheduler.py`) call the scrapers and then **bulk-upsert** the results into Supabase:

```python
items = await dps.fetch_market_watch()          # scrape ~500 rows
db.table("psx_market_snapshot").upsert(rows, on_conflict="symbol").execute()  # save
```

**"Upsert"** = update-or-insert: if the symbol's row exists, update it; otherwise create it. So the snapshot table always holds exactly one current row per stock.

**Full path of a price:**
```
DPS website (HTML)
  → scrapers/dps.py (BeautifulSoup parses it)
    → jobs/scheduler.py (every 5s, market hours only)
      → Supabase table psx_market_snapshot (upsert)
        → later: browser calls GET /api/market/snapshot
          → repository SELECTs the row → returns JSON to the browser
```

Two live-ness tricks:
- Jobs only run **during market hours** (`_is_market_open()` checks Mon–Fri, 09:30–15:30 PKT).
- Supabase **Realtime** is enabled on `psx_market_snapshot`, so when a row changes the browser gets a **push** and refreshes instantly — no constant polling needed.

---

## 13. Authentication

We use a **two-tier** security model, decided in `middleware/auth.py`:

### Tier 1 — Public market endpoints (a shared API token)
Endpoints like `/api/market/*`, `/api/quote/*`, `/api/signal/*` are the same for everyone. They're protected by a **single shared bearer token** (`PSX_API_TOKEN`). The frontend sends `Authorization: Bearer <token>`; the middleware checks it matches. This just stops random strangers from hammering our API.

### Tier 2 — User endpoints (per-user Supabase JWT)
Endpoints like `/api/portfolio/*`, `/api/finance/*`, `/api/alerts/*`, `/api/notifications/*` are **personal**. These require a **JWT** — a *JSON Web Token*, the cryptographically-signed proof of login that Supabase gives the browser after the user logs in.

Flow (`api/deps.py` → `services/auth.py`):
1. Browser logs in via **Supabase Auth** and receives a JWT.
2. Browser sends it: `Authorization: Bearer <JWT>` on every user request.
3. The `require_user` dependency runs before the controller. It **verifies the token's signature** against Supabase's public keys (JWKS) — so a forged token is rejected.
4. If valid, it returns `{user_id, email, plan, features}`, which the service uses to scope data to that user and to enforce plan limits.
5. If missing/invalid → **401 Unauthorized** (a clean 401, not a confusing 422).

> **Why two tiers?** Market data is shared (one token is enough). User data is private and must be tied to a specific identity (per-user JWT + database RLS). Defense in depth: even if the token check were bypassed, RLS in the database still blocks cross-user access.

---

## 14. Doing CRUD manually

If someone asks *"how would you run CRUD by hand?"*, there are **three** levels. Show whichever fits.

### Level 1 — Through the interactive API docs (easiest, great for a live demo)
1. Start the backend (section 17).
2. Open **`http://localhost:8000/docs`** in a browser.
3. This is **Swagger UI** — every endpoint is listed and clickable. Click one → "Try it out" → fill the fields → "Execute". You'll see the real request and response. (For protected routes, paste a token in the "Authorize" box first.)

### Level 2 — With `curl` (raw HTTP from the terminal)
```bash
# READ — get the market snapshot (public route, shared token)
curl -H "Authorization: Bearer $PSX_API_TOKEN" \
     http://localhost:8000/api/market/snapshot

# CREATE — make a portfolio (user route, Supabase JWT)
curl -X POST http://localhost:8000/api/portfolio/create \
     -H "Authorization: Bearer $SUPABASE_JWT" \
     -H "Content-Type: application/json" \
     -d '{"name": "My Halal Picks"}'

# READ — list holdings in portfolio 42
curl -H "Authorization: Bearer $SUPABASE_JWT" \
     http://localhost:8000/api/portfolio/42/holdings

# UPDATE — change a holding (PATCH)
curl -X PATCH http://localhost:8000/api/portfolio/42/holdings/7 \
     -H "Authorization: Bearer $SUPABASE_JWT" \
     -H "Content-Type: application/json" \
     -d '{"shares": 200}'

# DELETE — remove a holding
curl -X DELETE http://localhost:8000/api/portfolio/42/holdings/7 \
     -H "Authorization: Bearer $SUPABASE_JWT"
```

Notice the pattern: **HTTP method = CRUD verb.** `POST`=create, `GET`=read, `PATCH/PUT`=update, `DELETE`=delete.

### Level 3 — Directly in the database (raw SQL)
Open **Supabase Dashboard → SQL Editor** and run SQL against the tables. This maps 1:1 to what the repository layer does:

```sql
-- CREATE
INSERT INTO psx_portfolios (user_id, name) VALUES ('<uuid>', 'My Picks');
-- READ
SELECT * FROM psx_holdings WHERE portfolio_id = 42 ORDER BY symbol;
-- UPDATE
UPDATE psx_holdings SET shares = 200 WHERE id = 7;
-- DELETE
DELETE FROM psx_holdings WHERE id = 7;
```

> Point to make: *"CRUD is just the four database operations (INSERT/SELECT/UPDATE/DELETE) exposed over HTTP as POST/GET/PATCH/DELETE. Our `api/portfolio.py` has literally one function per operation."*

---

## 15. HTTP status codes

Every HTTP response carries a **3-digit status code** telling the caller what happened. They're grouped by first digit:

| Range | Meaning | Think of it as… |
|---|---|---|
| **2xx — Success** | It worked | 👍 |
| **3xx — Redirection** | Go look somewhere else | ➡️ |
| **4xx — Client error** | *You* (the caller) did something wrong | 🙅 your fault |
| **5xx — Server error** | *We* (the server) broke | 💥 our fault |

### The specific ones this project uses

| Code | Name | When it happens here |
|---|---|---|
| **200** | OK | Request succeeded, data returned (most successful GET/POST) |
| **201** | Created | A new resource was created (CRUD "create") — conceptually |
| **3xx** | Redirect | Rare in an API; used by web pages ("moved", "see other"). Our API returns data, not redirects, so you won't see these much. Auth *login* redirects (Google OAuth) happen on the Supabase/frontend side. |
| **400** | Bad Request | The request is malformed — e.g. `update_holding` with **no fields to update** raises `HTTPException(400, "No fields to update")` |
| **401** | Unauthorized | Missing/invalid token — `require_user` raises this; also the API-token middleware for public routes |
| **403** | Forbidden | You're logged in but **not allowed** — e.g. a Free user exceeding their portfolio limit (`check_count_limit`) |
| **404** | Not Found | The thing doesn't exist or isn't yours — e.g. "Portfolio not found", "Holding not found" |
| **422** | Unprocessable Entity | **Validation failed** — FastAPI/Pydantic auto-returns this when the body doesn't match the schema (e.g. `name` too long, `shares` negative) |
| **429** | Too Many Requests | You hit the **rate limit** (e.g. more than 60/min on `/api/market/snapshot`) |
| **503** | Service Unavailable | The server isn't configured — e.g. `SUPABASE_JWT_SECRET` or `PSX_API_TOKEN` not set |
| **500** | Internal Server Error | An unhandled bug/crash on our side |

**Memory hook:** *"**4**xx = **f**our-fault-yours (client), **5**xx = **s**erver's fault."*

**Why the distinction matters:** the frontend behaves differently per code — `401` → send the user to log in again; `403` → show "upgrade your plan"; `404` → show "not found"; `422` → highlight the bad form field; `429` → "slow down"; `5xx` → "something went wrong, try later."

---

## 16. Background jobs

The backend doesn't just answer requests — it also runs **scheduled work** in the background using **APScheduler** (a Python job scheduler). Configured in `jobs/scheduler.py`, started at app boot (`init_scheduler()` in `main.py`'s lifespan).

| Job | Runs every | What it does |
|---|---|---|
| `job_refresh_market` | 5 seconds (market hours) | Scrape DPS market-watch → upsert `psx_market_snapshot` |
| `job_poll_ahletrade` | 5 seconds (market hours) | Poll AhleTrade for top-20 stocks → patch live prices |
| `job_refresh_tv_data` | 5 minutes | TradingView scanner → `psx_profile` (sectors) |
| `job_refresh_announcements` | 15 minutes | DPS announcements → `psx_announcements` |
| `job_check_alerts` | 60 seconds | Evaluate every user alert; fire notifications |
| `job_refresh_index_eod` | 01:00 PKT daily | Index closing values → `psx_index_eod` |
| `job_backfill_history` | 02:00 PKT daily | Full OHLCV history → `psx_ohlcv` |
| `job_refresh_fundamentals` | Sunday 04:00 PKT | P/E, EPS, etc. → `psx_fundamentals` + `psx_profile` |

This **decouples scraping from serving**: users get instant reads from the database, while the freshness is maintained quietly in the background. Every job is wrapped in `try/except` so one failure never crashes the server.

---

## 17. How to run it

```bash
# 1. Install everything
pnpm install                          # frontend deps (from repo root)
cd backend && pip install -e ".[dev]" # backend deps

# 2. Environment: create backend/.env with Supabase keys + PSX_API_TOKEN
#    and frontend/packages/web/.env with VITE_SUPABASE_* + VITE_PSX_API_URL

# 3. Run the backend (Terminal 1)
cd backend
python -m uvicorn app.main:app --reload --port 8000
#   → API at   http://localhost:8000
#   → Docs at  http://localhost:8000/docs

# 4. Run the frontend (Terminal 2)
pnpm run dev
#   → App at   http://localhost:8080
```

- `uvicorn` is the **ASGI server** that actually runs the FastAPI app (async web server).
- `--reload` restarts the server automatically when you edit code (dev only).

---

## 18. Glossary

| Term | Plain meaning |
|---|---|
| **API** | A set of URLs that return data (JSON), for programs to call |
| **Endpoint / Route** | One specific URL + method, e.g. `GET /api/quote/HBL` |
| **Controller / Route handler** | The function that handles an endpoint (our `api/` files) |
| **Service** | The layer holding business rules |
| **Repository** | The layer that runs SQL / talks to the DB |
| **Schema (Pydantic)** | A definition of what valid input/output data looks like |
| **ORM** | Object-Relational Mapping — translates between code objects and SQL tables |
| **SQLAlchemy** | The Python ORM/toolkit we use |
| **asyncpg** | The fast async PostgreSQL driver SQLAlchemy uses |
| **async / await** | Doing other work while waiting (on the DB, network) instead of blocking |
| **Reflection** | SQLAlchemy reading the live DB to learn its table shapes automatically |
| **Migration** | A timestamped SQL file that creates/changes tables (DB version history) |
| **Upsert** | Insert if new, update if it already exists |
| **CRUD** | Create, Read, Update, Delete (the four data operations) |
| **PWA** | Progressive Web App — a website that installs like a phone app |
| **Supabase** | Managed Postgres + Auth + Realtime + RLS ("Firebase for Postgres") |
| **PostgreSQL / Postgres** | The relational database engine |
| **RLS** | Row-Level Security — the DB itself restricts rows to their owner |
| **JWT** | JSON Web Token — a signed proof of who you are (login token) |
| **Bearer token** | A secret sent in the `Authorization` header to prove access |
| **Middleware** | Code that runs on *every* request before the controller |
| **Rate limiting** | Capping how many requests a caller can make per minute |
| **APScheduler** | The library that runs our timed background jobs |
| **Scraping** | Extracting data from a website's HTML because it has no API |
| **BeautifulSoup** | The Python library that parses HTML for us |
| **httpx** | The async HTTP client we use to fetch pages |
| **Uvicorn** | The async server that runs the FastAPI app |
| **OpenAPI / Swagger** | The auto-generated interactive API docs at `/docs` |
| **Monorepo** | One git repository holding several projects (frontend + backend + docs) |
| **Pooler** | A connection broker that shares a few DB connections efficiently |

---

## 19. Likely questions & answers

**Q: Walk me through your architecture.**
A: Monorepo with a React frontend and a Python FastAPI backend, sharing a Supabase Postgres database. The backend is layered: controllers in `api/` receive HTTP, services hold business logic, repositories run SQL, and the `db/` layer manages the SQLAlchemy connection. Background jobs scrape PSX every few seconds and cache into Postgres, so user requests are instant reads.

**Q: Why FastAPI?**
A: Our workload is I/O-heavy scraping, so async is a natural fit; our ML/data stack is Python; and we get automatic validation and interactive docs for free.

**Q: What's a controller in your project?**
A: A FastAPI route handler in the `api/` folder. It's thin — parse input, verify auth, delegate to a service, return JSON. No business logic in it.

**Q: What design pattern is this — MVC?**
A: It's layered Controller–Service–Repository, essentially MVC without the server-side View, because our View is the React app. Splitting the "Model" into Service (rules) and Repository (data) gives cleaner separation and easier testing.

**Q: What is an ORM and why SQLAlchemy?**
A: An ORM translates between code and SQL tables. We use SQLAlchemy Core with async asyncpg — it's the Python standard, supports async, auto-reflects our schema from the live DB, and parameterizes queries to prevent SQL injection.

**Q: How do you keep one user from seeing another's data?**
A: Two layers. The API verifies a per-user Supabase JWT and scopes every query to that `user_id`. And Postgres Row-Level Security refuses cross-user rows at the database level — so even a bug can't leak data.

**Q: Where does the market data come from?**
A: Three public sources — the PSX DPS portal (HTML, scraped with BeautifulSoup), the TradingView scanner (JSON), and the AhleTrade feed (real-time tape). Scheduled jobs pull them and upsert into Supabase; the API just serves the cached copy.

**Q: What are migrations?**
A: Timestamped SQL files in `backend/database/migrations/` that build and evolve the schema in order — the version history of the database, including tables, indexes, and RLS policies. We apply them via the Supabase SQL editor.

**Q: What do the status codes mean?**
A: 2xx success, 3xx redirect, 4xx the caller's mistake (401 not logged in, 403 not allowed, 404 not found, 422 invalid input, 429 too many requests), 5xx our server's fault (500 crash, 503 not configured).

**Q: How would you do CRUD manually?**
A: Three ways — the interactive `/docs` page, raw `curl` (POST/GET/PATCH/DELETE), or straight SQL in the Supabase SQL editor. They all map to the same INSERT/SELECT/UPDATE/DELETE the repository layer runs.

---

*Prepared as a from-scratch walkthrough of the NafaIQ backend + system. Pair it with `recall/PRESENTATION_PREP.md` (frontend-focused) for full coverage. Good luck!* 🍀
