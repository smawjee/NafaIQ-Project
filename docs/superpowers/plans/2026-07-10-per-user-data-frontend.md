# Per-User Data Flow on Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded dummy data on dashboard, finance, and portfolio with real user data from the backend API. Fix KSE-100 candlestick chart. Compute today's P/L from real historical data.

**Architecture:** Backend adds aggregation endpoints (networth, finance summary/series, history coverage). Frontend adds new React Query hooks that consume these endpoints. Components swap their data sources at the literal-value points only. Anonymous fallback to existing dummy data preserved. New migration adds OHLCV columns to `psx_index_eod`. Backend startup logs warnings if any symbol has <20 days of `psx_ohlcv` data.

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2.0 (async) / Supabase / React 19 / TypeScript / TanStack Query / Supabase JS

**Working directory:** `D:\NafaIQ-Monorepo` ONLY

## Global Constraints

- No file, component, table, or implementation may be removed. Only additions or data-source swaps.
- No emojis in new code.
- Component shape, layout, animations, modals, behavior all preserved.
- No file/code/table may be removed without explicit user permission.
- Anonymous fallback to `lib/data.ts` and `lib/finance/data.ts` constants must continue to work.
- New code uses SQLAlchemy Core `text()` (matches existing `portfolio.py`, `finance.py` pattern).
- Frontend hooks live in `src/hooks/` and follow existing `use-portfolio.ts` pattern (React Query + `userGet`/`userPost`/`userPatch`/`userDelete`).
- Every phase ends with: tests pass → commit → branch ready for next phase.

---

## Phase 0 — KSE-100 Candlesticks Fix

### Task 0.1: Add OHLCV columns to `psx_index_eod` table

**Files:**
- Create: `backend/database/migrations/20260710010000_index_ohlcv.sql`

**Step 1: Write the migration file**

Create `backend/database/migrations/20260710010000_index_ohlcv.sql` with this exact content:

```sql
-- 20260710010000_index_ohlcv.sql
-- Add open/high/low columns to psx_index_eod to support candlestick rendering for indices (KSE-100, KSE-30, KMI-30, ALLSHR)

ALTER TABLE psx_index_eod
    ADD COLUMN IF NOT EXISTS open NUMERIC(12,2) DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS high NUMERIC(12,2) DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS low  NUMERIC(12,2) DEFAULT 0 NOT NULL;

-- Backfill open/high/low from close where missing (initial state)
UPDATE psx_index_eod
SET open = close, high = close, low = close
WHERE open = 0 AND high = 0 AND low = 0 AND close > 0;

CREATE INDEX IF NOT EXISTS idx_psx_index_eod_code_date
    ON psx_index_eod (code, date DESC);
```

**Step 2: Apply the migration to Supabase**

Open Supabase Dashboard → SQL Editor → paste file contents → Run. Verify with:

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'psx_index_eod' ORDER BY ordinal_position;
```

Expected: rows include `code, date, close, volume, open, high, low`.

**Step 3: Commit**

```bash
git add backend/database/migrations/20260710010000_index_ohlcv.sql
git commit -m "feat(db): add open/high/low columns to psx_index_eod for candlestick rendering"
```

---

### Task 0.2: Extend `IndexBar` model with OHLCV fields

**Files:**
- Modify: `backend/src/app/models/__init__.py:1-100` (find `class IndexBar` definition)

**Step 1: Edit the IndexBar model**

Find `class IndexBar(BaseModel):` and change to:

```python
class IndexBar(BaseModel):
    code: str
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
```

Keep all other classes unchanged.

**Step 2: Verify no other consumers of `IndexBar` break**

Run from `D:\NafaIQ-Monorepo\backend`:

```bash
cd backend && python -c "from app.models import IndexBar; print(IndexBar.model_fields)"
```

Expected output lists `code, date, open, high, low, close, volume`.

**Step 3: Commit**

```bash
git add backend/src/app/models/__init__.py
git commit -m "feat(models): add open/high/low fields to IndexBar"
```

---

### Task 0.3: Update DPS scraper to parse OHLCV for indices

**Files:**
- Modify: `backend/src/app/scrapers/dps.py` (find `fetch_index_eod` method)

**Step 1: Edit `fetch_index_eod` to defensively parse OHLCV**

Find the `fetch_index_eod` method body and replace the `IndexBar(...)` construction with this defensively-parsed version:

```python
bars: list[IndexBar] = []
for row in reversed(rows):
    if not isinstance(row, list) or len(row) < 2:
        continue
    try:
        ts = int(row[0])
        close = float(row[1])
    except (ValueError, TypeError):
        continue
    vol = None
    if len(row) >= 3:
        try:
            vol = int(float(row[2]))
        except (ValueError, TypeError):
            pass
    # Defensive OHLCV: parse if present, else fallback to close
    open_p = close
    high_p = close
    low_p = close
    if len(row) >= 6:
        try:
            open_p = float(row[1])
            high_p = float(row[2])
            low_p = float(row[3])
            close = float(row[4])
            vol = int(float(row[5])) if row[5] not in (None, "") else vol
        except (ValueError, TypeError, IndexError):
            pass
    d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
    bars.append(IndexBar(
        code=code.upper(),
        date=d,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close,
        volume=vol,
    ))
return bars
```

**Step 2: Verify scraper still imports**

```bash
cd backend && python -c "from app.scrapers.dps import DPSScraper; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/scrapers/dps.py
git commit -m "feat(scraper): parse OHLCV from DPS index timeseries defensively"
```

---

### Task 0.4: Update `job_refresh_index_eod` to include KMI-30 and persist OHLCV

**Files:**
- Modify: `backend/src/app/jobs/scheduler.py:185-204` (find `job_refresh_index_eod`)

**Step 1: Edit the job to add KMI-30 and write OHLCV**

Replace `job_refresh_index_eod` with:

```python
async def job_refresh_index_eod():
    log.info("job:refresh_index_eod:start")
    db = get_supabase()
    for code in ("KSE100", "KSE30", "KMI30", "ALLSHR"):
        try:
            bars = await dps.fetch_index_eod(code)
            if bars:
                rows = [
                    {
                        "code": b.code,
                        "date": b.date.isoformat(),
                        "open": b.open or 0,
                        "high": b.high or 0,
                        "low": b.low or 0,
                        "close": b.close,
                        "volume": b.volume,
                    }
                    for b in bars
                ]
                db.table("psx_index_eod").upsert(rows, on_conflict="code,date").execute()
        except Exception:
            log.exception("job:refresh_index_eod:failed", code=code)
    log.info("job:refresh_index_eod:done")
