# Week 7 Presentation Prep — End-to-End Project Demo

> **NafaIQ** — a Pakistan Stock Exchange terminal + AI investment signals +
> inflation-aware personal finance, in one bilingual app on **web and mobile**,
> backed by **one** FastAPI backend and **one** Supabase project.
>
> This doc is your on-stage reference. Every path below is **real and verified**
> against the current tree (`file.py:NNN` = the exact line). If a judge says
> "show me the code for X", jump to the **Feature → Code Map** (§3) or the
> **"Show me…" quick index** (§4).

---

## 1. The 1–2 Minute Intro (say this)

> "NafaIQ is a single app that replaces the three things a Pakistani investor
> normally juggles across separate tools: a **market terminal** for the Pakistan
> Stock Exchange, an **AI layer** that turns raw numbers into guidance, and
> **inflation-aware personal finance**.
>
> It runs on **two front-ends — a web PWA and a React Native mobile app** — that
> share one FastAPI backend, one Supabase database, and one set of TypeScript
> contracts, so a feature built once is consistent everywhere. It's fully
> **bilingual (English + Urdu with RTL)**, has **light and dark themes**, and a
> custom **liquid-glass design system**.
>
> Three things make it more than a data dashboard:
> 1. **Signals V2** — a machine-learning engine that emits tiered buy/hold/sell
>    signals across 5/20/60-day horizons, and it runs behind a *shadow-mode
>    promotion gate*, so the ML never drives production until it beats the
>    technical baseline. Every signal is cross-checked against a TradingView
>    consensus, a trend-state read, and live foreign-investor flow, and we keep
>    an **audited, insert-only track record** of how past signals actually did.
> 2. **A verified AI layer** — market briefs, stock analyses and a conversational
>    **agent** that can *act* (add a transaction, set an alert, manage your
>    watchlist) by voice or text. Every generated number is citation-verified and
>    guardrailed so the AI can't fabricate a figure or give directive advice.
> 3. **Haqeeqi Daulat** — a devaluation-adjusted net-worth engine that shows your
>    *real* purchasing power, not just a nominal rupee number — plus budgets,
>    goals, bills, and a PKR-native Zakat calculator.
>
> Today I'll walk it end-to-end on both web and mobile, and I'm happy to open any
> part of the codebase you want to see."

**Tech in one breath:** React 19 + TanStack Start (web PWA) · React Native + Expo
SDK 54 (mobile) · FastAPI + scikit-learn/LightGBM/XGBoost/CatBoost (backend) ·
Supabase Postgres/Auth/Realtime · deployed on **Vercel** (web) and **Railway**
(backend, from `main`). Monorepo: Turborepo + pnpm workspaces.

---

## 2. Recommended Demo Flow (~10–12 min, end-to-end)

Pick web **or** mobile as your "primary" screen and use the other to show parity.
Order is designed so each step sets up the next.

| # | Show | Why it lands | Primary surface |
|---|------|--------------|-----------------|
| 1 | **Login → Dashboard** | One account, instant net-worth + KSE-100 + AI nudge | Web `/app` or mobile Dashboard |
| 2 | **PSX terminal**: index cards, candlestick, **sector heatmap**, screener | "This is a real market terminal, live PSX data" | Web `/psx` |
| 3 | **Stock detail** (e.g. HBL): **Signals V2 verdict** + context tiles + **track record** + AI analysis | The flagship — ML signal, honestly measured | Web `/stock/HBL` |
| 4 | **NafaIQ Assistant** (voice): *"Add a transaction of 1200 for food via Meezan card"* → confirm card → it lands in Finance | The wow moment: AI that *acts*, by voice | **Mobile** (`/assistant`) |
| 5 | **Finance**: the transaction now shows; then **Zakat calculator** + **Haqeeqi Daulat** | Closes the loop; the inflation-aware angle | Web `/finance` + `/portfolio` |
| 6 | **Email bank-import** (Settings → connect Gmail) *or* explain it | Auto-imports real bank alerts → transactions | Web `/settings` |
| 7 | **Mobile parity** — same account, liquid-glass UI, instant wallpaper | "Everything you saw, in your pocket" | Mobile |

