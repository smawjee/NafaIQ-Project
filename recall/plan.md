# PSX Data Sources & Integration Plan

## Overview

This document describes all publicly available data sources for Pakistan Stock Exchange (PSX) market data, their formats, how to access them, and how they can be used to build a trading indicator app (buy/sell/hold signals).

---

## Data Sources

### Source 1: PSX Data Dissemination Portal (DPS) — Primary

**Base URL:** `https://dps.psx.com.pk`

The official PSX data portal. Free, no API key required. Data is **15+ minutes delayed**. Returns HTML, JSON, or HTML fragments depending on endpoint.

#### Endpoints

| Endpoint | Method | Returns | Description |
|---|---|---|---|
| `/market-watch` | GET | HTML table | ~486 rows: symbol, sector, LDCP, open, high, low, current, change, change%, volume |
| `/symbols` | GET | JSON array | 1048 symbols: `{symbol, name, sectorName, isETF, isDebt, isGEM}` |
| `/historical` | POST | HTML fragment | Full OHLCV history per symbol (~2500 rows). Body: `symbol=SYM` |
| `/company/{SYMBOL}` | GET | HTML | Company profile, sector, listed shares, free float, financial tables, P/E (TTM), EPS, P/B, financial statements (annual + quarterly) |
| `/company/payouts` | POST | HTML fragment | Dividend history. Body: `symbol=SYM` |
| `/announcements` | POST | HTML fragment | Corporate announcements (50 per page). Body: `type=C&offset=0&count=50` |
| `/timeseries/eod/{INDEX}` | GET | JSON | Index EOD time series: `{data: [[timestamp, close, volume], ...]}`. Indexes: `KSE100`, `KSE30`, `ALLSHR` |

#### Usage Notes

- Headers required: `User-Agent: Mozilla/5.0`, `Accept-Language: en-PK,en;q=0.9`
- POST requests need `Content-Type: application/x-www-form-urlencoded; charset=UTF-8` and `X-Requested-With: XMLHttpRequest`
- HTML parsing needed for most endpoints (use BeautifulSoup or similar)
- Rate-limit: max ~2 concurrent requests recommended
- The `/historical` endpoint returns ~10 years of daily OHLCV data per symbol

#### Indicator-Relevant Data

- **Price data** (for computing RSI, MACD, SMA, EMA, Bollinger Bands, ATR): from `/historical` (OHLCV history) and `/market-watch` (current price)
- **Volume data** (for volume-based indicators): from `/historical` and `/market-watch`
- **Fundamentals** (for P/E, P/B, EPS, ROE screener filters): from `/company/{SYMBOL}`
- **Dividend history** (for dividend yield): from `/company/payouts`
- **Index data** (for beta, relative strength): from `/timeseries/eod/KSE100`
- **Sector data** (for sector rotation analysis): from `/symbols` (symbol→sector mapping) + `/market-watch` (current prices per symbol)

---

### Source 2: AhleTrade HTTP Feed — Real-Time

**Base URL:** `http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher`

Real-time PSX market feed. No delay, no API key. Used internally by psxterminal.com. HTTP long-poll; returns pipe-delimited text.

#### Endpoints

| Parameter | Description | Response Format |
|---|---|---|
| `action=Market&identifier=PriceVolume&market=REG&symbol=SYM` | L1 bid/ask snapshots | `HH:MM:SS;bid;ask;\|` |
| `action=Market&identifier=BuySell&market=REG&symbol=SYM` | Trade tape (time & sales) | `HH:MM:SS;price;vol;\|` |

#### Markets

`REG` (Regular), `FUT` (Futures), `IDX` (Index), `ODL` (Odd Lot), `BNB` (Bills & Bonds)

#### Usage Notes

- Poll repeatedly for real-time updates (there is no push WebSocket)
- The feed returns ALL data for the current trading session each time you poll
- Deduplicate locally (the feed includes heartbeats and repeats)
- Python library available: `pip install psx-terminal` (by nordixsoft)

#### Indicator-Relevant Data

- Real-time price ticks for intraday indicators
- Trade volume for volume spike detection
- Bid/ask spread analysis
- **Not suitable for historical analysis** — only current session data

---

### Source 3: psxterminal.com — Aggregated UI

**Base URL:** `https://psxterminal.com`

A SvelteKit frontend that aggregates data from both DPS and AhleTrade. No public API exists — all endpoints at `/api/*` return 404. The data on the website can be scraped, but it's easier and more reliable to use DPS directly.

