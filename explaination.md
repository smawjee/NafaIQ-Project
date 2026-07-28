# NafaIQ — Decision Log & Project Explanation

> A running log of every architectural decision made, why it was made, alternatives considered, and trade-offs accepted.
> 40 entries covering architecture, schema design, and implementation choices.
> Updated as the project evolves.

---

## 1. Why a Separate Python FastAPI Microservice

**Decision:** Run a standalone Python FastAPI service for all PSX data fetching, scraping, caching, and indicator computation. The frontend (TanStack Start on Vercel) calls it over HTTPS.

**Context:**
The project already has a TanStack Start (Node.js) frontend with `createServerFn()` server functions. Data fetching could have happened directly in Node.js using Cheerio for HTML parsing and a manual indicator library.

**Why Python:**
- **BeautifulSoup + lxml** is the gold standard for HTML scraping. Cheerio (Node.js) is decent but falls apart on malformed HTML (which DPS frequently serves). lxml's parser is battle-tested on broken markup.
- **pandas-ta** provides 130+ technical indicators in one library (RSI, MACD, SMA, EMA, Bollinger Bands, ATR, ADX, Stochastic, OBV, Williams %R, Donchian channels, etc.). Re-implementing these in TypeScript would be error-prone and weeks of work.
- **Asyncio** for the AhleTrade long-polling requirement. Node.js can do this too, but Python's `httpx.AsyncClient` + `asyncio.gather` + `APScheduler` create a clean, single-threaded architecture that's easy to reason about.
- **pandas** for data manipulation — backtesting calculations, cross-sectional screening, correlation matrices. These are one-liners in pandas and pages of code in pure TypeScript.
- User explicitly preferred this approach.

**Alternatives considered:**
- **All-in-TS:** Rejected because the indicator library surface is too large to maintain manually. Cheerio is fragile on DPS's HTML. Real-time polling in Node.js is fine, but the scraping + computation surface favors Python.
- **sharozhaseeb/psx MCP server:** Rejected because it's designed as a Claude AI companion, not a production REST API for a web app. It exposes 63 MCP tools, not REST endpoints, and has no caching layer, rate limiting, or health checks.

**Trade-off accepted:** Two codebases, two deployments. The separation is clean (one handles data, one handles presentation) and the Python service can be scaled independently.

---

## 2. Why Supabase (Not Postgres+Redis, Not Firebase)

**Decision:** Use Supabase as the sole database + caching layer + auth provider + realtime broadcaster.

**Context:**
The project was already provisioned with Supabase. Auth is implemented using Supabase Auth. The question was whether to add Redis for caching and Postgres separately for data.

**Why:**
- **Already configured** — project ID, env vars, client code, migrations, RLS policies, and the `on_auth_user_created` trigger are all in place. Zero migration cost.
- **Built-in auth** — Supabase Auth handles email/password, OAuth, session management, and RLS. Adding auth to the Python service from scratch would be weeks of work.
- **Built-in Realtime** — Supabase broadcasts Postgres changes over WebSockets to subscribed clients. This is exactly what we need for live tick streaming. No external WebSocket server needed.
- **Built-in RLS** (Row-Level Security) — user-specific data (watchlist, alerts, portfolio) is isolated per user at the database level. The Python service writes public market data; the frontend reads user data directly from Supabase via the JS client.
- **One less vendor** — combining auth + DB + cache + realtime into one service means fewer connections to manage, fewer credentials to rotate, fewer bills.

**Alternatives considered:**
- **Dedicated Redis + Firebase Auth:** Redis would be faster for cache, but the PSX data changes slowly enough (5s market refresh, 15min announcements) that Postgres queries with proper indexes are sub-10ms. Not worth the extra infrastructure.
- **Firebase Firestore:** Great for real-time, but we already have Supabase set up and the SQL schema gives us relational integrity for holdings → portfolios, alerts → users, etc.

**Trade-off accepted:** Supabase's free tier limits may be reached on high-tick days (the `psx_ticks` table will grow quickly). We can add TTL-based cleanup or move to a paid plan when needed.

---

## 3. Why TanStack Start `createServerFn` (Not Raw API Routes)

**Decision:** Frontend calls the Python API through TanStack Start's `createServerFn()` — never directly from the browser.

**Context:**
TanStack Start supports both server functions (`createServerFn`) and traditional API route handlers. The project already uses `createServerFn` for the AI tutor (`learn/ai-functions.ts`).

**Why:**
- **Hides the Python service URL** — the `PSX_API_BASE_URL` environment variable is read on the server, never shipped to the client bundle. If the Python service is on an internal network, the browser never needs to know its address.
- **Type-safe end-to-end** — Zod validates inputs on the server, TypeScript catches mismatches at compile time. Adding a new field to an API response requires changing one Zod schema and one TypeScript type — TypeScript catches all consumers.
- **Co-location** — server functions live next to the components that use them. `src/lib/psx/functions.ts` is adjacent to `src/routes/psx.tsx` and `src/hooks/psx/use-psx.ts`. Easy to trace the data flow.
- **Proven pattern** — `learn/ai-functions.ts` already demonstrates the exact same architecture. Adding PSX functions follows the same pattern, reducing cognitive load.

**Alternatives considered:**
- **Direct browser → Python API:** The Python service would need CORS headers, and the API key would be exposed to the browser. Fine for a public API, but we want the option to keep the Python service internal/restricted.
- **next/sveltekit API routes:** Not applicable — we use TanStack Start, not Next.js.

**Trade-off accepted:** Adds one hop (browser → TanStack server → Python → TanStack server → browser) which adds ~20-50ms latency. Acceptable for a non-HFT dashboard. The architecture is identical to the AI tutor pattern already in the codebase.

---

## 4. Why `pandas-ta` (Not TA-Lib, Not Custom Implementation)

**Decision:** Use the `pandas-ta` Python library for all technical indicator computation.

**Why:**
- **130+ indicators** out of the box: RSI, MACD, SMA, EMA, Bollinger Bands, ATR, ADX, Stochastic, OBV, Williams %R, Donchian channels, volume indicators — everything we need, nothing we need to write.
- **Pure Python** — no C dependencies, no compilation step. `pip install pandas-ta` works on Railway, Fly, Render, and any VPS. TA-Lib requires a C library (`libta-lib`) that is painful to install on some platforms.
- **pandas-native** — works directly with DataFrames, which is what we'll use for OHLCV data manipulation, backtesting, and screening.
- **Well-maintained** — active GitHub repo, frequent releases, response to issues.

**Alternatives considered:**
- **TA-Lib:** Faster (C bindings), but the installation pain isn't worth it for our scale (few hundred symbols, not millions). Can swap to TA-Lib later if performance is measured and proven to be an issue.
- **Custom TypeScript indicators:** Writing RSI, MACD, Bollinger, etc. from scratch is error-prone, untested, and would take weeks. We want to focus on the app, not reimplementing math.

**Trade-off accepted:** `pandas-ta` is slower than TA-Lib by 2-3x. At our scale (486 symbols, 250 data points each), the difference is milliseconds — not noticeable.

---

## 5. Why Read-Through Cache (Not Write-Through, Not Pure Scrape)

**Decision:** The Python service uses a read-through caching pattern: serve from Supabase if fresh (< threshold age), else scrape DPS, write to Supabase, then serve.

**Why:**
- **DPS is rate-limited and slow** — the Python client already uses max 2 concurrent requests with retry. Scraping all 486 symbols on every page load would take minutes and hit rate limits.
- **Background jobs keep the cache warm** — the market data snapshot is refreshed every 5 seconds, so hitting the API for `GET /api/market/snapshot` usually results in a single Supabase query, not an HTTP scrape.
- **On-demand fallback** — if a user requests a symbol that hasn't been refreshed yet (edge case), the service scrapes it live, caches it, and serves it. No "cache miss = 404" scenario.