### The single best live demo
**The Assistant acting by voice (step 4).** It's the most memorable and touches
the whole stack: mic → Whisper transcription → LLM agent → a *draft* the user
confirms → a real DB write → the Finance screen refreshing. If you show one
thing, show this.

### Demo prep checklist (do this BEFORE you present)
- **Warm the AI report caches**: open Dashboard + PSX and hit refresh on each AI
  popup once. Reports are day-cached, so warmed ones render instantly with no
  live LLM call on stage. (`report_service.py` single-flight + cooldown.)
- **Mobile**: cold-start once so the contour wallpaper is cached (we just made it
  instant — `GlassScreen` via expo-image + `WallpaperWarmup`); pre-grant the mic
  permission so the voice demo doesn't stall on the OS prompt.
- **Assistant quota**: 40 turns/day per user — don't burn them all rehearsing on
  the demo account.
- **Have a fallback**: if a provider is rate-limited, reports still serve from
  cache; the signal/track-record/heatmap are all deterministic and always work.

---

## 3. Feature → Code Map

Everything is a monorepo: `backend/` (FastAPI), `frontend/packages/web` (React),
`frontend/packages/mobile` (Expo), `frontend/packages/shared` (`@nafaiq/shared`
TS contracts). **All backend routes are under the `/api` prefix** (mounted in
`backend/src/app/main.py:183–206`).

### 3.1 Auth (Supabase + Google OAuth)
- **Web:** `/auth` → `src/routes/auth.tsx` → `src/features/auth/AuthPage.tsx`;
  logic `src/hooks/use-auth.tsx` (`signInWithPassword`, `signInWithOAuth`)
- **Mobile:** `src/app/auth.tsx` → `src/components/auth/AuthExperience.tsx`;
  `src/hooks/use-auth.tsx` — Google via `expo-web-browser` deep-link
  (`scheme: nafaiqmobile`)
- **Backend:** `middleware/auth.py` — two tiers: Supabase **JWT** for user paths,
  shared **PSX token** for public market data.

### 3.2 Dashboard
- **Web:** `/app` → `src/routes/app.tsx` → `src/features/dashboard/Dashboard.tsx`
  (`components/DashboardCharts.tsx`, `DashboardRecommendation.tsx`, `MacroWidget.tsx`)
- **Mobile:** `src/app/(tabs)/app.tsx` (+ `components/dashboard/TopRibbon.tsx` —
  the account menu, and the **only** entry to the Assistant)
- **AI nudge hook:** web `src/hooks/ai/use-dashboard-recommendation.ts` →
  `GET /api/ai/report/dashboard-recommendation`

### 3.3 PSX Market Terminal
- **Web:** `/psx` → `src/routes/psx.tsx` → `src/features/psx/PSX.tsx`
  - Index cards `components/PsxIndexOverview.tsx`, screener `PsxScreenerCard.tsx`,
    heatmap `PsxSectorHeatmap.tsx` + `src/features/heatmap/Treemap.tsx`
  - Candlestick `src/components/charts/CandlestickChart.tsx`
- **Mobile:** `src/app/(tabs)/psx.tsx` + `components/psx/SectorHeatmap.tsx`
- **Backend:** `api/market.py` + `api/market_v2.py` — `GET /api/market/snapshot`,
  `/api/index/cards`, `/api/market/treemap` (heatmap), `POST /api/screener`.
  Logic in `services/market/` (`heatmap.py`, `treemap.py`, `screener.py`);
  scrapers in `scrapers/` (`tradingview.py`, `dps.py`, …)

### 3.4 Stock Detail + **Signals V2** (flagship)
- **Web:** `/stock/$ticker` → `src/routes/stock.$ticker.tsx` →
  `src/features/stock/StockDetail.tsx`
  - Signals: `src/features/signals/` — `SignalBreakdownPanel.tsx`,
    `SignalContextTiles.tsx`, `SignalTrackRecordCard.tsx`, `SignalConfidence.tsx`
  - AI analysis: `src/features/stock/components/StockAnalysisReportCard.tsx`