#### Features on the Website (no API)

| Page | Data Available |
|---|---|
| `/market` | Live market breadth, gainers/losers, volume leaders |
| `/sectors` | Sector heatmap (color-coded by performance, box-size by volume) + sector table (volume, value, winners/losers, avg change %) |
| `/symbol/{SYM}` | Stock quote, chart, fundamentals, financials |
| `/research` | Advanced screener with composite scoring |
| `/financials/{SYM}` | Income statement, balance sheet, cash flow |

---

### Source 4: sharozhaseeb/psx MCP Server — Pre-Built Solution

**GitHub:** `https://github.com/sharozhaseeb/psx`

An MCP (Model Context Protocol) server that wraps all DPS data sources into 63 tools across 5 analytics tiers. Pre-computes indicators, screener scores, sector rotation, risk metrics, and more.

#### Architecture

```
psx-mcp/
├── server.py              # FastMCP entrypoint
├── src/psx_mcp/
│   ├── psx_client.py      # DPS HTTP client (async, httpx + BeautifulSoup)
│   ├── cache.py           # SQLite cache (data/psx.db)
│   ├── indicators.py      # RSI, MACD, SMA, EMA, Bollinger, ATR, etc.
│   ├── screener.py        # Multi-criteria screener
│   ├── ranking.py         # Sector ranking, universe ranking
│   ├── risk.py            # Sharpe, volatility, max drawdown
│   ├── risk_extended.py   # Sortino, Calmar, VaR, CVaR, capture ratios
│   ├── beta.py            # OLS beta vs index
│   ├── backtest.py        # Simple backtesting engine
│   ├── quality.py         # Quality score (ROE + EPS trend)
│   ├── cross_section.py   # Cross-sectional z-score/percentile ranks
│   ├── alerts.py          # Alert rules (price, indicator, volume, fundamental)
│   ├── symbols.py         # Symbol search, universe management
│   ├── watchlist.py       # Watchlist management
│   ├── news.py            # News RSS feeds
│   ├── events.py          # Upcoming corporate events
│   └── models.py          # Data models (Bar, Quote, Fundamentals, etc.)
```

#### Key Tools for Indicator App

| Tool | What it gives you |
|---|---|
| `compute_indicators` | RSI(14), MACD, SMA(20/50/200), EMA, Bollinger Bands, ATR(14), volume z-score, Donchian channels, ADX(14), Stochastic (%K/%D), OBV, Williams %R(14) |
| `get_quote` | Latest cached quote + 52-week high/low |
| `get_history` | Daily OHLCV from cache |
| `get_market_summary` | KSE-100 / KSE-30 / All-Share snapshot |
| `get_top_movers` | Gainers, losers, volume leaders |
| `get_fundamentals` | EPS, P/E, P/B, dividend yield, payout ratio, ROE |
| `get_sector_summary` | Sector-level: member count, breadth, median PE, top/bottom 5 |
| `rank_sectors` | Sector rotation table by avg change %, breadth, median PE |
| `screen_symbols` | Filter by sector, PE, EPS, price, RSI, SMA stack, volume, ROE, P/B, dividend yield, Sortino, Calmar, max DD |
| `compute_4quadrant_score` | Value / Quality / Momentum / Trend composite score |
| `compute_risk_metrics` | Annualized volatility, Sharpe ratio, max drawdown |
| `compute_beta` | OLS beta vs KSE-100 |
| `compute_relative_strength` | RS vs KSE-100 |
| `backtest_simple` | Smoke-test backtest with screener filter |
| `get_full_analysis` | One-shot research dashboard (all of the above combined) |

#### Running the Server

```bash
cd psx-mcp
uv sync --extra dev
.\run-psx-mcp.ps1
# Listens on http://127.0.0.1:8765/sse
```

---

### Source 5: TradingView Scanner API — Sector & Market Data (NEW)

**Base URL:** `https://scanner.tradingview.com/pakistan/scan`

**Method:** POST (JSON body)

**Auth:** None (public, no API key)

**Data:** Real-time scanner for all PSX stocks — 478 symbols with price, change%, volume, **sector**, and **market cap**.

This is the data source behind TradingView's PSX heatmap widget and Chase Securities' embedded KSE-100 Heatmap. It provides complete sector classification for every actively traded PSX stock.

#### Request