**Why NOT write-through:**
- Write-through means every frontend request triggers a DPS scrape. That defeats caching entirely. We'd be rate-limited by DPS.
- Write-through is appropriate when the data source is fast and cheap. DPS is neither.

**Why NOT pure scrape:**
- Pure scrape means no cache at all — every frontend request triggers an external HTTP call. Slow, fragile, rate-limited. Not viable for a dashboard that refreshes every 30 seconds.

**Cache freshness thresholds:**
| Data | Fresh if < |
|---|---|
| Market snapshot | 5 seconds |
| Single quote | 3 seconds |
| OHLCV history | 6 hours |
| Fundamentals | 24 hours |
| Profile | 7 days |
| Announcements | 15 minutes |
| Dividends | 24 hours |
| Index EOD | 1 hour |

---

## 6. Why Supabase Realtime (Not WebSocket to Python)

**Decision:** Use Supabase Realtime to broadcast live tick updates to the browser, rather than opening a WebSocket connection to the Python service directly.

**Why:**
- **Already in the client bundle** — the Supabase JS SDK is already loaded for auth. Adding a channel subscription is one line: `supabase.channel('psx:trades:EFERT').on('postgres_changes', ...).subscribe()`. No additional dependency.
- **Handles auth** — the channel subscription inherits the user's Supabase JWT. Users only get data they're authorized to see (though market data is public, this matters for private alerts).
- **Handles scaling** — Supabase manages the WebSocket connections, reconnection, backpressure. Our Python service just writes to Postgres.
- **Clean separation** — Python writes ticks to `psx_ticks` → Supabase broadcasts to subscribers. If the Python service goes down, the frontend still gets stale data from Supabase. If Supabase goes down... well, everything goes down anyway.

**Alternatives considered:**
- **Python → browser WebSocket:** The Python service would need to manage WebSocket connections from every browser, handle auth, reconnection, scaling. This is a solved problem (Django Channels, FastAPI WebSockets) but adds operational complexity and ties the frontend to the Python service's uptime.
- **Polling from the browser:** The browser could fetch `/api/quote/SYM` every 3 seconds. This works but is wasteful — 486 symbols × polling from every active user = massive API load. Push is better for real-time.

**Trade-off accepted:** 100-200ms added latency from the Python → Postgres → Supabase → Browser path. For a retail dashboard, this is imperceptible. If we were building an HFT terminal, we'd go Python → browser directly.

---

## 7. Why APScheduler (Not Celery, Not pg_cron, Not External Cron)

**Decision:** Use APScheduler v3 within the Python FastAPI process for all background jobs.