- **Mobile:** `src/app/stock/[ticker].tsx` + `components/psx/SignalContextTiles.tsx`,
  `components/psx/SignalTrackRecordCard.tsx` (hook `usePsxSignalV2` in
  `hooks/queries/use-market.ts`)
- **Backend:** `api/signals.py` — `GET /api/signals/v2/{symbol}?horizon=`,
  `GET /api/signals/v2/{symbol}/breakdown`, `GET /api/signals/v2/track-record`,
  `GET /api/signals/v2/leaderboard`
  - **The ML engine:** `services/signals_v2/`
    - `engine.py::get_signal()` — loads inputs → adjusts OHLCV → model score →
      fuse → decorate with trend + flow + consensus
    - `fusion.py::fuse_signal()` — blends ML + fundamentals through an
      actionability gate
    - `ranking.py` — triple-barrier labeling, purged walk-forward CV
    - `outcomes.py::aggregate_track_record()` — the audited, insert-only history
    - `trend_state.py::classify_trend()`, `risk_metrics()`
  - **Cross-checks:** `services/market/flow_context.py` (foreign FIPI flow),
    `services/market/tv_ratings.py` (TradingView consensus)

### 3.5 NafaIQ Assistant (voice + text agent)
- **Web:** entry = "Ask NafaIQ AI" in `src/components/layout/Sidebar.tsx` →
  `src/features/assistant/AssistantPanel.tsx` (mic `components/MicButton.tsx`,
  draft `components/ActionDraftCard.tsx`); client `src/lib/assistant/client.ts`
- **Mobile:** `src/app/assistant.tsx` (entered from `TopRibbon` account menu)
  - hook `src/hooks/ai/use-assistant-chat.ts`
  - client `src/lib/assistant/client.ts` (**`expo/fetch` SSE stream**),
    `src/lib/assistant/mappings.ts` (web→mobile query-key & route translation)
  - components `src/components/assistant/ActionDraftCard.tsx`,
    `AssistantMicButton.tsx` (**expo-audio**, records m4a → transcribe)
- **Backend:** `api/assistant.py` — `POST /api/assistant/chat` (SSE),
  `/execute`, `/transcribe` (Whisper), `GET /usage`
  - Agent loop: `services/assistant/agent.py::run_turn()` (`agent.py:146`)
  - Tool registry: `services/assistant/tools.py::TOOLS` (`tools.py:191`) —
    read tools run inline, **write** tools return a draft to confirm, **nav**
    tools navigate. Confirmed writes execute via `services/assistant/execute.py`.

### 3.6 AI Reports (market brief / stock / portfolio / finance / daily nudge)
- **Web:** `/ai-insights` → `src/routes/ai-insights.tsx`; hooks in
  `src/hooks/ai/` (`use-market-brief.ts`, `use-ai-report.ts`, …); client
  `src/lib/ai/reports-client.ts`
- **Mobile:** `src/hooks/ai/use-ai-report.ts`, surfaced via
  `components/ai/AiReportSheet.tsx`
- **Backend:** `api/reports.py` — `GET /api/ai/report/market-brief`, etc.
  - Generation: `services/ai/engine/__init__.py`; **Gemini→Groq failover**
    `services/ai/providers.py::make_report_failover_client()` (`providers.py:813`)
  - Caching/serving: `services/ai/report_service.py`; trust layer
    `services/ai/verify.py` (citation check) + `guardrails.py` (no directive advice)
  - Prompts: file-based store `backend/prompts/*.txt` (loaded by
    `services/ai/prompts.py`)

### 3.7 Finance (transactions, budgets, bills, goals, payment methods, Zakat)
- **Web:** `/finance` → `src/routes/finance.tsx` → `src/features/finance/Finance.tsx`
  (`components/Transactions.tsx`, `Budgets.tsx`, `Bills.tsx`, `Goals.tsx`)
  - **Zakat:** `src/features/finance/zakat/` — logic `zakat.logic.ts`
    (+ `zakat.logic.test.ts`), UI `Zakat.tsx`, PDF export `zakat-pdf.ts`
- **Mobile:** `src/app/(tabs)/finance.tsx` (tabs: Overview/Transactions/Budgets/
  Bills/Goals/Zakat) + `components/finance/PaymentMethodPicker.tsx`