```json
POST https://scanner.tradingview.com/pakistan/scan
Content-Type: application/json

{
  "filter": [{"left": "type", "operation": "equal", "right": "stock"}],
  "columns": ["name", "close", "change", "change_abs", "volume", "sector", "market_cap_basic"],
  "sort": {"sortBy": "volume", "sortOrder": "desc"},
  "range": [0, 500]
}
```

#### Response

```json
{
  "totalCount": 478,
  "data": [
    {
      "s": "PSX:TPLP",
      "d": ["TPLP", 12.54, 7.73, 0.90, 66770551, "Finance", 6531051162]
    },
    ...
  ]
}
```

Column order (index in `d` array):
0. name
1. close price
2. change %
3. change absolute
4. volume
5. **sector** (TradingView classification)
6. market cap

#### TradingView Sectors (19 categories)

| Sector | Count | Examples |
|---|---|---|
| Finance | 102 | HBL, UBL, MCB |
| Process Industries | 177 | LOTCHEM, GCIL |
| Non-Energy Minerals | 32 | LUCK, DGKC |
| Consumer Non-Durables | 39 | NESTLE, COLG |
| Producer Manufacturing | 25 | PAEL, INIL |
| Utilities | 21 | KEL, HUBC |
| Health Technology | 13 | SEARL, GLAXO |
| Consumer Durables | 17 | BATA, ATBA |
| Energy Minerals | 9 | OGDC, PPL, POL |
| Commercial Services | 8 | PTC, NETSOL |
| Distribution Services | 7 | CNERGY |
| Transportation | 7 | PIA, PNSC |
| Technology Services | 5 | SYS, NETSOL |
| Communications | 5 | PTCL |
| Consumer Services | 4 | PSMC |
| Industrial Services | 2 | SNGP, SSGC |
| Electronic Technology | 2 | TPL |
| Retail Trade | 2 | — |
| Health Services | 1 | — |

#### Integration in NafaIQ

Used as the primary sector data source via `app/scrapers/tradingview.py`:
- `TradingViewScraper.fetch_market_data()` — returns all 478 stocks with sectors
- `job_refresh_tv_data` — scheduled every 5 minutes, upserts into `psx_profile`
- Overwrites DPS sector data — TradingView covers 478/495 stocks vs DPS's 181
- `GET /api/sectors` aggregates snapshot data by TradingView sector

#### Notes
- TradingView sectors are broader than PSX's own 26-sector classification
- Free, no auth, no observed rate limits
- Same data powers `s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js` (used by Chase Securities)
- Recommended columns also available: `market_cap_basic`, `pre_change`, `perf_w`, `perf_1m`, `perf_3m`, `perf_6m`, `perf_y`, `beta_5_year`, etc.

### Option A: Use the MCP server directly (recommended for quickest path)

```
┌─────────────┐     MCP/SSE     ┌──────────────┐     HTTP     ┌──────────────┐
│ Your App     │ ◄────────────► │ psx-mcp      │ ◄──────────► │ dps.psx.com.pk│
│ (any client) │                │ (local server)│              └──────────────┘
└─────────────┘                └──────────────┘
```

- Run the MCP server locally
- Call `refresh_market` to pull fresh data
- Call `compute_indicators` with list of indicators you need
- For buy/sell logic: call `screen_symbols` with your criteria or build custom logic on top of the indicators
- Use `check_alerts` for automated signal detection

### Option B: Build directly on DPS + AhleTrade

```
┌─────────────┐     HTTP     ┌──────────────┐
│ Your App     │ ◄─────────► │ dps.psx.com.pk│
│ (custom)     │              └──────────────┘
│              │     HTTP     ┌──────────────────┐
│              │ ◄─────────► │ feed.ahletrade.com│
└─────────────┘              └──────────────────┘
```

- Use DPS for historical data (cache locally in SQLite)
- Use AhleTrade for real-time price feeds
- Compute indicators yourself using pandas/numpy
- Build your own screener, alert system, and backtester

### Option C: Hybrid

- Use the MCP server for all DPS data (historical, fundamentals, sectors)
- Add AhleTrade feed separately for real-time updates
- Extend the MCP server with custom tools for your specific indicator logic

---

## Data Flow for Buy/Sell/Hold Signals