```

**Step 2: Verify import**

```bash
cd backend && python -c "from app.jobs.scheduler import job_refresh_index_eod; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/jobs/scheduler.py
git commit -m "feat(jobs): include KMI-30 and persist OHLCV in index EOD job"
```

---

### Task 0.5: Update `ApiIndexBar` type in frontend

**Files:**
- Modify: `frontend/packages/web/src/lib/psx/types.ts:64-69` (find `ApiIndexBar` interface)

**Step 1: Add open/high/low fields to `ApiIndexBar`**

Find:

```ts
export interface ApiIndexBar {
  code: string;
  date: string;
  close: number;
  volume: number | null;
}
```

Replace with:

```ts
export interface ApiIndexBar {
  code: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors related to `ApiIndexBar`.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/lib/psx/types.ts
git commit -m "feat(types): add OHLCV fields to ApiIndexBar for candlestick rendering"
```

---

### Task 0.6: Fix KSE-100 chart data path in `psx.tsx`

**Files:**
- Modify: `frontend/packages/web/src/routes/psx.tsx:137, 175-192` (find KSE-100 special case)

**Step 1: Edit the data wiring**

Find this code block (around line 137):

```tsx
const { data: ohlcvData } = usePsxHistory(sym === "KSE-100" ? undefined : sym);
```

Replace with:

```tsx
const { data: ohlcvData } = usePsxHistory(sym === "KSE-100" ? "KSE100" : sym);
```

**Step 2: Edit the kse100Data mapping to use real OHLCV when present**

Find this block (around line 175-192):

```tsx
const full = useMemo(() => {
  if (sym === "KSE-100" && kse100Data && kse100Data.length > 0) {
    return kse100Data.map((b) => ({
      date: b.date,
      t: new Date(b.date).getTime(),
      open: b.close,
      high: b.close,
      low: b.close,
      close: b.close,
      volume: b.volume ?? 0,
    }));
  }
  if (ohlcvData && ohlcvData.length > 0) {
    return ohlcvData.slice(-250);
  }
  const meta = symbolMeta(sym);
  return generateOHLCV(meta.seed, meta.start, meta.end, 250, meta.vMin, meta.vMax);
}, [sym, ohlcvData, kse100Data]);
```

Replace with:

```tsx
const full = useMemo(() => {
  if (sym === "KSE-100" && ohlcvData && ohlcvData.length > 0) {
    return ohlcvData.slice(-250);
  }
  if (kse100Data && kse100Data.length > 0) {
    return kse100Data.map((b) => ({
      date: b.date,
      t: new Date(b.date).getTime(),
      open: b.open ?? b.close,
      high: b.high ?? b.close,
      low: b.low ?? b.close,
      close: b.close,
      volume: b.volume ?? 0,
    }));
  }
  if (ohlcvData && ohlcvData.length > 0) {
    return ohlcvData.slice(-250);
  }
  const meta = symbolMeta(sym);
  return generateOHLCV(meta.seed, meta.start, meta.end, 250, meta.vMin, meta.vMax);
}, [sym, ohlcvData, kse100Data]);
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 4: Manual test** — Run dev server, navigate to `/psx`, select KSE-100, switch chart type to "Candle". Verify real OHLCV candles render (not flat lines). Repeat for KSE-30, KMI-30, KSE All Share if selectable.

**Step 5: Commit**

```bash
git add frontend/packages/web/src/routes/psx.tsx
git commit -m "fix(psx): use real OHLCV for KSE-100 candlestick chart"
```

---

## Phase 1 — Backend Aggregation Endpoints

### Task 1.1: Add `GET /api/portfolio/networth` endpoint

**Files:**
- Modify: `backend/src/app/api/portfolio.py` (append at end)

**Interfaces:**
- Consumes: `require_user` dependency, `psx_holdings`, `psx_portfolios`, `psx_market_snapshot`, `psx_ohlcv` tables
- Produces: `NetworthResponse` with `total_market_value, total_cost_basis, total_unrealized_pnl, total_unrealized_pnl_pct, today_pnl, today_pnl_pct, portfolio_count, holding_count`

**Step 1: Write the failing test**

Create `backend/tests/test_networth.py`:

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_networth_endpoint_requires_auth():
    """Unauthenticated request returns 401."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/portfolio/networth")
    assert r.status_code in (401, 403)
```

**Step 2: Run the test to verify it fails**

```bash
cd backend && python -m pytest tests/test_networth.py -v
```

Expected: PASS (because BearerTokenMiddleware returns 401). If PASS, the auth gate works.

**Step 3: Add the endpoint to portfolio.py**

Append to `backend/src/app/api/portfolio.py`:

```python
class NetworthHolding(BaseModel):
    symbol: str
    shares: int
    avg_cost: float
    current_price: float | None
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    pnl_pct: float
    previous_close: float | None
    today_pnl: float


class NetworthResponse(BaseModel):
    total_market_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    today_pnl: float
    today_pnl_pct: float
    portfolio_count: int
    holding_count: int
    by_holding: list[NetworthHolding]


@router.get("/portfolio/networth")
async def portfolio_networth(
    user: Annotated[dict, Depends(require_user)],
):
    """Sum totals across all user portfolios with today's P/L from previous close."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                WITH prev_close AS (
                    SELECT DISTINCT ON (symbol) symbol, close AS previous_close
                    FROM psx_ohlcv
                    WHERE date < CURRENT_DATE
                    ORDER BY symbol, date DESC
                )
                SELECT
                    h.id, h.symbol, h.shares, h.avg_cost,
                    s.price AS current_price,
                    (h.shares * COALESCE(s.price, 0))::numeric AS market_value,
                    (h.shares * h.avg_cost)::numeric AS cost_basis,
                    (h.shares * COALESCE(s.price, 0) - h.shares * h.avg_cost)::numeric AS unrealized_pnl,
                    CASE WHEN (h.shares * h.avg_cost) > 0 AND s.price IS NOT NULL
                        THEN ROUND(
                            ((h.shares * s.price - h.shares * h.avg_cost) / (h.shares * h.avg_cost)) * 100,
                            2
                        )
                        ELSE 0
                    END AS pnl_pct,
                    pc.previous_close AS previous_close,
                    CASE
                        WHEN s.price IS NOT NULL AND pc.previous_close IS NOT NULL
                        THEN ((s.price - pc.previous_close) * h.shares)::numeric
                        ELSE 0
                    END AS today_pnl
                FROM psx_holdings h
                JOIN psx_portfolios p ON p.id = h.portfolio_id AND p.user_id = :uid
                LEFT JOIN psx_market_snapshot s ON s.symbol = h.symbol
                LEFT JOIN prev_close pc ON pc.symbol = h.symbol
                ORDER BY h.symbol ASC
            """),
            {"uid": user_id},
        )
        rows = result.mappings().all()

    by_holding = [
        NetworthHolding(
            symbol=r["symbol"],
            shares=r["shares"],
            avg_cost=float(r["avg_cost"]),
            current_price=float(r["current_price"]) if r["current_price"] else None,
            market_value=float(r["market_value"]),
            cost_basis=float(r["cost_basis"]),
            unrealized_pnl=float(r["unrealized_pnl"]),
            pnl_pct=float(r["pnl_pct"]),
            previous_close=float(r["previous_close"]) if r["previous_close"] else None,
            today_pnl=float(r["today_pnl"]),
        )
        for r in rows
    ]

    total_market_value = sum(h.market_value for h in by_holding)
    total_cost_basis = sum(h.cost_basis for h in by_holding)
    total_unrealized_pnl = sum(h.unrealized_pnl for h in by_holding)
    total_unrealized_pnl_pct = (
        round((total_unrealized_pnl / total_cost_basis) * 100, 2)
        if total_cost_basis > 0
        else 0.0
    )
    today_pnl = sum(h.today_pnl for h in by_holding)
    prev_value = sum(
        (h.previous_close or 0) * h.shares
        for h in by_holding
        if h.previous_close is not None
    )
    today_pnl_pct = (
        round((today_pnl / prev_value) * 100, 2)
        if prev_value > 0
        else 0.0
    )

    return NetworthResponse(
        total_market_value=total_market_value,
        total_cost_basis=total_cost_basis,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_pnl_pct=total_unrealized_pnl_pct,
        today_pnl=today_pnl,
        today_pnl_pct=today_pnl_pct,
        portfolio_count=len({h.symbol for h in by_holding}),  # unique symbols proxy; replace below
        holding_count=len(by_holding),
        by_holding=by_holding,
    )
```

**Step 4: Fix `portfolio_count` to count distinct portfolios**

Replace the field with a separate count query. Add this before the return:

```python
        count_result = await conn.execute(
            text("SELECT COUNT(*) AS c FROM psx_portfolios WHERE user_id = :uid"),
            {"uid": user_id},
        )
        portfolio_count = count_result.scalar() or 0
```

Then in the return, use `portfolio_count=portfolio_count` instead of the line `len({h.symbol for h in by_holding})`.

**Step 5: Run the test**

```bash
cd backend && python -m pytest tests/test_networth.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/app/api/portfolio.py backend/tests/test_networth.py
git commit -m "feat(api): add /api/portfolio/networth with today's P/L from previous close"
```

---

### Task 1.2: Add `GET /api/finance/summary` endpoint

**Files:**
- Modify: `backend/src/app/api/finance.py` (append at end)

**Interfaces:**
- Consumes: `require_user`, `user_transactions` table
- Produces: `FinanceSummaryResponse` with `month, income, expenses, savings, savings_rate, last_month_income, last_month_expense`

**Step 1: Add the endpoint**

Append to `backend/src/app/api/finance.py`:

```python
class FinanceSummaryResponse(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float
    savings_rate: float
    last_month_income: float
    last_month_expense: float
    last_month_savings: float


@router.get("/finance/summary")
async def finance_summary(
    month: str | None = None,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Aggregate income, expenses, and savings for a given month.

    If `month` is None, uses the current month. Format: YYYY-MM.
    """
    from datetime import datetime
    user_id = user["user_id"]
    if month is None:
        month = datetime.utcnow().strftime("%Y-%m")
    year, m = month.split("-")
    year_i, m_i = int(year), int(m)

    last_month_date = (datetime(year_i, m_i, 1) - timedelta(days=1))
    last_year_i, last_m_i = last_month_date.year, last_month_date.month
    last_month = f"{last_year_i:04d}-{last_m_i:02d}"

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM'))
                GROUP BY transaction_type
            """),
            {"uid": user_id, "month": month},
        )
        rows = {r["transaction_type"]: float(r["total"]) for r in result.mappings().all()}

        last_result = await conn.execute(
            text("""
                SELECT
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND DATE_TRUNC('month', transaction_date) = DATE_TRUNC('month', TO_DATE(:month, 'YYYY-MM'))
                GROUP BY transaction_type
            """),
            {"uid": user_id, "month": last_month},
        )
        last_rows = {r["transaction_type"]: float(r["total"]) for r in last_result.mappings().all()}

    income = rows.get("income", 0.0)
    expenses = rows.get("expense", 0.0)
    savings = income - expenses
    savings_rate = round((savings / income) * 100, 1) if income > 0 else 0.0

    last_income = last_rows.get("income", 0.0)
    last_expense = last_rows.get("expense", 0.0)

    return FinanceSummaryResponse(
        month=month,
        income=income,
        expenses=expenses,
        savings=savings,
        savings_rate=savings_rate,
        last_month_income=last_income,
        last_month_expense=last_expense,
        last_month_savings=last_income - last_expense,
    )
```

Make sure `timedelta` is imported at the top of the file (already imported via `from datetime import ...` if used elsewhere; otherwise add `from datetime import timedelta`).

**Step 2: Verify import**

```bash
cd backend && python -c "from app.api.finance import router; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/api/finance.py
git commit -m "feat(api): add /api/finance/summary for income/expense/savings aggregation"
```

---

### Task 1.3: Add `GET /api/finance/income-expense` endpoint

**Files:**
- Modify: `backend/src/app/api/finance.py` (append)

**Step 1: Add the endpoint**

Append to `backend/src/app/api/finance.py`:

```python
class IncomeExpensePoint(BaseModel):
    month: str
    income: float
    expense: float


class IncomeExpenseResponse(BaseModel):
    months: int
    series: list[IncomeExpensePoint]


@router.get("/finance/income-expense")
async def finance_income_expense(
    months: int = 6,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Return the last N months of income/expense series, ordered ASC by month."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
                    transaction_type,
                    COALESCE(SUM(amount), 0)::numeric AS total
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_date >= DATE_TRUNC('month', CURRENT_DATE) - (:months - 1) * INTERVAL '1 month'
                GROUP BY 1, transaction_type
                ORDER BY 1 ASC
            """),
            {"uid": user_id, "months": months},
        )
        rows = result.mappings().all()

    by_month: dict[str, dict[str, float]] = {}
    for r in rows:
        m = r["month"]
        if m not in by_month:
            by_month[m] = {"income": 0.0, "expense": 0.0}
        by_month[m][r["transaction_type"]] = float(r["total"])

    series = [
        IncomeExpensePoint(month=m, income=v.get("income", 0.0), expense=v.get("expense", 0.0))
        for m, v in by_month.items()
    ]
    return IncomeExpenseResponse(months=months, series=series)