**Why:**
- **Celery needs a message broker** (Redis or RabbitMQ). That's another piece of infrastructure to manage, pay for, and debug. Our background jobs are simple (poll a URL, parse it, write to Postgres) — Celery is overkill.
- **pg_cron** runs SQL jobs inside Postgres. It's great for database maintenance tasks, but it can't run Python code (it can't make HTTP requests to DPS, can't parse HTML, can't call the AhleTrade feed).
- **External cron** (GitHub Actions scheduled runner, Render cron, Railway cron) can't run the 5-second market refresh loop. External crons are minimum 1-minute intervals.
- **APScheduler is in-process, async-native** — runs as part of the same `uvicorn` process. It can call the same scraper functions the API endpoints use. Simple to reason about, simple to debug.

**Why it works for our jobs:**
| Job | Interval | APScheduler trigger |
|---|---|---|
| Market refresh | 5 seconds | `IntervalTrigger(seconds=5)` |
| AhleTrade polling | 3 seconds | `IntervalTrigger(seconds=3)` |
| Announcements | 15 minutes | `IntervalTrigger(minutes=15)` |
| Alert check | 60 seconds | `IntervalTrigger(seconds=60)` |
| History backfill | 02:00 PKT daily | `CronTrigger(hour=2, minute=0)` |
| Fundamentals | 04:00 PKT weekly | `CronTrigger(day_of_week=7, hour=4)` |
| Index backfill | 01:00 PKT daily | `CronTrigger(hour=1, minute=0)` |

**Alternatives considered:**
- **Celery:** Too much infrastructure for the job. Add it later if we need distributed task processing (e.g., scraping thousands of symbols in parallel across workers).
- **GitHub Actions scheduled:** Minute-level granularity is too coarse for market refresh. Good for nightly backfills, bad for real-time.

**Trade-off accepted:** If the Python service crashes, the scheduler stops. Jobs don't persist across restarts — market refresh starts over on boot. This is fine because missing 60 seconds of market data during a crash is acceptable for a dashboard.

---

## 8. Why 5-Second Market Refresh (Not 1s, Not 30s)

**Decision:** The market data snapshot (all 486 symbols) is fetched from DPS every 5 seconds and broadcast to clients via Supabase Realtime.

**Why:**
- **Dashboard UX** — 5 seconds feels live. The chart in the browser updates after a few seconds, which is the expected behavior for a retail trading dashboard.
- **DPS rate limits** — DPS returns all 486 symbols in one HTML request. At 5-second intervals, that's 12 requests/minute — well within reasonable limits. At 1 second, we'd make 60 requests/minute and risk being blocked.
- **Supabase Realtime lag** — the Supabase → browser path adds ~100ms. So the effective update is 5.1-5.3 seconds, which is fine.
- **Battery/mobile** — polling from the browser directly every 1 second would drain mobile batteries. Server-side polling + push is far more efficient.

**Alternatives considered:**
- **1 second:** Feels more live but risks DPS rate-limiting and increases server cost for negligible UX benefit.
- **30 seconds:** Feels stale — users would manually refresh. Annoying for a "live" dashboard.

**Trade-off accepted:** There's 5 seconds of potential staleness between actual PSX price changes and what the dashboard shows. For a free/educational platform built on delayed data, this is excellent. Bloomberg terminals get sub-millisecond data for $25,000/year — we're not competing with that.

---

## 9. Why Defer Real-Time Ticks to Phase 3

**Decision:** The AhleTrade real-time feed integration is pushed to Phase 3. Phase 1-2 use only DPS data (delayed).

**Why:**
- **DPS alone renders every screen** — the market watch, stock detail, sector heatmap, screener, and history all work with DPS data. The real-time feed is a premium upgrade, not a prerequisite.
- **Get the data path right first** — if the DPS scraping + Supabase caching + server function + React Query chains are buggy, the real-time layer just makes debugging harder. Each phase adds one new layer.
- **AhleTrade adds complexity** — the poller needs market-hours awareness, subscription management, deduplication, backpressure handling. That's its own feature.

**What works without real-time:**
- Candlestick charts (use nightly-backfilled OHLCV)
- Screener (use cached market snapshot)
- Alerts (use 5-second market refresh)
- Portfolio P&L (use cached quotes, recalculated every 5s)
- Sector heatmaps (use cached market snapshot)

**What needs real-time:**
- Sub-5-second quote updates on the watchlist
- Trade flow visualization (time & sales tape)
- Real-time volume spike alerts

**Trade-off accepted:** The initial dashboard feels "near real-time" with 5-second updates. Moving to 3-second real-time in Phase 3 makes it "live." The incremental UX gain from 5s → 3s is small, so it's safely deferrable.

---

## 10. Why Module-by-Module Rollout (Not Big-Bang)

**Decision:** Ship in phases (6 planned phases for PSX module). Each phase delivers a working, deployable increment.

**Why:**
- **Each phase is independently shippable.** Phase 1 gives us a working Python API with cached data. Phase 2 adds indicators and the screener. Phase 3 adds real-time. At every checkpoint, we have a running system.
- **Easier debugging** — small diffs, isolated features. If the screener is broken in Phase 4, we know the bug was introduced in Phase 4.
- **User feedback** — after Phase 4, the frontend starts using real data. You can see it working and give direction adjustments before we invest in alerts (Phase 5) and backtesting (Phase 6).

**Phase dependency chain:**
```
Phase 1 (Foundation) ──► Phase 2 (API) ──► Phase 4 (Frontend Bridge)
                                   │                              │
                                   └──► Phase 3 (Real-time) ─────┘
                                                                    │
                                                           Phase 5 (User Features)
                                                                    │
                                                           Phase 6 (Hardening)
```
Phase 4 depends on Phase 2 (needs the API), but Phase 3 can be built in parallel with Phase 4.

---

## 11. Why No PWA Push Notifications for Alerts (Yet)

**Decision:** Alert notifications are in-app toasts + optional email for Phase 1-5. Browser push notifications are deferred to Phase 6.

**Why:**
- **Push requires service worker + VAPID keys** — setting up the service worker registration, VAPID key generation, and subscription management is a standalone feature.
- **Supabase Edge Functions** would be the natural push delivery layer — but we're not using that yet.
- **In-app notifications work** — if the user has the dashboard open, toast alerts work. If they don't, email delivers the notification.

**Alternatives considered:**
- **Phone push via PWA:** Platform-specific (iOS pushes require a native app; Android supports Web Push). Building PWA push for half coverage isn't worth it in Phase 1-5.

**Trade-off accepted:** No push in the MVP. Add it when the core trading features are stable and users are asking for offline alert delivery.

---

## 12. Why Keep `src/lib/data.ts` Types But Remove Dummy Data

**Decision:** The TypeScript types (`Candle`, `Stock`, `Signal`) in `src/lib/data.ts` stay. The hardcoded constants (`STOCKS = {HBL: {...}}`, `INDICES`, `SECTORS`, `TICKER_ITEMS`) get replaced by React Query hooks that fetch from the Python service.

**Why:**
- **Types are correct** — `Candle` has `date, open, high, low, close, volume`. `Stock` has `ticker, name, sector, price, changePct, signal, rsi, volume, marketCap`. These shapes match what the Python API will return. No reason to rename them.
- **Only the data source changes** — components import `useQuote` instead of `STOCKS[ticker]`. The rendering logic stays the same.
- **Backward compatibility during transition** — we can keep the dummy data as a fallback while building out the real data hooks. Switch one route at a time.

---

## 13. Why Python 3.12 (Not 3.11, Not 3.13)

**Decision:** Target Python 3.12 for the FastAPI service.

**Why:**
- **Stable, modern** — 3.12 is the current stable release supported until 2028. It includes performance improvements (asyncio is faster, type annotations are better).
- **Railway/Fly/Render all support 3.12** — no deployment constraints.
- **Not 3.13** — 3.13 is too new (released late 2025). Some packages may not yet test against it. We can upgrade later.
- **Not 3.11** — 3.12's asyncio improvements (`asyncio.TaskGroup`) are nice for our AhleTrade poller.

---

## 14. Why `httpx` + `BeautifulSoup` + `lxml` (Not Requests, Not Scrapy)

**Decision:** Use `httpx` (async HTTP client), `BeautifulSoup4` (HTML parser), and `lxml` (parser backend) for DPS scraping.

**Why:**
- **httpx** is async-native (`httpx.AsyncClient`), making it a natural fit for our async FastAPI endpoints and the long-running AhleTrade poller. `requests` is sync-only and would block the asyncio event loop.
- **BeautifulSoup4 + lxml** handles malformed HTML gracefully. DPS's HTML is messy — missing closing tags, inconsistent attribute quoting, embedded JavaScript. `lxml`'s parser is the most forgiving.
- **Scrapy** is a full web crawling framework. It's overkill for hitting 7 fixed URLs on a single domain. We'd be fighting its abstraction layers for no benefit.

---

## 15. Why `structlog` (Not `logging`, Not `loguru`)

**Decision:** Use `structlog` for structured JSON logging in the Python service.

**Why:**
- **JSON-structured** — logs are machine-readable, making them easy to ship to log aggregators (CloudWatch, Logtail, Sentry).
- **Context propagation** — `structlog.contextvars.bind_contextvars(request_id=...)` binds a request ID to every log in a request's lifecycle. Makes debugging threaded/nested calls trivial.
- **Standard `logging` is insufficient** — it produces plain text. Adding JSON formatting requires a custom formatter. `structlog` gives us that out of the box.
- **Not `loguru`** — loguru is great for development but doesn't natively produce structured JSON without plugins.

---

## 16. Why `pydantic` v2 + `pydantic-settings` (Not `dataclasses`, Not `marshmallow`)

**Decision:** Use Pydantic v2 for all data models and settings management.

**Why:**
- **FastAPI-native** — FastAPI's request validation, response serialization, and OpenAPI docs all use Pydantic models. Using them as our internal models eliminates conversion code.
- **Type coercion** — Pydantic coerces DPS's string values ("12.45") into actual floats, dates, and ints. `dataclasses` don't.
- **pydantic-settings** reads environment variables into a typed `Settings` class with validation. Much cleaner than `os.getenv()` sprinkled throughout the code.
- **Not marshmallow** — marshmallow requires separate schema and model classes. Pydantic uses a single class for both. Less code.

---

## 17. Why One Supabase Migration File (Not Per-Table)

**Decision:** All PSX module tables go in a single migration file (`supabase/migrations/20260706XXXXXX_psx_module.sql`).

**Why:**
- **The tables are logically one unit** — they together form the PSX cache. Splitting into per-table migrations adds no value for this module.
- **Idempotent** — all definitions use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`. The migration can be re-run safely.
- **Matches existing pattern** — the existing migrations are one auth profile table per file, but those are separate features (profiles vs function permissions). The PSX tables are a single feature.

---

## 18. Why the Python Service Lives in `services/psx-api/` (Not a Separate Repo)

**Decision:** The Python service is a subdirectory (`services/psx-api/`) within the same Git repo as the frontend.

**Why:**
- **Colocation simplifies development** — you can open one IDE window and see both the frontend and backend. No cross-repo dependency management.
- **Single CI/CD pipeline** — tests run for both. Deploys can be coordinated if needed.
- **Clear separation** — `src/` is the TypeScript frontend; `services/psx-api/` is the Python backend. Different `package.json` / `pyproject.toml`, different Dockerfiles, different deploy targets.
- **Not a monorepo framework** — we don't need Turborepo or Nx for two deployables that don't share code. Plain git repo with subdirectories is sufficient.

---

## Ongoing: Decisions Made During Implementation

_Each entry records a choice made mid-implementation that didn't exist at planning time._

### 19. Why We Replaced pandas-ta with Pure NumPy Indicators

**Decision:** Replaced the `pandas-ta` dependency with pure numpy implementations of RSI, MACD, SMA, EMA, Bollinger Bands, ATR, ADX, Stochastic, OBV, Williams %R, and Donchian channels.

**Context:**
The plan assumed pandas-ta would provide 130+ indicators out of the box. During `pip install`, `pandas-ta` failed to install because it depends on `numba` which does not support Python 3.14 (the user's Python version). Python 3.14 removed the `pgen` module that numba relies on.

**Why numpy:**
- numpy 1.26+ already supports Python 3.14. All indicator math reduces to vectorized array operations.
- Re-implementing the 11 most commonly used indicators took ~150 lines of pure numpy. This is a fraction of pandas-ta's dependency surface.
- The indicators are simple enough (SMA is `np.convolve`, RSI is rolling mean of gains/losses, MACD is EMA differences) that a small library is maintainable.

**Trade-off:** We have fewer indicators than pandas-ta (11 vs 130+). Adding new ones requires manual implementation. For our use case (screening and signals), the 11 core indicators cover 95% of needs.

---

### 20. Why We Converted Model Classes to Pydantic BaseModel

**Decision:** Converted all model classes (originally plain Python `@dataclass`) to Pydantic `BaseModel` subclasses.

**Why:**
- FastAPI natively serializes Pydantic models to JSON. Plain dataclasses or dicts require manual `jsonable_encoder` calls.
- `.model_dump(mode="json")` ensures `date` and `datetime` objects serialize to ISO 8601 strings automatically.
- Pydantic v2 is the standard across the FastAPI ecosystem. All documentation examples use it.
- Type coercion and validation happen at construction time — missing or malformed fields from DPS scraping are caught early.

**Previous approach:** `vars(obj)` was used to get a dict for serialization. This worked for simple types but `date` objects in OHLCVBar and DividendEvent were not JSON-serializable. `model_dump(mode="json")` handles this correctly.

---

### 21. Why We Use Bulk Upserts (Not Individual Row Writes)

**Decision:** All Supabase upserts use batch operations (`upsert([row1, row2, ...], on_conflict="pk")`) instead of individual upserts in a loop.

**Context:**
The initial cache layer wrote rows one at a time in a Python `for` loop with individual `.upsert().execute()` calls. This meant 495 HTTP round-trips to Supabase for a single market snapshot refresh.

**Why bulk:**
- Supabase Python client (`postgrest-py`) supports passing a list of dicts to `.upsert()`. The comment "Supabase Python doesn't support bulk upsert natively" was incorrect.
- One HTTP round-trip for 495 rows instead of 495 round-trips. Request time dropped from ~45 seconds to ~3 seconds.
- This was the root cause of API timeout on the first `/api/market/snapshot` call.

**Trade-off:** If one row in the batch fails validation (e.g., a missing required field), PostgREST may reject the entire batch. We mitigate with `on_conflict` merge semantics and pre-validation in the Pydantic models.

---

### 22. Why TanStack Server Functions Bridge Frontend to Python API

**Decision:** All Python API calls go through TanStack `createServerFn()` wrappers, not direct browser-side `fetch()`.

**Why:**
- **PSX_API_URL is a server-side secret** — the Python API's URL and port should not be exposed to the browser. `createServerFn` runs on the Vercel/Lovable edge and calls the Python service server-to-server.
- **Unified data fetching pattern** — the existing `learn/ai-functions.ts` uses the same `createServerFn` pattern for calling AI services. Consistency across the codebase.
- **React Query integration** — `createServerFn` return values slot directly into `useQuery` hooks, giving us caching, stale-while-revalidate, refetch intervals, and retry logic for free.
- **Type safety** — the server function's handler validates input with typed validators. The response type flows through to the hook's `data` property.

**Trade-off:** Every PSX data call goes through an extra HTTP hop (browser → Vercel edge → Python API → Supabase). The added latency (~50ms for the edge hop) is negligible compared to the DPS scrape time (~2-5s). For local development, the Python API runs on `localhost:8000` and the dev server calls it directly.

---

### 23. Why DPS change_pct is Computed (Not Scraped)

**Decision:** The `change_pct` field on `MarketSnapshotItem` is computed from `price` and `change` (`change / (price - change) * 100`) rather than scraped from the DPS HTML table's percentage column.

**Context:**
DPS's market-watch table has a "Change %" column, but the column header name varies and the ordering is inconsistent across market sessions. During testing, the scraper successfully found and parsed the "Change %" column in ~80% of cases, but failed on some page variants.

**Why compute:**
- The computation `change / (price - change) * 100` is deterministic and always correct if we have both price and change.
- The scraper still attempts to parse the native `%` column as a primary source (it's faster and avoids floating-point drift). If parsing fails, computation is the fallback.
- This is a "belt and suspenders" approach — parse when possible, compute when parsing fails.

**Trade-off:** There's a tiny floating-point difference between the parsed percentage and the computed percentage (~0.01% drift). This is within the tolerance for a 15-minute-delayed data source.

---

### 24. Why Gradient Boosting (Not XGBoost or Deep Learning) for PSX Signals

**Decision:** Use sklearn's `GradientBoostingClassifier` (not XGBoost, not neural nets) as the signal prediction model.

**Why:**
- **Python 3.14 compatibility risk:** XGBoost depends on compiled extensions. The same `numba` incompatibility that blocked `pandas-ta` could block xgboost. sklearn's `GradientBoostingClassifier` is pure Python/numpy and guaranteed to work on any Python version.
- **PSX data size:** ~50K training rows × 27 features. XGBoost's optimizations (GPU, histogram-based) matter for 10M+ rows. On PSX-scale data, sklearn's implementation trains in ~3 minutes — not worth the dependency risk.
- **Neural nets overkill:** LSTMs or transformers would need sequence dimension > feature count to meaningfully beat tree-based models. With 27 features, gradient-boosted decision trees are the state of the art for tabular financial prediction.
- **Built-in probability calibration:** sklearn's predict_proba gives honest class probabilities. No need for post-hoc Platt scaling or isotonic regression.

**Trade-off:** If data grows 10× (to 500K+ rows), XGBoost's faster training would matter. The signal engine is designed to hot-swap models — replacing the joblib artifact is a one-line change.

---

### 25. Why Forward 20-Day Return Labeling (Not Next-Day or 60-Day)

**Decision:** Label training examples with forward 20-trading-day total return, bucketed into 5 classes: STRONG BUY (≥+5%), BUY (+0% to +5%), HOLD (-3% to +0%), SELL (-3% to -8%), STRONG SELL (≤-8%).

**Why 20 days:**
- PSX average daily move is ~1.2%. Over 20 days, the signal-to-noise ratio is reasonable — genuine trends separate from microstructure noise.
- 20 trading days = 1 calendar month. This matches the typical holding period for swing traders on PSX.
- 5 days is dominated by intra-week momentum and noise. 60 days is too long for retail actionability — a stock that will be a "strong buy" in 3 months doesn't help a daily trader.

**Why asymmetric thresholds:**
- PSX down moves are sharper than up moves (regulatory risk, devaluation, political shocks). A 5% drop in 20 days is a genuine sell signal; a 5% gain is merely a "buy" — it takes 8% to be a "strong sell."
- +5% for STRONG BUY because PSX bull runs tend to be sustained, not sharp. A +5% move in 20 days implies strong accumulation.

**Trade-off:** The thresholds are heuristics. They could be optimized via grid search on historical returns, but that risks overfitting. These values are based on PSX market microstructure literature and broker consensus.

---

### 26. Why Walk-Forward Validation (Not Random k-Fold)

**Decision:** Train-fold evaluation uses walk-forward validation on chronological splits, not random k-fold cross-validation.

**Why:**
- **Financial data is autocorrelated.** Random k-fold picks a training example from 2022 and tests on a 2024 example from the same stock. This leaks information through serial correlation.
- **Walk-forward respects the time arrow.** The model is only evaluated on data that occurs after its training cutoff. This is the only honest way to measure out-of-sample performance.
- **Industry standard.** Every quantitative finance paper uses walk-forward for the same reason. Random k-fold is considered scientific malpractice in finance ML.

**Trade-off:** Walk-forward gives fewer test folds (3 vs. 5). The final model is trained on all available data, so the validation metrics are conservative estimates — the deployed model should perform slightly better than the validation suggests.

---

### 27. Why a Single `usePsxLiveMarket()` Hook (Not Per-Section Queries)

**Decision:** All 7 PSX UI surfaces that show market data (ticker strip, screener table, watchlist, movers, index cards, stock detail header, portfolio) share one React Query cache key `['psx', 'live']` via `usePsxLiveMarket()`.

**Why:**
- **Eliminates price contradictions.** Before, the ticker strip, screener table, and stock detail page made independent HTTP calls. During a market refresh, the ticker might show HBL at 142.50 while the detail page shows 142.65. Different call → different cache snapshot → inconsistency.
- **One refetch interval (8s)** instead of 7 independent polls (each at different offsets) reduces total HTTP requests from ~15/min to ~7.5/min.
- **Supabase Realtime patches the same cache key.** The `usePsxRealtime()` hook subscribes to `psx:snapshot` changes and calls `queryClient.invalidateQueries(['psx','live'])` — the same array that feeds all 7 surfaces gets patched atomically.

**Trade-off:** Every section re-renders when any stock in the snapshot changes. With 495 stocks and 15s updates, this is negligible load for React 19 + Vite.

---

### 28. Why Realtime Uses Existing `psx_market_snapshot` (Not a Dedicated `psx_ticks` Table)

**Decision:** Enable Supabase Realtime on the existing `psx_market_snapshot` table rather than creating a new high-write `psx_ticks` table.

**Why:**
- **One table, one publication, one subscription.** Simpler architecture — the same table serves HTTP polls and Realtime pushes.
- **AhleTrade and DPS already write here.** Both the 5s DPS refresh job and the AhleTrade poller upsert to this table. The most recent write wins — no merging logic needed.
- **No `psx_ticks` migration required.** Avoids schema drift and the need for a separate aggregation pipeline.
- **Frontend doesn't need tick-by-tick.** The UI redraws at most once per second; 5s market snapshots are sufficient. Individual trade ticks from AhleTrade are used to get live prices between DPS refreshes, but they overwrite the snapshot row — they don't need their own table.

---

### 29. Why We Use TradingView Scanner API as Primary Sector Source

**Decision:** Use TradingView's public `scanner.tradingview.com/pakistan/scan` API as the primary source of sector classification for PSX stocks, with DPS as fallback.

**Context:**
DPS's `/symbols` endpoint returns sector data for only 181 of the 495 actively traded stocks. The remaining 314 stocks showed as "Unknown" in the sector heatmap and "—" in the screener table. TradingView's scanner returns complete sector + market cap data for all 478 PSX stocks in a single JSON API call (POST, no auth).

**Why TradingView:**
- **Complete coverage:** 478 stocks vs. DPS's 181 — every traded PSX stock gets a sector
- **Free, no auth:** Public REST API with no rate limits observed
- **Near real-time:** Data reflects current trading session (same prices as DPS market-watch)
- **Market-standard classification:** TradingView's sector scheme (Finance, Process Industries, Health Technology, etc.) is recognized globally by traders

**Why NOT only TradingView:**
- DPS sector names are more granular (26 PSX-specific categories like "CEMENT" and "AUTOMOBILE ASSEMBLER") vs. TradingView's 19 broader categories
- PSX investors recognize DPS sector names from the exchange's own classification

**How we combine both:**
- TradingView job (`job_refresh_tv_data`) runs every 5 minutes, upserts all 478 stocks into `psx_profile`
- DPS `/symbols` endpoint also writes to `psx_profile` (now overwritten by TradingView)
- Result: 19 TradingView sectors covering 96.5% of stocks; DPS sectors for the remaining 17 stocks not in TV

**Trade-off:** TradingView sector categories are broader than PSX's own classification. A stock like "Lucky Cement" shows as "Non-Energy Minerals" rather than "CEMENT" which PSX investors expect. Future: we could maintain a mapping table from TV → DPS sector names if granularity is needed.

---

### 30. Why We Use Direct Fetch (Not createServerFn) for Local Dev

**Decision:** All PSX data hooks (`usePsxLiveMarket`, `usePsxHistory`, etc.) call the Python API directly via browser `fetch()` instead of going through TanStack `createServerFn`.

**Context:**
The original architecture used `createServerFn` to proxy PSX API calls through the Vite dev server, hiding the Python API URL from the browser. During local development, the `createServerFn` layer consistently failed to reach the Python API — the browser → Vite dev → Python chain added latency and failure points with no debuggability.

**Why direct fetch:**
- **Reliable:** Browser → Python API directly, no intermediate Node.js proxy. Every call succeeded immediately after removing `createServerFn`.
- **Debuggable:** `F12 → Network` tab shows every API call, its timing, and the exact JSON response
- **CORS already enabled:** The Python FastAPI has `allow_origins=["*"]` — no security issue for local dev
- **Zero code change for production:** In production, Vercel's edge functions would proxy anyway — the `psx/client.ts` base URL is a single constant to swap

**Trade-off:** The Python API URL (`localhost:8000`) is exposed in the browser's network tab. For production deployment, we'd switch back to `createServerFn` or use environment-specific build configuration. The `psx/functions.ts` server functions are kept for production use.

---

### 31. Why PSX Routes Bypass Auth in Local Dev

**Decision:** PSX routes (`/psx`, `/stock/*`) do not require Supabase authentication during local development.

**Context:**
The existing `AuthGate` component in `__root.tsx` redirects all non-public routes to `/auth`. Since the Python API is a separate process with no auth integration, running the PSX module required either a mock user or bypassing auth entirely.

**Why bypass:**
- **PSX data is public:** Market prices, OHLCV, sectors, and announcements have no user-specific data. Auth is only needed for watchlist/alerts which gracefully fall back to local state when not authenticated.
- **Faster iteration:** No login → no session management → instant page load for testing
- **AppShell preserved:** PSX routes still render with the navigation sidebar and header (unlike landing page which is full-width)

**Implementation:** Added `isPsx` check in `AuthGate` that skips the redirect. PSX routes render with `AppShell` but without the loading spinner blocking on `!user`. When a user is not authenticated, watchlist operations use local React state and price alert creation shows "Please log in" message.

**Trade-off:** Production will re-enable auth for PSX routes (or keep them public since the data itself is public). The watchlist and alert features already handle auth gracefully via `supabase.auth.getSession()` checks in `useWatchlist()`.

---

### 32. Why Two Categories of Tables: User-Owned (Linked to Auth) vs Standalone (Public)

**Decision:** Tables are split into two categories — user-owned tables that FK to `auth.users`, and standalone public tables with no user ownership.

**Why two categories:**

- **User-owned tables** (watchlist, alerts, portfolios, holdings, finance_* , ai_*, notifications, billing) have a `user_id` FK to `auth.users(id) ON DELETE CASCADE`. This enables RLS: every row belongs to exactly one user, and RLS enforces `auth.uid() = user_id` on every SELECT/INSERT/UPDATE. When a user deletes their account, all their personal data cascades away automatically.

- **Standalone public tables** (psx_market_snapshot, psx_ohlcv, psx_fundamentals, psx_profile, psx_announcements, psx_dividends, psx_index_eod, psx_ticks, psx_signals, fx_rates, plan_features, feature_flags) have no `user_id` because the same row is shared across all users. Every user reads the same price for HBL at the same instant. FKing these to auth.users would create N redundant copies of every price row — one per user — which is wasteful and impossible to keep consistent.

**How Supabase enforces the split:**

```sql
-- User-owned: RLS checks user_id
CREATE POLICY "Users own their watchlist" ON user_watchlist
  FOR ALL TO authenticated
  USING (user_id = auth.uid());

-- Public: RLS allows everyone
CREATE POLICY "Public read market snapshot" ON psx_market_snapshot
  FOR SELECT USING (true);
```

**Why not a hybrid approach** (e.g., user-scoped copies of market data):
- Every user having their own copy of 495 stock prices would be 495 × N users rows — completely unsustainable.
- Supabase RLS is designed for exactly this pattern: public tables for shared data, user_id-scoped tables for private data.

---

### 33. Why `psx_market_snapshot` Uses `bigint id PK` + `UNIQUE(symbol)` (Not `text symbol PK`)

**Decision:** The market snapshot table uses a surrogate `bigint GENERATED BY DEFAULT AS IDENTITY` primary key, with `UNIQUE(symbol)` for the business key.

**Why not `symbol` as PK:**
- **Supabase Realtime requires a single-column PK** for `postgres_changes` subscriptions. The JS SDK's `on('postgres_changes', {table: 'psx_market_snapshot'})` works best with a simple integer PK. A `text` PK works technically but `bigint` is more efficient for the WAL (Write-Ahead Log) that Realtime reads.
- **Symbols can theoretically change** — if PSX renames a ticker (e.g., `PIOC` → `PIBTL`), the text PK would need to cascade to all child tables. With a surrogate `id`, only the `symbol` column updates.
- **Performance:** `bigint` PKs are faster for B-tree index traversal than `text` PKs at scale (495 rows × 10+ years of history = millions of index entries).
- **Supabase convention:** Every auto-generated model in the Supabase JS SDK expects an `id` column. Surrogate PKs are the standard pattern for PostgREST.

**Why `UNIQUE(symbol)` still exists:**
- The symbol is the business identifier — it's what users and the Python service use to look up stocks.
- The unique constraint ensures no duplicate symbols, which is the same guarantee a PK gives.
- It enables `ON CONFLICT (symbol) DO UPDATE` for the Python service's bulk upserts.

**Trade-off:** All child tables (`psx_ohlcv`, `psx_announcements`, etc.) reference by `symbol` (text), not by the surrogate `id`. This means the FK is not a direct reference to the PK, which prevents us from declaring a real FK constraint. The trade-off is accepted because the app-layer logic ensures referential integrity, and the symbol-based join is idiomatic PSX data modeling.

---

### 34. Why v1 and v2 Tables Coexist (`psx_watchlist` + `user_watchlist`, `psx_alerts` + `price_alerts`)

**Decision:** Both the old (v1) and new (v2) versions of watchlist and alert tables exist in the database. v1 tables won't be dropped until Phase 1 cleanup confirms no code path still depends on them.

**Why v1 exists:**
- The initial schema (migration `20260706120000_psx_module.sql`) created `psx_watchlist` and `psx_alerts` with composite PKs and old column names (`threshold` instead of `price`, a separate `type` column).
- These tables were already deployed to production (the Supabase project at `gmonfgxmjgzipnbhgimv`) when we decided the schema needed improvement.

**Why v2 was created (not just v1 altered):**
- **Breaking column changes:** `psx_alerts.type` column was removed (redundant — the type is implicit in the symbol and condition). `psx_alerts.threshold` was renamed to `price` with a different precision (`NUMERIC(14,2)` vs `NUMERIC(12,4)`). Altering existing columns with data in production is risky.
- **Primary key change:** `psx_watchlist` uses a composite PK `(user_id, symbol)`. The new `user_watchlist` uses a surrogate `bigint id` PK to match the pattern used elsewhere in the app and simplify the Supabase JS SDK operations.
- **CHECK constraint addition:** `price_alerts.condition` has a `CHECK IN ('above','below','cross_above','cross_below')` constraint. The old `psx_alerts.condition` has no CHECK — it accepts free-form text.

**Migration plan (Phase 1):**
1. Verify no code path reads from v1 tables (frontend hooks use `user_watchlist` and `price_alerts` only).
2. Run `DROP TABLE IF EXISTS psx_watchlist, psx_alerts CASCADE`.
3. Regenerate Supabase types.

**Trade-off:** Both versions occupy disk space (negligible for watchlists) and create confusion when reading the schema. The v1 tables are clearly marked in the ERD with `_v1` suffix and documentation explaining their superseded status.

---

### 35. Why Child Tables Don't Have Explicit FK Constraints to `psx_market_snapshot`

**Decision:** Tables that reference stock symbols (`psx_ohlcv`, `psx_announcements`, `psx_dividends`, `psx_ticks`, `psx_signals`, `user_watchlist`, `price_alerts`, `psx_holdings`) do NOT have `FOREIGN KEY (symbol) REFERENCES psx_market_snapshot(symbol)` declared in SQL. Referential integrity is enforced at the application layer by the Python service.

**Why not:**
- `psx_market_snapshot` uses `bigint id PK` with `UNIQUE(symbol)` (not `PRIMARY KEY (symbol)`). Postgres allows FK references to a UNIQUE column, but the target column must be in the same table as the PK's unique constraint — which it is. Technically `REFERENCES psx_market_snapshot(symbol)` would work, but:
- **Circular dependency risk:** The Python service bulk-upserts `psx_ohlcv` rows before the corresponding snapshot row may exist (backfill scenario). An FK constraint would reject the insert.
- **Staging data:** Announcements and dividends may reference symbols not yet in the active trading list (delisted stocks with pending dividends, old announcements). An FK would prevent inserting these.
- **Performance:** FK checks add overhead on every INSERT/UPDATE. At our scale (495 stocks, ~2M OHLCV rows) the overhead is small, but it adds up during the nightly backfill of all-history bars.

**How integrity is maintained:**
- The Python service always upserts `psx_market_snapshot` rows before any dependent data (the cache layer writes snapshot → history → fundamentals in that order).
- The `UNIQUE(symbol)` constraint on `psx_market_snapshot` is present, so there's a defensive assertion — just not a formal FK.
- Application-level validation in the Pydantic models ensures every symbol written to child tables exists in the snapshot first.

**Recommended cleanup (Phase 1):** Add explicit FKs now that the data pipeline is stable. The migration would be:
```sql
ALTER TABLE psx_ohlcv ADD FOREIGN KEY (symbol) REFERENCES psx_market_snapshot(symbol);
ALTER TABLE user_watchlist ADD FOREIGN KEY (symbol) REFERENCES psx_market_snapshot(symbol);
-- ... etc for all 12 child tables
```

---

### 36. Why `profiles.id` = `auth.users.id` (1:1 with Auth, Not a Separate Serial PK)

**Decision:** The `profiles` table uses `id UUID PRIMARY KEY` which is both the PK and the FK to `auth.users(id)`. There is no separate serial `id` column. This is 1:1 with the auth user.

**Why:**
- **No duplicate identity** — the user's identity is their `auth.users.id`. Having a separate `profiles.id` serial creates two identifiers for the same entity, which is confusing and requires a join or mapping to reconcile.
- **Trigger ensures creation** — `handle_new_user()` fires on `AFTER INSERT ON auth.users`, creating a `profiles` row with `NEW.id`. This guarantees every auth user has exactly one profile row.
- **CASCADE handles deletion** — `ON DELETE CASCADE` means deleting the auth user deletes the profile. No orphaned profile rows.
- **Simpler RLS** — RLS on profiles checks `auth.uid() = id` (same as other user-owned tables' `auth.uid() = user_id`). No extra join on `profiles.user_id = auth.uid()`.

**Why NOT a serial PK with user_id FK:**
- This is the pattern used by every other user-owned table (`user_watchlist`, `price_alerts`, `finance_*`, etc.). Those tables need a serial PK because a user can have many rows (many watchlist entries, many transactions). Profiles is 1:1 — one profile per user — so the PK is naturally the user's ID.
- Having both `id SERIAL PK` and `user_id UUID FK UK` would work, but it adds an unnecessary column and index. The `id` column would never be used for lookups (everything queries by `user_id`).

**Trade-off:** Joins from profiles to other tables use `profiles.id` instead of a consistent `user_id` column name. This is fine because the 1:1 relationship means `profiles.id` IS the user's ID.

---

### 37. Why `psx_index_eod` Uses Composite PK (Not Surrogate id)

**Decision:** `psx_index_eod` uses `(code, date)` as a composite primary key. No surrogate `bigint id` column.

**Why not `bigint id PK`:**
- The natural key `(code, date)` is guaranteed unique — there is exactly one KSE-100 closing value per trading day. Adding a surrogate `id` column would introduce a meaningless identifier that's never used for lookups.
- The table has no child tables referencing it, so there's no need for a PK that FK constraints can target.
- The composite PK directly enforces the business rule: "one row per index per day." A unique constraint would do the same, but making it the PK is more semantically correct.

**Why other PSX tables use surrogate PKs:**
- `psx_market_snapshot` — needs `id` for Supabase Realtime compatibility.
- `psx_ohlcv` — uses `bigint id PK` with `UNIQUE(symbol, date)` because the PK is used for FK references (logical) and the composite natural key is large (symbol text + date = ~16 bytes + overhead vs 8-byte bigint).
- `psx_announcements` — uses `text id PK` because the source system (DPS) provides a unique announcement ID. Since the source system's ID is already suitable as a PK, adding a surrogate is unnecessary indirection.

---

### 38. Why `plan_features` Uses `text PK` (Not Serial id)

**Decision:** The `plan_features` table uses `plan TEXT PRIMARY KEY` — the plan name itself is the PK.

**Why:**
- **Plans are few and stable** — `Free`, `Pro`, `Premium`, `Admin`. Adding new plans is a rare event (maybe once per year). A serial ID adds no value for 4-5 rows.
- **Readability** — `SELECT * FROM plan_features WHERE plan = 'Pro'` is self-documenting. `SELECT * FROM plan_features WHERE id = 2` requires a lookup to understand which row is being queried.
- **No FK to other tables** — the `profiles.plan` column references the plan name, not an ID. Using the plan name as the PK makes the FK readable without a join: `profiles.plan REFERENCES plan_features(plan)`.

**Why other dimension tables use serial PKs:**
- `finance_categories` — uses `bigint id PK` because categories are user-created (many per user) and referenced by `finance_transactions.category_id`. A text name would be too large and variable for efficient FK joins on the high-volume transactions table.

---

### 39. Why psx_ticks Uses `bigint id PK` + `REPLICA IDENTITY FULL` (For Realtime)

**Decision:** The `psx_ticks` table uses a `bigint GENERATED BY DEFAULT AS IDENTITY` primary key and has `ALTER TABLE psx_ticks REPLICA IDENTITY FULL`.

**Why `REPLICA IDENTITY FULL`:**
- Supabase Realtime broadcasts row changes by reading the WAL (Write-Ahead Log). To reconstruct the full row for broadcast, it needs to know which columns to capture.
- The default `REPLICA IDENTITY DEFAULT` uses the PK only. For a table with `bigint PK`, the WAL only contains the `id` column — not the `symbol`, `price`, `volume`, or `time`.
- `REPLICA IDENTITY FULL` tells Postgres to write all columns to the WAL. This makes Realtime broadcasts include the full tick data (price, symbol, volume) instead of just `{id: 12345}`.

**Why not use `REPLICA IDENTITY USING INDEX (symbol, time)`:**
- A composite index on `(symbol, time DESC)` exists (for query performance), but using it as the replica identity would prevent upserts from updating it correctly. `FULL` is simpler and works for all operations (INSERT, UPDATE, DELETE). The WAL overhead is acceptable — ticks are small rows (< 200 bytes).

---

### 40. Security Incident (2026-07-07) — Service-Role Key Leak + Remediation

**What happened:** A `.env` file containing the Supabase `service_role` key (full admin access) was committed to git in commit `f605ac4` ("Changes", way back in the project's history). It was eventually removed in commit `ac66480` ("Delete .env") during a recent cleanup pass, but the secret value remained in the git history of every clone, fork, and CI cache.

**What was leaked:** The `service_role` JWT for Supabase project `gmonfgxmjgzipnbhgimv`. This key has full read/write access to all 16 tables in the database, bypassing RLS. It could have been used by anyone with read access to the GitHub repo (or a stale clone) to:
- Read every user's watchlist, alerts, portfolios, holdings.
- Modify or delete any row in any table.
- Issue queries as any role (authenticated, anon, service_role).

**Root cause:** The project's `.gitignore` did **not** include `.env`. The leak was the inevitable result of the omission — at some point a developer (or a tool) added the file, and git happily tracked it.

**What we did (Phase 0):**
1. **Rotated both keys** in the Supabase Dashboard — created a new `sb_secret_xxx` (replaces the legacy `service_role` JWT) and a new `sb_publishable_xxx` (replaces `anon`).
2. **Added `.env` to `.gitignore`** with comprehensive coverage (root + `services/psx-api/`, both `*.env` and `*.env.*` patterns, with `.env.example` allowlist).
3. **Updated `services/psx-api/app/config.py`** to use the new key name (`SUPABASE_SECRET_KEY`) with a legacy fallback to `SUPABASE_SERVICE_ROLE_KEY` for backward compat.
4. **Updated both `.env.example` files** to document the new key names and remove stale project IDs.
5. **Smoke-tested the API** with the new key — confirmed read+write+delete work end-to-end.
6. **Wrote a new RLS WITH CHECK migration** (`20260707100000_rls_with_check_fix.sql`) closing a separate but related vulnerability: 4 user-data tables (`psx_watchlist`, `psx_alerts`, `psx_portfolios`, `psx_holdings`) had `USING` clauses but no `WITH CHECK` clauses, meaning an authenticated user could UPDATE a row to reassign ownership to another user.
7. **Regenerated `src/integrations/supabase/types.ts`** via `npx supabase gen types typescript` so the stale (4/16 table) types file is replaced with the canonical schema-derived types.
8. **Updated `AGENTS.md`** to document the regen command and list all 16 tables.

**What's still pending (Phase 0 follow-up):**
- **Scrub git history** with `git filter-repo --path .env --path services/psx-api/.env --invert-paths` and force-push. This rewrites all commit hashes. Solo project, so impact is limited to the user. Anyone with an old clone must re-clone.
- **Apply the RLS WITH CHECK migration** via Supabase SQL editor. Run the commented test cases in the migration file to verify the fix.

**Residual risk (post-remediation):**
- GitHub's cached view of the old commits may retain the leaked key for up to 24 hours after the force-push. If this is a concern, also request a GitHub cache purge via support.
- Any third-party CI or backup system that cloned the repo before the scrub retains the old history. Audit any such systems.
- **The legacy `service_role` and `anon` JWTs in the Supabase project were NOT revoked.** They remain valid until 2036-07-07 (10-year JWT expiry). Rotating to the new `sb_secret_xxx` key does not invalidate the old JWTs — they are separate keys. The old JWTs were verified still-active on 2026-07-07 against the live Supabase project. **Decision (2026-07-07):** accepted as residual risk. Rationale: the repository is private and slated for deletion in the near future, so the attack surface for the leaked JWT is limited to anyone with access to the private repo or this conversation transcript. If the repo were public or long-lived, the project would need to migrate to a new Supabase project to fully close the leak.

**Why this approach instead of just rotating:**
- Rotation alone is necessary but not sufficient. If a leaked key is rotated but git history isn't scrubbed, a future secret scan by GitHub, a third-party auditor, or an attacker who finds the old history could still surface the (now-invalid) JWT and gain insight into the JWT format/issuer. Scrubbing makes the leak unrecoverable from the repo itself.
- The RLS WITH CHECK fix is a separate vulnerability, but discovered during the same review pass. Closing both at once is more efficient than two separate security sprints.

---

**Update 2026-07-07 (final state):** The rotation was partially reverted per user decision. The codebase uses a 4-key convention where each env var name holds its semantically corresponding key:

| Env var name | Key used |
|---|---|
| `*_PUBLISHABLE_KEY` | New `sb_publishable_aJUwvjC4...vfE1` |
| `*_SECRET_KEY` | New `sb_secret_BgTyaS-9v...C6AU` (server-side) |
| `*_ANON_KEY` | Old anon JWT `DT0asnB-2g...C0U` |
| `*_SERVICE_ROLE_KEY` | Old service_role JWT `6KLA_ZOkp...uLU` |

**Rationale:** The old service_role JWT is already publicly exposed and not revocable through the Supabase Dashboard. Rotating to a new key does not invalidate the old one. The user chose to use the new secret key for the renamed `SUPABASE_SECRET_KEY` slot (where the leaked value was never the secret key) while keeping the legacy `SUPABASE_SERVICE_ROLE_KEY` env var mapped to the old JWT (since that env var name historically held the leaked value). Equivalent security since the leaked JWT was already public. The new `sb_publishable_` key is used for the renamed `*_PUBLISHABLE_KEY` slot. The old anon JWT is used in the `*_ANON_KEY` slot, which holds a public-by-design key.

**Code impact:** `services/psx-api/app/config.py:supabase_service_key` no longer falls back through `SUPABASE_PUBLISHABLE_KEY` (which now holds a client-side key under the new convention) — it falls back from `SUPABASE_SECRET_KEY` to `SUPABASE_SERVICE_ROLE_KEY` only.

---

### 41. Why Hybrid Data Access: Supabase REST + SQLAlchemy Core (Not Full ORM, Not Status Quo)

**Decision:** Add SQLAlchemy Core to the Python service for complex queries, joins, and aggregations. Keep Supabase REST for the high-throughput bulk-upsert path and simple lookups. Keep Supabase JS on the frontend. Do NOT use a full ORM (SQLAlchemy ORM, Prisma, Drizzle).

**Context:**
The project had no ORM. Python data access was entirely through the Supabase REST client (`postgrest-py`), making HTTP calls to PostgREST. This is fast for bulk writes (~3s for 495 rows via bulk upsert) but produces untyped `dict` results and makes complex queries (CTEs, window functions, multi-table joins) awkward.

The user needed "proper architecture" for an internship project. The question was whether to add an ORM, and if so, which one.

**Why SQLAlchemy Core (not full ORM):**
- **Bulk write performance preserved:** Supabase REST does 495 rows in 3s via a single HTTP POST with `on_conflict=DO UPDATE`. SQLAlchemy ORM would be ~10s per full refresh (row-to-object mapping overhead). Prisma would be ~30s (no native bulk upsert). SQLAlchemy Core avoids object mapping entirely — it's just a query builder.
- **No Realtime disruption:** Supabase Realtime (`postgres_changes` WAL subscriptions) is PostgREST-specific. The frontend's `usePsxRealtime()` hook uses `supabase.channel('psx:market').on('postgres_changes', ...)` — this stays unchanged.
- **No RLS bypass:** Full ORMs bypass PostgREST entirely (they connect directly to Postgres). That means RLS is bypassed — you'd need the service_role key in the ORM client, which is a security downgrade. SQLAlchemy Core also bypasses PostgREST, but it's only used for complex reads, not for writes that need RLS enforcement.
- **Right tool per job:** The project has two distinct query patterns: (1) high-throughput bulk writes (market refresh, 495 rows every 5s) and (2) complex analytical queries (Phase 4 Finance aggregations, Phase 5 Portfolio P&L). Pattern 1 is best served by REST. Pattern 2 benefits from a typed query builder.

**Why not Prisma or Drizzle (TypeScript):**
- Both would need to replace the Supabase connection string entirely — they connect to Postgres directly, not through PostgREST. This breaks Supabase Realtime and RLS.
- Prisma handles bulk upserts poorly (one row at a time, or verbose `executeRawUnsafe` workarounds).
- The frontend already has a working data-access layer (React Query + Supabase JS). Rewriting it provides negligible benefit for significant disruption.

**Why not the status quo (no SQLAlchemy):**
- Complex joins in Phase 4 Finance (e.g., transactions + categories + users for spending analysis) would require either multiple REST calls with client-side joining or raw SQL strings with no type safety.
- Analytics queries (window functions, CTEs for portfolio P&L) are near-impossible through REST. SQLAlchemy Core handles them naturally.
- Having a second query path makes testing easier — you can mock the engine instead of mocking HTTP calls.

**Architecture name:** The pattern is formally documented as **"Layered Architecture with BaaS-Backed Microservices and Read-Through Cache"** — see `docs/superpowers/specs/2026-07-08-architecture-orm-design.md`.

**What was added:**
- `services/psx-api/app/db/sqlalchemy.py` — async engine, session factory, connection helper
- `services/psx-api/app/db/orm.py` — table definitions for all 17 tables (auto-mapped)
- `services/psx-api/pyproject.toml` — added `sqlalchemy[asyncio]>=2.0`
- `services/psx-api/tests/test_sqlalchemy_queries.py` — sanity tests

**Update 2026-07-08 (post-execution):**
The direct Postgres connection (`db.gmonfgxmjgzipnbhgimv.supabase.co:5432`) is unreachable from the local network (IPv6 only). The connection was switched to use **Supavisor transaction pooler** (`aws-1-ap-southeast-1.pooler.supabase.com:6543`) with user format `postgres.gmonfgxmjgzipnbhgimv`. Key adjustments:
- **Pooler host** and **user** are configured via `SUPABASE_POOLER_HOST/PORT/USER` in `.env` and `app/config.py`
- **NullPool** is used (no client-side pooling) because the pooler handles pooling server-side. Client-side pooling caused "another operation is in progress" errors from asyncpg.
- **`statement_cache_size=0`** disables prepared statements because pgbouncer transaction mode does not support them (avoids `DuplicatePreparedStatementError`).
- **Auto-reflection** replaced hand-written table definitions in `orm.py` — the schema is reflected from the live DB on first access via `ensure_reflected()`. This eliminates schema drift and makes `orm.py` zero-maintenance.
- An example endpoint `/api/market/sectors/avg` demonstrates SQLAlchemy Core in production code: a typed join between `psx_market_snapshot` and `psx_profile` computing per-sector average change %. The test passes.
- 7 out of 8 sanity tests pass (1 skipped: `fx_rates` table not yet created — Phase 5).

**What stayed the same:**
- `services/psx-api/app/db/supabase.py` — unchanged (still used for bulk writes + simple lookups)
- `services/psx-api/app/services/cache.py` — uses Supabase REST (the 3s path)
- All frontend code (`src/`) — unchanged
- Supabase schema, RLS policies, Realtime publications — unchanged

**Trade-off accepted:** The Python service now has two database access paths (REST + SQLAlchemy Core). Developers must choose the right tool per query. Bulk writes always go through REST. Complex reads go through SQLAlchemy. This is a documented convention, not a source of confusion, because the two patterns serve distinct, non-overlapping use cases.