```
1. Refresh Data
   ├── Call refresh_market() → market snapshot
   ├── Call refresh_history(SYM) → OHLCV history per symbol
   └── Call refresh_fundamentals() when needed

2. Compute Indicators
   ├── compute_indicators(symbol, [rsi14, sma20, sma50, sma200, macd, bollinger, atr14])
   ├── Optional: compute_4quadrant_score(symbol)
   └── Optional: compute_risk_metrics(symbol)

3. Generate Signal
   ├── Buy  → RSI < 30 (oversold) + price > SMA50 (uptrend) + volume spike
   ├── Sell → RSI > 70 (overbought) + price < SMA20 (downtrend)
   └── Hold → between thresholds

4. Screen Universe
   └── screen_symbols(above_sma200=True, rsi_max=35, sort_by="volume", limit=20)
       → returns list of symbols matching buy criteria

5. Monitor Alerts
   └── set_alert_rule(symbol, type="indicator", condition="rsi14 < 30")
       → check_alerts() triggers when condition met
```

---

## Code Examples

### Fetching market watch from DPS (Python)

```python
import httpx
from bs4 import BeautifulSoup

url = "https://dps.psx.com.pk/market-watch"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-PK,en;q=0.9",
}

response = httpx.get(url, headers=headers)
soup = BeautifulSoup(response.text, "lxml")
table = soup.find("table")

# Parse rows into {symbol, price, change, volume, day_high, day_low}
```

### Fetching historical data from DPS (Python)

```python
import httpx
from bs4 import BeautifulSoup

url = "https://dps.psx.com.pk/historical"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

response = httpx.post(url, headers=headers, data={"symbol": "EFERT"})
soup = BeautifulSoup(response.text, "lxml")

# Table columns: DATE | OPEN | HIGH | LOW | CLOSE | VOLUME
# Date format: "May 22, 2026"
```

### Fetching real-time trades from AhleTrade (Python)

```python
import httpx
from datetime import datetime

url = "http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher"
params = {
    "action": "Market",
    "identifier": "BuySell",
    "market": "REG",
    "symbol": "EFERT",
}

response = httpx.get(url, params=params)
# Response format: "HH:MM:SS;price;vol;|HH:MM:SS;price;vol;|..."
records = response.text.split("|")
for record in records:
    parts = record.strip().split(";")
    if len(parts) >= 3 and parts[0]:
        time, price, volume = parts[0], float(parts[1]), int(float(parts[2]))
```

### Using the MCP server

```python
# Via SSE client (example with mcp Python SDK)
from mcp import ClientSession, StdioServerParameters
import asyncio

async def main():
    async with ClientSession(...) as session:
        indicators = await session.call_tool(
            "compute_indicators",
            {"symbol": "EFERT", "indicators": ["rsi14", "sma20", "sma50", "macd"]}
        )
        print(indicators)

asyncio.run(main())
```

---

## Notes & Caveats

- **DPS data is 15+ minutes delayed.** Not suitable for real-time trading decisions.
- **AhleTrade feed is real-time** but only contains current session data (reset daily).
- **No official PSX REST API exists.** All data is obtained through HTML scraping.
- **Rate-limiting:** Be respectful — max 2 concurrent requests, with retry on 5xx.
- **Data accuracy:** Always verify critical values against official PSX sources.
- **Legal:** All data is publicly available. For informational/educational purposes only.
- **Historical depth:** DPS provides ~10 years of daily OHLCV per symbol.
- **Symbol format:** Use uppercase ticker symbols (EFERT, LUCK, HUBC, etc.).

---

## What NafaIQ Actually Built (Implementation Additions)

The sections above document all available data sources and architecture options. Below is what we chose and built.

### Architecture Choice

We went with a **custom Python FastAPI microservice** (not Option A/B/C from the MCP server). The service lives at `services/psx-api/` in the same repo.

**Why not the MCP server:**
- MCP is designed as a Claude AI companion, not a production REST API
- We needed Supabase as a multi-user cache layer (MCP uses local SQLite)
- We needed background jobs (APScheduler) for periodic data refresh
- We needed bulk upsert capability for 495-stock snapshots

**Why Python (not all-TypeScript):**
- BeautifulSoup + lxml is the HTML scraping standard
- numpy enables vectorized indicators in ~150 lines
- sklearn gives us a production ML pipeline

### Data Sources Combined