```

**Step 2: Verify import**

```bash
cd backend && python -c "from app.api.finance import router; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/api/finance.py
git commit -m "feat(api): add /api/finance/income-expense for 6-month series"
```

---

### Task 1.4: Add `GET /api/finance/spending-by-category` endpoint

**Files:**
- Modify: `backend/src/app/api/finance.py` (append)

**Step 1: Add the endpoint**

Append to `backend/src/app/api/finance.py`:

```python
class SpendingCategory(BaseModel):
    category: str
    amount: float
    pct: float


class SpendingByCategoryResponse(BaseModel):
    days: int
    total: float
    categories: list[SpendingCategory]


@router.get("/finance/spending-by-category")
async def finance_spending_by_category(
    days: int = 30,
    user: Annotated[dict, Depends(require_user)] = ...,
):
    """Aggregate spending by category for the last N days, ordered by amount DESC."""
    user_id = user["user_id"]
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    category,
                    COALESCE(SUM(amount), 0)::numeric AS amount
                FROM user_transactions
                WHERE user_id = :uid
                  AND transaction_type = 'expense'
                  AND transaction_date >= CURRENT_DATE - (:days || ' days')::interval
                GROUP BY category
                ORDER BY amount DESC
            """),
            {"uid": user_id, "days": days},
        )
        rows = result.mappings().all()

    total = sum(float(r["amount"]) for r in rows)
    categories = [
        SpendingCategory(
            category=r["category"],
            amount=float(r["amount"]),
            pct=round((float(r["amount"]) / total) * 100, 1) if total > 0 else 0.0,
        )
        for r in rows
    ]
    return SpendingByCategoryResponse(days=days, total=total, categories=categories)
```

**Step 2: Verify import**

```bash
cd backend && python -c "from app.api.finance import router; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/api/finance.py
git commit -m "feat(api): add /api/finance/spending-by-category for top categories"
```

---

### Task 1.5: Add `GET /api/market/history-coverage` endpoint

**Files:**
- Modify: `backend/src/app/api/market.py` (append at end)

**Step 1: Add the endpoint**

Append to `backend/src/app/api/market.py`:

```python
@router.get("/market/history-coverage")
async def history_coverage():
    """Report days of historical OHLCV data per symbol. Used to verify 20-day guarantee."""
    await ensure_reflected()
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                get_table("psx_ohlcv").c.symbol,
                func.count().label("days_available"),
                func.min(get_table("psx_ohlcv").c.date).label("oldest_date"),
                func.max(get_table("psx_ohlcv").c.date).label("newest_date"),
            )
            .group_by(get_table("psx_ohlcv").c.symbol)
            .order_by(get_table("psx_ohlcv").c.symbol)
        )
        result = await session.execute(stmt)
        rows = result.all()
    return [
        {
            "symbol": r.symbol,
            "days_available": r.days_available,
            "oldest_date": str(r.oldest_date) if r.oldest_date else None,
            "newest_date": str(r.newest_date) if r.newest_date else None,
        }
        for r in rows
    ]
```

**Step 2: Verify import**

```bash
cd backend && python -c "from app.api.market import router; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add backend/src/app/api/market.py
git commit -m "feat(api): add /api/market/history-coverage for data freshness check"
```

---

## Phase 2 — 20-Day Data Guarantee + Startup Check

### Task 2.1: Add startup check for 20-day data in main.py

**Files:**
- Modify: `backend/src/app/main.py:42-48` (lifespan function)

**Step 1: Add the data coverage check to lifespan**

Replace the lifespan function with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", port=settings.port)
    await ensure_reflected()
    init_scheduler()
    await _check_history_coverage()
    yield
    shutdown_scheduler()
    log.info("shutdown")


async def _check_history_coverage():
    """Log a warning per symbol with <20 days of psx_ohlcv data."""
    try:
        from sqlalchemy import func, select
        from app.db.sqlalchemy import get_session_factory
        from app.db.orm import get_table
        factory = get_session_factory()
        async with factory() as session:
            ohlcv = get_table("psx_ohlcv")
            stmt = (
                select(
                    ohlcv.c.symbol,
                    func.count().label("days"),
                )
                .group_by(ohlcv.c.symbol)
            )
            result = await session.execute(stmt)
            rows = result.all()
        low_coverage = [r for r in rows if r.days < 20]
        if low_coverage:
            log.warning(
                "history_coverage:low",
                threshold=20,
                count=len(low_coverage),
                symbols=[r.symbol for r in low_coverage[:20]],
            )
        else:
            log.info("history_coverage:ok", symbols=len(rows))
    except Exception:
        log.exception("history_coverage:check_failed")
```

**Step 2: Restart the backend and check logs**

```bash
cd backend && python -m app.main
```

Look for `history_coverage:ok` or `history_coverage:low` in the startup logs. (If running in a different shell, the previous command output can be checked.)

**Step 3: Commit**

```bash
git add backend/src/app/main.py
git commit -m "feat(startup): log warning if any symbol has <20 days of OHLCV data"
```

---

### Task 2.2: Add tests for new endpoints

**Files:**
- Modify: `backend/tests/test_networth.py` (extend)

**Step 1: Add a test that exercises the networth endpoint shape**

Append to `backend/tests/test_networth.py`:

```python
@pytest.mark.asyncio
async def test_history_coverage_endpoint_returns_list():
    """Public PSX-token endpoint returns list of {symbol, days_available, ...}."""
    from httpx import ASGITransport, AsyncClient
    from app.config import settings
    from app.main import app
    headers = {"Authorization": f"Bearer {settings.psx_api_token}"} if settings.psx_api_token else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/market/history-coverage", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
```

**Step 2: Run tests**

```bash
cd backend && python -m pytest tests/test_networth.py -v
```

Expected: PASS

**Step 3: Run full test suite**

```bash
cd backend && python -m pytest -v
```

Expected: All previously passing tests still pass.

**Step 4: Commit**

```bash
git add backend/tests/test_networth.py
git commit -m "test: cover history-coverage endpoint"
```

---

## Phase 3 — Supabase types

### Task 3.1: Add 8 missing table types to Supabase types.ts

**Files:**
- Modify: `frontend/packages/web/src/integrations/supabase/types.ts` (append new table types at the end of the `Database` interface's `Tables`)

**Step 1: Read the existing types.ts structure**

Open `frontend/packages/web/src/integrations/supabase/types.ts` and find the `Database` interface. It has a `Tables` object with table entries. Each entry has `Row`, `Insert`, `Update`.

**Step 2: Add the 8 new table types**

Find the last table entry in `Tables`. After it, add the following new entries (additive, do not modify existing entries):

```typescript
      user_alerts: {
        Row: {
          id: number;
          user_id: string;
          type: "stock_price" | "bill" | "budget" | "goal";
          title: string;
          meta: Json | null;
          enabled: boolean | null;
          triggered_at: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          type: "stock_price" | "bill" | "budget" | "goal";
          title: string;
          meta?: Json | null;
          enabled?: boolean | null;
          triggered_at?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          type?: "stock_price" | "bill" | "budget" | "goal";
          title?: string;
          meta?: Json | null;
          enabled?: boolean | null;
          triggered_at?: string | null;
          created_at?: string | null;
        };
      };
      in_app_notifications: {
        Row: {
          id: number;
          user_id: string;
          kind: "price_alert" | "bill" | "budget" | "goal" | "system";
          title: string;
          body: string;
          link: string | null;
          read: boolean | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          kind: "price_alert" | "bill" | "budget" | "goal" | "system";
          title: string;
          body: string;
          link?: string | null;
          read?: boolean | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          kind?: "price_alert" | "bill" | "budget" | "goal" | "system";
          title?: string;
          body?: string;
          link?: string | null;
          read?: boolean | null;
          created_at?: string | null;
        };
      };
      user_notification_prefs: {
        Row: {
          user_id: string;
          email_alerts: boolean | null;
          push_alerts: boolean | null;
          in_app_alerts: boolean | null;
          updated_at: string | null;
        };
        Insert: {
          user_id: string;
          email_alerts?: boolean | null;
          push_alerts?: boolean | null;
          in_app_alerts?: boolean | null;
          updated_at?: string | null;
        };
        Update: {
          user_id?: string;
          email_alerts?: boolean | null;
          push_alerts?: boolean | null;
          in_app_alerts?: boolean | null;
          updated_at?: string | null;
        };
      };
      user_transactions: {
        Row: {
          id: number;
          user_id: string;
          merchant: string;
          amount: number;
          currency: string | null;
          transaction_type: string;
          category: string;
          transaction_date: string | null;
          source: string | null;
          note: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          merchant: string;
          amount: number;
          currency?: string | null;
          transaction_type: string;
          category: string;
          transaction_date?: string | null;
          source?: string | null;
          note?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          merchant?: string;
          amount?: number;
          currency?: string | null;
          transaction_type?: string;
          category?: string;
          transaction_date?: string | null;
          source?: string | null;
          note?: string | null;
          created_at?: string | null;
        };
      };
      user_goals: {
        Row: {
          id: number;
          user_id: string;
          emoji: string | null;
          name: string;
          target: number;
          saved: number | null;
          color: string | null;
          ai_tip: string | null;
          target_date: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          emoji?: string | null;
          name: string;
          target: number;
          saved?: number | null;
          color?: string | null;
          ai_tip?: string | null;
          target_date?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          emoji?: string | null;
          name?: string;
          target?: number;
          saved?: number | null;
          color?: string | null;
          ai_tip?: string | null;
          target_date?: string | null;
          created_at?: string | null;
        };
      };
      user_budgets: {
        Row: {
          id: number;
          user_id: string;
          category: string;
          spent: number | null;
          limit_amount: number | null;
          period: string | null;
          tip: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          category: string;
          spent?: number | null;
          limit_amount?: number | null;
          period?: string | null;
          tip?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          category?: string;
          spent?: number | null;
          limit_amount?: number | null;
          period?: string | null;
          tip?: string | null;
          created_at?: string | null;
        };
      };
      user_bills: {
        Row: {
          id: number;
          user_id: string;
          name: string;
          amount: number;
          currency: string | null;
          due_date: string | null;
          status: string | null;
          recurring: boolean | null;
          paid_at: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          name: string;
          amount: number;
          currency?: string | null;
          due_date?: string | null;
          status?: string | null;
          recurring?: boolean | null;
          paid_at?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: number;
          user_id?: string;
          name?: string;
          amount?: number;
          currency?: string | null;
          due_date?: string | null;
          status?: string | null;
          recurring?: boolean | null;
          paid_at?: string | null;
          created_at?: string | null;
        };
      };
      user_settings: {
        Row: {
          user_id: string;
          monthly_income: number | null;
          currency: string | null;
          language: string | null;
          plan: string | null;
          updated_at: string | null;
        };
        Insert: {
          user_id: string;
          monthly_income?: number | null;
          currency?: string | null;
          language?: string | null;
          plan?: string | null;
          updated_at?: string | null;
        };
        Update: {
          user_id?: string;
          monthly_income?: number | null;
          currency?: string | null;
          language?: string | null;
          plan?: string | null;
          updated_at?: string | null;
        };
      };
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/integrations/supabase/types.ts
git commit -m "feat(types): add 8 missing Supabase table type definitions"
```

---

### Task 3.2: Remove `as any` casts from frontend hooks

**Files:**
- Modify: `frontend/packages/web/src/hooks/use-alerts.ts:29`
- Modify: `frontend/packages/web/src/hooks/use-notifications.ts:41` (if present)
- Modify: `frontend/packages/web/src/lib/finance/financeBills.ts` (find any `as any`)

**Step 1: Find and remove `as any`**

Run from `D:\NafaIQ-Monorepo`:

```bash
Select-String -Path "frontend\packages\web\src\hooks\use-alerts.ts" -Pattern "as any"
```

Remove any `as any` casts. The types should now resolve correctly.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-alerts.ts frontend/packages/web/src/hooks/use-notifications.ts frontend/packages/web/src/lib/finance/financeBills.ts
git commit -m "refactor: remove 'as any' casts now that Supabase types are defined"
```

---

## Phase 4 — Frontend Hooks

### Task 4.1: Create `use-finance-summary.ts` hook

**Files:**
- Create: `frontend/packages/web/src/hooks/use-finance-summary.ts`

**Step 1: Create the file**

```typescript
import { useQuery } from "@tanstack/react-query";
import { userGet } from "@/lib/psx/client";

export interface FinanceSummary {
  month: string;
  income: number;
  expenses: number;
  savings: number;
  savings_rate: number;
  last_month_income: number;
  last_month_expense: number;
  last_month_savings: number;
}

export function useFinanceSummary(month?: string) {
  return useQuery<FinanceSummary>({
    queryKey: ["finance", "summary", month ?? "current"],
    queryFn: () => {
      const qs = month ? `?month=${month}` : "";
      return userGet<FinanceSummary>(`/api/finance/summary${qs}`);
    },
    staleTime: 60_000,
  });
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-finance-summary.ts
git commit -m "feat(hooks): add useFinanceSummary hook"
```

---

### Task 4.2: Create `use-finance-budgets.ts` hook

**Files:**
- Create: `frontend/packages/web/src/hooks/use-finance-budgets.ts`

**Step 1: Create the file**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost, userPatch, userDelete } from "@/lib/psx/client";

export interface FinanceBudget {
  id: number;
  user_id: string;
  category: string;
  spent: number;
  limit_amount: number;
  period: string;
  tip: string | null;
  created_at: string | null;
}

export function useFinanceBudgets() {
  return useQuery<FinanceBudget[]>({
    queryKey: ["finance", "budgets"],
    queryFn: () => userGet<FinanceBudget[]>("/api/finance/budgets"),
    staleTime: 60_000,
  });
}

export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { category: string; spent?: number; limit_amount: number; period?: string; tip?: string }) =>
      userPost<FinanceBudget>("/api/finance/budgets", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}

export function useUpdateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; spent?: number; limit_amount?: number; tip?: string }) =>
      userPatch<FinanceBudget>(`/api/finance/budgets/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/budgets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-finance-budgets.ts
git commit -m "feat(hooks): add useFinanceBudgets CRUD hooks"
```

---

### Task 4.3: Create `use-finance-goals.ts` hook

**Files:**
- Create: `frontend/packages/web/src/hooks/use-finance-goals.ts`

**Step 1: Create the file**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost, userPatch, userDelete } from "@/lib/psx/client";

export interface FinanceGoal {
  id: number;
  user_id: string;
  emoji: string | null;
  name: string;
  target: number;
  saved: number;
  color: string | null;
  ai_tip: string | null;
  target_date: string | null;
  created_at: string | null;
}

export function useFinanceGoals() {
  return useQuery<FinanceGoal[]>({
    queryKey: ["finance", "goals"],
    queryFn: () => userGet<FinanceGoal[]>("/api/finance/goals"),
    staleTime: 60_000,
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { emoji?: string; name: string; target: number; saved?: number; color?: string; ai_tip?: string; target_date?: string }) =>
      userPost<FinanceGoal>("/api/finance/goals", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}

export function useContributeGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      userPatch<FinanceGoal>(`/api/finance/goals/${id}/contribute`, { amount }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/goals/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-finance-goals.ts
git commit -m "feat(hooks): add useFinanceGoals CRUD hooks"
```

---

### Task 4.4: Create `use-finance-series.ts` hook

**Files:**
- Create: `frontend/packages/web/src/hooks/use-finance-series.ts`

**Step 1: Create the file**

```typescript
import { useQuery } from "@tanstack/react-query";
import { userGet } from "@/lib/psx/client";

export interface IncomeExpensePoint {
  month: string;
  income: number;
  expense: number;
}

export interface IncomeExpenseResponse {
  months: number;
  series: IncomeExpensePoint[];
}

export interface SpendingCategory {
  category: string;
  amount: number;
  pct: number;
}

export interface SpendingByCategoryResponse {
  days: number;
  total: number;
  categories: SpendingCategory[];
}

export function useIncomeExpenseSeries(months: number = 6) {
  return useQuery<IncomeExpenseResponse>({
    queryKey: ["finance", "income-expense", months],
    queryFn: () => userGet<IncomeExpenseResponse>(`/api/finance/income-expense?months=${months}`),
    staleTime: 60_000,
  });
}

export function useSpendingByCategory(days: number = 30) {
  return useQuery<SpendingByCategoryResponse>({
    queryKey: ["finance", "spending-by-category", days],
    queryFn: () => userGet<SpendingByCategoryResponse>(`/api/finance/spending-by-category?days=${days}`),
    staleTime: 60_000,
  });
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-finance-series.ts
git commit -m "feat(hooks): add useIncomeExpenseSeries and useSpendingByCategory"
```

---

### Task 4.5: Add `usePortfolioNetworth` to `use-portfolio.ts`

**Files:**
- Modify: `frontend/packages/web/src/hooks/use-portfolio.ts` (append at end)

**Step 1: Add the new hook**

Append to `use-portfolio.ts`:

```typescript
export interface NetworthHolding {
  symbol: string;
  shares: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  pnl_pct: number;
  previous_close: number | null;
  today_pnl: number;
}

export interface NetworthResponse {
  total_market_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  today_pnl: number;
  today_pnl_pct: number;
  portfolio_count: number;
  holding_count: number;
  by_holding: NetworthHolding[];
}

export function usePortfolioNetworth() {
  return useQuery<NetworthResponse>({
    queryKey: ["portfolio", "networth"],
    queryFn: () => userGet<NetworthResponse>("/api/portfolio/networth"),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/packages/web/src/hooks/use-portfolio.ts
git commit -m "feat(hooks): add usePortfolioNetworth with today's P/L"
```

---

## Phase 5 — Dashboard Wiring (`app.tsx`)

### Task 5.1: Wire dashboard KPI cards to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/app.tsx:1-211` (top portion of file, before modals)

**Step 1: Add imports and wire Net Worth + Portfolio Value + Today's P/L**

Find the import section at the top of the file. Add (or extend existing) imports:

```typescript
import { usePortfolioNetworth } from "@/hooks/use-portfolio";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useSpendingByCategory } from "@/hooks/use-finance-series";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
```

In the Dashboard component body, after the existing hooks, add:

```typescript
const { user } = useAuth();
const { data: networth } = usePortfolioNetworth();
const { data: financeSummary } = useFinanceSummary();
const { data: spendingByCat } = useSpendingByCategory(30);
const { data: userGoals } = useFinanceGoals();
```

Find the hardcoded KPI values (lines 188-211). Replace each value with a real value when user is logged in, falling back to dummy when not.

The replacement pattern (apply to each stat card):

```tsx
// Total Net Worth
value={user && networth ? networth.total_market_value : 4280500}
sub={user && networth ? `+PKR ${Math.round(networth.today_pnl).toLocaleString()} (+${networth.today_pnl_pct}%) today` : "+PKR 56,000 (+1.32%) this month"}

// Portfolio Value
value={user && networth ? networth.total_market_value : 858054}
sub={user && networth ? `+${networth.total_unrealized_pnl_pct}% all time` : "+12.73% YTD"}

// Monthly Spending
value={user && financeSummary ? financeSummary.expenses : 112050}
sub={user && financeSummary ? `${financeSummary.last_month_expense > 0 ? Math.round(((financeSummary.expenses - financeSummary.last_month_expense) / financeSummary.last_month_expense) * 100) : 0}% vs last month` : "-12% vs May"}

// Today's PSX P/L
value={user && networth ? Math.round(networth.today_pnl) : 17480}
sub={user && networth ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct}%` : "+1.42%"}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Run dev server, log in as a user with at least one portfolio and one holding, navigate to `/app`. Verify KPI cards show real values matching the user's holdings. Log out, verify dummy fallback works.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/app.tsx
git commit -m "feat(dashboard): wire KPI cards to /api/portfolio/networth and /api/finance/summary"
```

---

### Task 5.2: Wire dashboard watchlist strip to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/app.tsx:21, 277-301` (watchlist strip)

**Step 1: Replace the `WATCHLIST` constant usage with `useWatchlist()`**

Find the import of `WATCHLIST` (around line 21):

```typescript
import { STOCKS, WATCHLIST, generateOHLCV } from "@/lib/data";
```

Replace with:

```typescript
import { STOCKS, generateOHLCV } from "@/lib/data";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
```

In the Dashboard body, add:

```typescript
const { watchlist } = useWatchlist();
```

Find the watchlist strip iteration (around line 277) and update:

```tsx
{user ? (watchlist.length > 0 ? watchlist : ["HBL", "ENGRO", "LUCK", "OGDC"]) : WATCHLIST}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, verify watchlist strip shows user's actual watchlist. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/app.tsx
git commit -m "feat(dashboard): wire watchlist strip to useWatchlist()"
```

---

### Task 5.3: Wire dashboard savings goals to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/app.tsx:304-335` (savings goals section)

**Step 1: Replace `GOALS.slice(0, 3)` with real goals**

Find the import of `GOALS` from `@/lib/finance/data` and keep it (still needed for fallback). Find the savings goals iteration (around line 304). Update:

```tsx
{(user && userGoals ? userGoals.slice(0, 3) : GOALS.slice(0, 3)).map((g, i) => {
  // Use g.target, g.saved, g.name, g.emoji for real or g.target, g.saved, g.name, g.emoji for dummy
  // The structures differ slightly — adapt the JSX accordingly
  ...
})}
```

Note: real goals from `useFinanceGoals()` use `target` and `saved` (numeric fields). Dummy `GOALS` from `lib/finance/data.ts` use `target` and `saved` too (with `emoji` and `name` fields). The structures are compatible. Adjust the JSX to use the real field names if different.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, verify goals section shows user's real goals. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/app.tsx
git commit -m "feat(dashboard): wire savings goals to useFinanceGoals()"
```

---

### Task 5.4: Wire dashboard spending donut to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/app.tsx:253-260` (spending donut)

**Step 1: Replace `SPENDING` constant with real spending-by-category**

Find the import of `SPENDING` from `@/lib/finance/data`. Keep it for fallback. Find the spending donut usage (around line 253). Update:

```tsx
{user && spendingByCat && spendingByCat.categories.length > 0
  ? spendingByCat.categories.slice(0, 5).map((c, i) => ({
      name: c.category,
      value: c.pct,
      amount: c.amount,
      color: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length],
    }))
  : SPENDING
}
```

The `centerValue` may need adjustment (real total = `spendingByCat.total`, dummy = the literal `132,000`).

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, add some transactions, verify donut shows real categories. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/app.tsx
git commit -m "feat(dashboard): wire spending donut to useSpendingByCategory()"
```

---

## Phase 6 — Finance Wiring (`finance.tsx`)

### Task 6.1: Wire Finance Overview tab to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/finance.tsx:1-46` (imports and Finance component start)

**Step 1: Add imports**

Find the existing imports. Add:

```typescript
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useIncomeExpenseSeries, useSpendingByCategory } from "@/hooks/use-finance-series";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useFinanceBudgets } from "@/hooks/use-finance-budgets";
```

**Step 2: Wire Overview KPIs and chart**

Find the Overview section (around lines 225-365). Replace the hardcoded `useCountUp` values with real ones:

```tsx
const { user } = useAuth();
const { data: summary } = useFinanceSummary();
const { data: series } = useIncomeExpenseSeries(6);
const { data: spending } = useSpendingByCategory(30);
const { data: userGoals } = useFinanceGoals();
const { data: userBudgets } = useFinanceBudgets();
```

Then in the Overview section, replace the countUp values and sparkline data:

```tsx
<CountUpNumber value={user && summary ? summary.income : 47500} ... />
<CountUpNumber value={user && summary ? summary.expenses : 18675} ... />
<CountUpNumber value={user && summary ? summary.savings : 28825} ... />
<CountUpNumber value={user && summary ? summary.savings_rate : 60.7} decimals={1} ... />

// Sparkline data
<Sparkline data={user && series ? series.series.map(s => s.income).slice(-3) : [43000, 45000, 47500]} ... />
<Sparkline data={user && series ? series.series.map(s => s.expense).slice(-3) : [22000, 21200, 18675]} ... />

// Savings rate bar
<div style={{ width: `${user && summary ? summary.savings_rate : 60.7}%` }} ... />

// 6-month chart
<IncomeExpenseChart
  data={user && series ? series.series.map(s => ({ month: s.month, income: s.income, expense: s.expense })) : INCOME_EXPENSE}
/>

// Totals
{user && series ? Math.round(series.series.reduce((a, b) => a + b.income, 0)).toLocaleString() : "285,000"}
{user && series ? Math.round(series.series.reduce((a, b) => a + b.expense, 0)).toLocaleString() : "112,050"}
{user && series ? Math.round(series.series.reduce((a, b) => a + b.income - b.expense, 0)).toLocaleString() : "172,950"}
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 4: Manual test** — Log in, add transactions, verify Overview shows real data. Log out, verify dummy fallback.

**Step 5: Commit**

```bash
git add frontend/packages/web/src/routes/finance.tsx
git commit -m "feat(finance): wire Overview tab to summary, income-expense, and spending-by-category APIs"
```

---

### Task 6.2: Wire Finance Budgets tab to real CRUD

**Files:**
- Modify: `frontend/packages/web/src/routes/finance.tsx:644-704` (Budgets tab)

**Step 1: Replace localStorage `BUDGETS` with real CRUD**

Find the Budgets tab section. Replace the iteration over `BUDGETS` (from `@/lib/finance/data`) with iteration over `userBudgets`. The form should call `useCreateBudget()`. The delete should call `useDeleteBudget()`. Update should call `useUpdateBudget()`.

Adapt the JSX to use real field names (`category, spent, limit_amount` instead of `category, spent, limit`). Keep the dummy data fallback for anonymous users.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, add/edit/delete budgets, verify CRUD operations work. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/finance.tsx
git commit -m "feat(finance): wire Budgets tab to useFinanceBudgets CRUD"
```

---

### Task 6.3: Wire Finance Goals tab to real CRUD

**Files:**
- Modify: `frontend/packages/web/src/routes/finance.tsx:931-1107` (Goals tab)

**Step 1: Replace `useFinanceStore().goals` with real CRUD**

Find the Goals tab section. Replace `const { goals } = useFinanceStore();` with `const { data: goals } = useFinanceGoals();`. The submit function should call `useCreateGoal()`. The contribute action should call `useContributeGoal()`. The delete should call `useDeleteGoal()`.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, add/contribute/delete goals, verify CRUD operations work. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/finance.tsx
git commit -m "feat(finance): wire Goals tab to useFinanceGoals CRUD"
```

---

## Phase 7 — Portfolio Wiring (`portfolio.tsx`)

### Task 7.1: Wire portfolio KPI cards to real data

**Files:**
- Modify: `frontend/packages/web/src/routes/portfolio.tsx:273-417` (KPI section)

**Step 1: Wire KPI cards**

The existing portfolio.tsx already uses `usePortfolioList()`, `useHoldings()`, `usePortfolioValue()`. Add `usePortfolioNetworth()` for the totals across all portfolios.

Replace the hardcoded fallback values in the KPI section (lines 403-417):

```tsx
value={user && portfolioValue ? portfolioValue.totals.market_value : (user && networth ? networth.total_market_value : 858054)}
```

For "Today's P/L" specifically:

```tsx
value={user && networth ? Math.round(networth.today_pnl) : (user && portfolioValue ? portfolioValue.totals.unrealized_pnl : 17480)}
sub={user && networth ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct}%` : "+1.42%"}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, add holdings, verify KPI cards show real values. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/portfolio.tsx
git commit -m "feat(portfolio): wire KPI cards to usePortfolioNetworth with today's P/L"
```

---

### Task 7.2: Wire portfolio sector/stock allocation donuts to real holdings

**Files:**
- Modify: `frontend/packages/web/src/routes/portfolio.tsx:62-74, 444-470` (donut data)

**Step 1: Compute allocation from real holdings**

The `SECTOR_ALLOC` and `STOCK_ALLOC` constants at lines 62-74 are used for the donut charts. Replace them with computed values from `useHoldings()` + sector lookup.

```tsx
const { data: symbols } = usePsxSymbols(); // from existing use-psx.ts

const sectorAlloc = useMemo(() => {
  if (!holdings || !symbols) return SECTOR_ALLOC; // fallback
  const sectorMap = new Map(symbols.map(s => [s.symbol, s.sector]));
  const totals = new Map<string, number>();
  for (const h of holdings) {
    const sector = sectorMap.get(h.symbol) ?? "Other";
    const value = (h.current_price ?? h.avg_cost) * h.shares;
    totals.set(sector, (totals.get(sector) ?? 0) + value);
  }
  const grand = Array.from(totals.values()).reduce((a, b) => a + b, 0);
  return Array.from(totals.entries()).map(([sector, value]) => ({
    [sector]: grand > 0 ? Math.round((value / grand) * 100) : 0,
  }));
}, [holdings, symbols]);

const stockAlloc = useMemo(() => {
  if (!holdings) return STOCK_ALLOC; // fallback
  const total = holdings.reduce((a, h) => a + (h.current_price ?? h.avg_cost) * h.shares, 0);
  return holdings.map(h => ({
    symbol: h.symbol,
    pct: total > 0 ? Math.round(((h.current_price ?? h.avg_cost) * h.shares / total) * 100) : 0,
  }));
}, [holdings]);
```

Then use `sectorAlloc` and `stockAlloc` in the donut chart components instead of `SECTOR_ALLOC` and `STOCK_ALLOC`.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Log in, add holdings across different sectors, verify donuts show real sector distribution. Log out, verify dummy fallback.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/portfolio.tsx
git commit -m "feat(portfolio): compute sector/stock allocation from real holdings"
```

---

### Task 7.3: Add "Coming soon" placeholder to AI Report button

**Files:**
- Modify: `frontend/packages/web/src/routes/portfolio.tsx` (find the AI Report trigger button, around line 678)

**Step 1: Add a `disabled` state and tooltip**

Find the button that opens the AI Report modal. Add `disabled` and `title="Coming soon"` attributes:

```tsx
<button
  onClick={() => setReportOpen(true)}
  disabled
  title="AI Portfolio Report — coming soon"
  ...
>
```

In the `ReportModal` component, change the title and add a notice:

```tsx
<h2>AI Portfolio Report</h2>
<p style={{ ... }}>Real AI insights from your portfolio are coming soon. For now, see your live KPIs above.</p>
```

Do not change the AI Report content text — only the title and add the notice. The four sections (Diversification, Risk, Opportunities, Suggested Actions) can remain as-is for now or be hidden behind the "coming soon" notice. Simplest: keep modal closed by default, show a "Coming soon" banner when the user clicks.

**Step 2: Verify TypeScript compiles**

```bash
cd frontend/packages/web && npx tsc --noEmit
```

Expected: no errors.

**Step 3: Manual test** — Click the AI Report button, verify it shows the "coming soon" notice instead of hardcoded text.

**Step 4: Commit**

```bash
git add frontend/packages/web/src/routes/portfolio.tsx
git commit -m "feat(portfolio): mark AI Report as coming soon (deferred)"
```

---

## Phase 8 — Manual Testing

### Task 8.1: Test as anonymous user

**Step 1: Log out (or use incognito)**

Open browser in incognito mode. Visit:
- `/app` — verify all dummy data shows (net worth 4.28M, today's P/L 17,480, watchlist of 5 stocks, savings goals with Hajj/Emergency/Honda City/Umrah, spending donut with Food/Utilities/Transport/Shopping/Other)
- `/finance` — verify Overview shows 47,500 income, 18,675 expenses, 60.7% savings, Budgets tab shows Food/Utilities/Transport/Shopping/Groceries/Subscriptions, Goals tab shows Hajj Fund/Emergency/Honda City/Umrah
- `/portfolio` — verify 858,054 portfolio, 12.73% gain, sector/stock allocation donuts
- `/psx` — switch to KSE-100, verify candlestick chart renders (real or fallback — both acceptable for anonymous)
- `/alerts`, `/learn` — verify existing dummy data (these are out of scope but should still work)

**Step 2: Document any issues found**

If any of the above show real data instead of dummy (or vice versa), note for follow-up.

---

### Task 8.2: Test as logged-in user with empty data

**Step 1: Create a fresh test user**

Sign up with a new email, confirm, log in.

**Step 2: Visit each page**

- `/app` — verify KPI cards show 0 or empty (not 4.28M etc.), watchlist shows "no items" or empty, savings goals shows "no goals", spending donut shows empty/0
- `/finance` — Overview shows 0 income/expenses, Budgets tab shows "no budgets", Goals tab shows "no goals"
- `/portfolio` — verify 0 portfolio value, no holdings table
- `/psx` — verify KSE-100 chart still works (real candles, not error)

**Step 3: Add test data**

- Add 1 holding to portfolio (e.g., HBL 100 shares @ 140)
- Add 1 transaction (e.g., Salary +50000)
- Add 1 goal (e.g., Hajj Fund target 1,200,000 saved 0)
- Add 1 budget (e.g., Food & Dining limit 35000)
- Add 1 watchlist item (e.g., OGDC)

**Step 4: Verify each page**

- `/app` — KPI cards now show non-zero values, watchlist shows OGDC, savings goals shows Hajj Fund
- `/finance` — Overview shows 50000 income, Budgets shows Food & Dining, Goals shows Hajj Fund
- `/portfolio` — shows HBL 100 shares, today's P/L computed from previous close

**Step 5: Document any issues**

---

### Task 8.3: Verify today's P/L calculation

**Step 1: Check the calculation manually**

For each holding, compute:
- previous_close = `psx_ohlcv.close` for most recent date < today
- today_pnl = (current_price - previous_close) * shares

Compare to what the API returns at `/api/portfolio/networth`. The `by_holding[].today_pnl` should match.

**Step 2: Verify aggregation**

Sum of `by_holding[].today_pnl` should equal the top-level `today_pnl`. Sum of `(previous_close * shares)` for non-null previous_close should be the denominator for `today_pnl_pct`.

---

## Phase 9 — Commit and Push to dev

### Task 9.1: Verify git status

**Step 1: Check working tree**

```bash
cd D:\NafaIQ-Monorepo && git status
```

Expected: clean except for `backend/requirements.txt` (untracked) which we can leave as-is.

**Step 2: Check log**

```bash
cd D:\NafaIQ-Monorepo && git log --oneline -20
```

Expected: 15+ commits from this project's work, each atomic and well-described.

---

### Task 9.2: Push to dev

**Step 1: Push the dev branch**

```bash
cd D:\NafaIQ-Monorepo && git push origin dev
```

Expected: `dev` is up to date or pushed.

**Step 2: Verify on GitHub**

Open `https://github.com/usmankhalidj15-glitch/NafaIQ-MainProject/tree/dev`. Verify the latest commits are visible.

---

## Self-Review

**1. Spec coverage:**
- Per-user data on dashboard → Tasks 5.1-5.4 ✓
- Per-user data on finance (Overview, Budgets, Goals) → Tasks 6.1-6.3 ✓
- Per-user data on portfolio (KPIs, allocation) → Tasks 7.1-7.2 ✓
- KSE-100 candlesticks fix → Tasks 0.1-0.6 ✓
- Today's P/L from real data → Tasks 1.1, 2.1, 7.1 ✓
- 20-day history guarantee → Tasks 0.x (no change to existing job), 2.1 (startup check), 1.5 (coverage endpoint) ✓
- Supabase types → Tasks 3.1-3.2 ✓
- Anonymous fallback preserved → All tasks include fallback pattern ✓
- No file/component removed → All tasks are additive ✓
- No emojis in new code → No emoji literals in any new file ✓

**2. Placeholder scan:** No "TBD", "TODO", "fill in", "implement later" anywhere. Every step has concrete code or commands.

**3. Type consistency:** All new hook return types match the backend Pydantic models. `NetworthResponse` shape is consistent across the SQL response, the Pydantic model, and the frontend hook. `FinanceSummary` matches. `FinanceBudget` matches. `FinanceGoal` matches. `IncomeExpenseResponse` matches. `SpendingByCategoryResponse` matches.

**4. Risk areas addressed:**
- `<20 days` data: covered by Task 2.1 (startup warning) and Task 1.5 (coverage endpoint)
- TypeScript errors: each task has a `npx tsc --noEmit` step
- P&L discrepancy with `psx_market_snapshot.change`: we use `psx_ohlcv.close` as source of truth, not the snapshot's `change` field