- **Backend:** `api/finance.py` (CRUD, payment-methods, `/vocabulary`, summary) +
  `api/finance_extended.py` (Zakat: `POST /api/finance/zakat/calculate`). Logic in
  `services/finance/` (`zakat.py`, `payment_methods.py`, `categories.py`)

### 3.8 Portfolio + **Haqeeqi Daulat**
- **Web:** `/portfolio` → `src/routes/portfolio.tsx` →
  `src/features/portfolio/Portfolio.tsx`; real-returns card
  `components/HaqeeqiDaulat.tsx`
- **Mobile:** `src/app/(tabs)/portfolio.tsx` ("Haqeeqi Daulat™ — Real Returns")
- **Backend:** `api/portfolio.py` + `api/portfolio_extended.py` — `/portfolio/networth`,
  `/allocation`, `/performance`. Logic in `services/portfolio/networth.py`
  (`performance_vs_kse100()`). *Note: "Haqeeqi Daulat" is the front-end branding;
  the devaluation/real-returns math lives in `networth.py`.*

### 3.9 Email Bank-Import (Gmail → transactions)
- **Web:** `/settings` → `src/routes/settings.tsx` → `BankEmailCard`; hook
  `src/hooks/use-email-integration.ts`
- **Backend:** `api/integrations.py` — `GET /api/integrations/gmail/connect`,
  `/callback`, `POST /api/integrations/email/sync`
  - Pipeline: `services/email_import/` — `pipeline.py::sync_user()` (`:165`) →
    `_parse_message()` (`:78`) runs `rules.py::parse()` (`:320`) + `sanitize.py`
    then `llm.py` (LLM fallback) → writes transaction/bill. Sender allowlist in
    `senders.py`. (This is the parsing we hardened for Alfalah/Meezan alerts.)

### 3.10 Learn Hub + AI Tutor
- **Web:** `/learn` → `src/routes/learn.tsx`; `src/features/learn/`
  (`hub/LearnHub.tsx`, `lesson/LessonPage.tsx`); tutor `src/lib/ai/tutor-client.ts`
- **Mobile:** `src/app/(tabs)/learn/`; tutor `src/components/TutorSheet.tsx`,
  `src/hooks/ai/use-tutor-chat.ts`
- **Backend:** `api/learn.py` + `api/learn_ai.py`; tutor `POST /api/ai/tutor` (SSE)

### 3.11 Alerts + Notifications
- **Web:** `/alerts` → `src/routes/alerts.tsx` → `src/features/alerts/Alerts.tsx`
- **Mobile:** `src/app/alerts.tsx`
- **Backend:** `api/alerts.py` + `api/notifications.py`. Evaluation in
  `services/alerts/evaluator.py` (price alerts, watchlist moves, **bill-due
  auto-alerts**). Email dispatch `services/notifier.py` (**Brevo** primary,
  Resend fallback). Scheduled by `jobs/scheduler.py`.

---

## 4. "Show me the code for…" — Quick Index

When a judge points at something, here's the one file to open first.