| Source | What we use it for | Frequency |
|---|---|---|
| DPS `/market-watch` | 495-stock price snapshot → `psx_market_snapshot` | Every 5s |
| DPS `/historical` | 10-year OHLCV per stock → `psx_ohlcv` | Nightly backfill |
| DPS `/company/{sym}` | Fundamentals + profile → `psx_fundamentals`, `psx_profile` | Weekly |
| DPS `/announcements` | Corporate announcements → `psx_announcements` | Every 15min |
| DPS `/company/payouts` | Dividend history → `psx_dividends` | Weekly |
| DPS `/timeseries/eod/{code}` | Index EOD (KSE100, KSE30, ALLSHR) → `psx_index_eod` | Daily |
| TradingView `/pakistan/scan` | **Sector classification** for 478 stocks → `psx_profile` | Every 5min |
| AhleTrade `/FeedFetcher` | Real-time trade prices → `psx_market_snapshot` | Every 5s |

### Signal Engine (ML — Not Yet Trained)

We built a production-grade ML signal pipeline using sklearn's GradientBoostingClassifier:

**Features (27):** price-derived (6), trend (5), momentum (4), volatility (3), volume (4), fundamentals (5)
**Labels (5-class):** STRONG BUY/BUY/HOLD/SELL/STRONG SELL from forward 20-day returns
**Validation:** Walk-forward over 3 chronological folds (not random k-fold)
**Artifacts:** `app/ml/signal_model.joblib`, `app/ml/scaler.joblib`, `app/ml/feature_list.json`

**API endpoints:** `GET /api/signal/{symbol}` (4h cache TTL), `POST /api/signals/batch`

**Training:** `python scripts/train_signal_model.py` — requires OHLCV backfill first (~3 minutes on 50K samples)

### Frontend Integration

The frontend calls the Python API directly via browser `fetch()` during local development. CORS is enabled on the API.

**Single source of truth:** `usePsxLiveMarket()` — one React Query cache key `["psx","live"]` shared by all 7 UI surfaces (ticker strip, screener, watchlist, movers, index cards, stock detail header, portfolio). This eliminates price contradictions across the UI.

**Realtime:** Supabase Realtime enabled on `psx_market_snapshot` table. The `usePsxRealtime()` hook subscribes to `psx:market` channel and invalidates the shared cache key on every update.

**Auth bypass:** PSX routes (`/psx`, `/stock/*`) skip authentication for local dev. Watchlist and alerts fall back to local React state when no user session exists.

### Current Status (July 2026)

| Phase | Status |
|---|---|
| Python Backend (FastAPI + 3 scrapers + 8 jobs) | ✅ Complete |
| REST API (17 endpoints) | ✅ Complete |
| Realtime Layer (AhleTrade + Supabase Realtime) | ✅ Complete |
| Frontend Bridge (15 hooks, 7 UI surfaces wired) | ✅ Complete |
| ML Signal Engine (code complete) | ♻ Awaiting OHLCV backfill for training |
| User Features (watchlist, alerts, screener) | ✅ Complete |
| Sector Heatmap (TradingView + DPS, 24 sectors) | ✅ Complete |
| Hardening (error monitoring, rate limiting) | ⬜ Pending |
| Finance Module | ⬜ Pending |

### Key Files (Actual — not planned)

```
services/psx-api/
├── app/
│   ├── main.py                    # FastAPI + CORS + 8 background jobs
│   ├── api/market.py              # 14 market endpoints
│   ├── api/signals.py             # 2 ML signal endpoints
│   ├── scrapers/dps.py            # DPS HTML/JSON scraper (all endpoints)
│   ├── scrapers/ahletrade.py      # AhleTrade real-time poller
│   ├── scrapers/tradingview.py    # TradingView scanner API client (NEW)
│   ├── services/cache.py          # Read-through Supabase cache (bulk upserts)
│   ├── services/indicators.py     # 11 pure numpy indicators
│   ├── services/signal_engine.py  # ML signal predictor (lazy-loads model)
│   ├── ml/features.py             # 27-feature engineering for ML
│   └── jobs/scheduler.py          # 8 APScheduler background jobs
├── scripts/train_signal_model.py  # Walk-forward GBC training
└── supabase/migrations/
    ├── 20260706XX_psx_module.sql          # 12 core PSX tables
    └── 20260706XX_psx_realtime_and_fix.sql # Realtime + signals + watchlist + alerts
```

### Running the Full Stack

```bash
# Terminal 1 — Python API
cd services/psx-api
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd .
npm run dev
# → http://localhost:8080/psx (no auth needed)
```