| Judge asks… | Open this |
|---|---|
| "How does the ML signal actually work?" | `backend/src/app/services/signals_v2/engine.py` → `fusion.py` |
| "How do you know the signals are any good?" | `services/signals_v2/outcomes.py::aggregate_track_record()` |
| "Show the AI agent that takes actions" | `backend/src/app/services/assistant/agent.py:146` + `tools.py:191` |
| "How does voice work?" | mobile `src/components/assistant/AssistantMicButton.tsx` → backend `api/assistant.py` `/transcribe` |
| "Can the AI make up numbers?" | `services/ai/verify.py` + `guardrails.py` (it's blocked) |
| "What if the AI provider is down?" | `services/ai/providers.py:813` `make_report_failover_client` (Gemini→Groq) |
| "How does the bank-email import parse?" | `services/email_import/pipeline.py:78` + `rules.py:320` |
| "The Zakat math" | web `src/features/finance/zakat/zakat.logic.ts` (+ tests) |
| "Real / inflation-adjusted returns" | `backend/services/portfolio/networth.py` |
| "Same feature on mobile?" | mirror path under `frontend/packages/mobile/src/app/` |
| "Where's the design system?" | mobile `src/components/glass/` + `src/constants/theme.ts` |
| "How do web & mobile share types?" | `frontend/packages/shared/src/api.ts` (`@nafaiq/shared`) |

---

## 5. Architecture (one slide)

```
┌── frontend/packages/web  (React 19, TanStack Start SSR, PWA, Vercel)
│      routes/*  ──►  features/*  ──►  hooks/*  ──►  lib/*/client.ts
│
├── frontend/packages/mobile (Expo SDK 54, RN 0.81.5, expo-router)
│      app/*  ──►  hooks/queries/*, hooks/ai/*  ──►  lib/api.ts
│
├── frontend/packages/shared  (@nafaiq/shared — TS API DTOs, shared by both)
│
└── backend  (FastAPI, Railway from `main`)
       api/*.py  ──►  services/*  ──►  Supabase (Postgres/Auth/Realtime)
       + scrapers/*, jobs/scheduler.py (cron), ML models (signals_v2)
```

- **One Supabase project + one FastAPI backend** serve both front-ends — the same
  account, data, and contracts everywhere.
- **Auth tiers** (`middleware/auth.py`): Supabase JWT for user data, a shared PSX
  token for public market data.
- **AI providers:** Gemini primary → Groq failover, one OpenAI-compatible SDK;
  Whisper (Groq) for voice; Langfuse for tracing.

---

## 6. Anticipated Q&A

- **"Is the ML signal actually live / real?"** — It's real but gated: ML runs in
  *shadow mode* behind a promotion check (`signals_v2`), so a model only drives
  production once it beats the technical baseline. Whatever's shown, the
  **track record** (`outcomes.py`) is measured against real post-publication
  prices and is insert-only — never edited.
- **"Can the AI give bad financial advice / hallucinate a number?"** — No: report
  numbers are citation-verified (`verify.py`) and directive buy/sell/allocate
  language is banned by guardrails (`guardrails.py`). The agent only *drafts*
  write-actions; the user confirms before anything is saved.
- **"Web and mobile — is it two codebases doing the same thing twice?"** — They're
  separate UIs but share one backend, one Supabase project, and one set of TS
  contracts (`@nafaiq/shared`). Web is the source of truth; mobile mirrors it.
- **"What's original vs. off-the-shelf?"** — The signal engine, the verified/
  guardrailed AI layer, the acting agent, the bank-email parser, Haqeeqi Daulat,
  and the PKR-native Zakat calculator are all ours. We stand on FastAPI, Supabase,
  Expo, and the LLM providers.
- **"How do you get PSX data?"** — Scrapers in `backend/src/app/scrapers/`
  (TradingView, DPS, PSX financials, MUFAP, Business Recorder, SBP) on scheduled
  jobs (`jobs/scheduler.py`), stored in Supabase.
- **"Voice — which language?"** — Both. The mic sends an `en`/`ur` hint to Whisper,
  and the whole app is bilingual with RTL Urdu.

---

## 7. Facts to have on hand

- **Stack:** React 19 · TanStack Start · Expo SDK 54 · **React Native 0.81.5** ·
  FastAPI · scikit-learn/LightGBM/XGBoost/CatBoost · Supabase · Turborepo/pnpm.
- **Deploy:** web → Vercel (PWA, installable); backend → Railway from `main`.
- **Signals horizons:** 5D / 20D / 60D. **Signal tiers:** STRONG BUY · BUY · HOLD ·
  SELL · STRONG SELL.
- **Assistant limits:** 40 turns/day per user; voice clip ≤ 30s / 5 MB.
- **Bilingual:** English + Urdu (RTL); light + dark; liquid-glass UI.
- **Repo layout:** `backend/`, `frontend/packages/{web,mobile,shared}`.

> All paths verified against the working tree on branch `tayyib`
> (== `dev`). If something's moved by demo day, `grep -rn "<symbol>" backend/src`
> or check the route file in `frontend/packages/{web/src/routes, mobile/src/app}`.
