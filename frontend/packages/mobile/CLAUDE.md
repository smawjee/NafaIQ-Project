# NafaIQ Mobile — Project Directives (CLAUDE.md)

React Native **Expo** app that mirrors the NafaIQ web app, which lives in this
monorepo at **`frontend/packages/web`** (see §0). The web app is the **source
of truth** for every feature. This file governs ALL work in this package —
read it before each task and keep it under 300 lines.

Dev environment is **Windows + Linux only**. Never add macOS- or Swift-specific
dependencies, native modules, or build steps. iOS is built via Expo
(EAS / Expo Go), never a local Mac toolchain.

---

## 0. Web Source of Truth (HARD)

- This package lives in the **nafaiq-monorepo**; the web app is a sibling
  package at `frontend/packages/web` and the FastAPI backend at `backend/`.
  Consult them directly — the old standalone-repo `zenith-main` mirror-branch
  workflow is obsolete.
- Before building or changing any screen, open the corresponding web source
  (`frontend/packages/web/src/routes/*`, `src/features/*`, `src/hooks/*`) and
  match functionality and data contracts. Backend endpoint contracts live in
  `backend/src/app/api/*.py`.
- Shared pure-TS types/content live in `@nafaiq/shared`
  (`frontend/packages/shared`) — API DTOs (`api.ts`, kept in sync with web's
  `src/lib/psx/types.ts`), formatters, and Learn content.

## 1. Framework Rules (HARD)

- **Expo best practices throughout.** Stay on the managed workflow. Use Expo
  SDK modules (`expo-*`) before third-party native modules. Add native deps
  only via `npx expo install` so versions match the SDK. Never hand-edit
  `ios/` or `android/` native projects — use config plugins in `app.json`.
- **expo-router** (file-based) is the routing system — it mirrors the web app's
  file-based TanStack Router. Routes live in `src/app/`.
- **Optimize list rendering.** Any scrolling collection (transactions, lessons,
  screener rows, glossary, holdings, notifications) MUST use a virtualized list
  (`FlatList`/`SectionList`, or `FlashList` where installed) — never `.map()`
  inside a `ScrollView` for unbounded data. Provide `keyExtractor`,
  `getItemLayout` where rows are fixed-height, and memoized `renderItem`.
- **Consistent cross-platform UI.** Every screen must look and behave correctly
  on **both Android and iOS**. Respect safe areas with
  `react-native-safe-area-context`. Use `Platform.select` for unavoidable
  divergences. Test both platforms before considering UI work done.
- Animations use `react-native-reanimated` (worklets) — honor
  `prefers-reduced-motion` (`AccessibilityInfo.isReduceMotionEnabled`), matching
  the web app's reduced-motion behavior.

## 2. QA & Testing (HARD)

- **Mobile accessibility is mandatory** for all new UI:
  - **Touch targets ≥ 44×44 pt** (hitSlop where the visual is smaller).
  - **Screen-reader labels**: every interactive element needs
    `accessibilityLabel` + `accessibilityRole`; icon-only buttons must be
    labeled; decorative/icon glyphs marked `accessibilityElementsHidden`.
  - **Contrast ratios** ≥ WCAG AA (4.5:1 text). Verify against the dark theme
    tokens in §Design.
- **Component tests required for all new UI work.** Use
  `@testing-library/react-native` + `jest-expo`. Each new component ships with a
  test covering render + key interaction/accessibility. Do not mark UI work
  complete with failing or missing tests.
- Run `npx tsc --noEmit` and `npm run lint` clean before completing a task.

## 3. Asset Generation (HARD)

- Whenever visual assets are needed — UI mockups, product images, placeholder
  graphics, icons, illustrations, hero/marketing imagery — **generate them with
  the Higgsfield MCP connector**, using models such as **Kling 3.0** or
  **Seedance**. (`mcp__higgsfield__generate_image` / `generate_video`; call
  `models_explore` if unsure which model fits.)
- **Do NOT use static placeholder images** (lorem-picsum, gray boxes, stock
  filler) when generation is available.
- Generation spends credits — **confirm with the user before each batch** and
  prefer one well-specified prompt over many retries. Save outputs under
  `assets/images/` (or `assets/generated/`) and reference locally.
- App icons/splash: regenerate NafaIQ-branded assets via Higgsfield; do not ship
  the default Expo logo.

## 4. Feature Parity (HARD)

- **Continuously consult the `zenith-main` branch** (the web app source; see
  §0) during development. Before building any screen/component, open the
  corresponding web source and match functionality, data, and layout intent
  (adapted to mobile patterns).
- **Track every feature** against the checklist in §Parity Checklist below.
  Anything present in the web app must be implemented (or explicitly deferred
  with a note) in mobile. Update the checklist as features land.
- Port the web app's **pure logic verbatim** where possible (deterministic data
  generators, formatters, lesson content) so charts/numbers match exactly.

---

## Tech Stack

- Expo SDK 56, React Native 0.85, React 19, expo-router (typed routes).
- **State:** `@tanstack/react-query` (provider wired; web app keeps it for
  future live data) + React Context for auth & learn progress.
- **Backend:** `@supabase/supabase-js` — auth + `profiles` table only.
- **Storage:** `@react-native-async-storage/async-storage` (Supabase session +
  learn progress; replaces web `localStorage`). Tokens may use
  `expo-secure-store`.
- **Auth:** email/password + Google OAuth via `expo-auth-session` /
  `expo-web-browser` deep-link flow.
- **Charts:** `react-native-svg`-based (replacing web Recharts).
- **Icons:** `lucide-react-native` (web maps emoji→Lucide; do the same — avoid
  raw emoji in UI).
- `react-native-url-polyfill` is imported once at entry for supabase-js.

## Architecture / Folder Structure

```
src/
  app/                 # expo-router routes (file-based)
    _layout.tsx        # root: providers + auth gate + theme
    index.tsx          # landing OR redirect to (tabs)
    auth.tsx           # sign in / sign up
    plans.tsx          # pricing (public)
    (tabs)/            # auth-gated bottom-tab group
      _layout.tsx      # Tabs: Home, Markets, Portfolio, Finance, Learn
      app.tsx          # Dashboard
      psx.tsx          # PSX market terminal
      portfolio.tsx
      finance.tsx
      learn/
        index.tsx      # Learn hub
        lesson/[id].tsx
    alerts.tsx
    stock/[ticker].tsx
  components/          # shared UI: Card, StatCard, Change, SignalBadge,
                       # charts/, icons, primitives (Button, Sheet, Tabs…)
  hooks/               # useAuth, useLearn, useColorScheme…
    queries/           # React Query hooks per domain (live backend data)
  lib/                 # api.ts (FastAPI client), supabase.ts,
                       # database.types.ts, plan-features.ts, theme
  constants/theme.ts   # design tokens
```

- **Auth gate:** root `_layout` redirects unauthenticated users to `/auth`
  (preserving return path). Public routes: `/`, `/auth`, `/plans`.
- **Navigation:** bottom tabs (Home/Markets/Portfolio/Finance/Learn) + a
  drawer/menu for Alerts, Plans, Settings, sign-out — mirrors web `AppShell`'s
  `BottomNav` + sidebar.

## Data Layer (live — no mock domain data)

The app shares the web app's Supabase project (auth + `profiles` +
`user_watchlist` direct; realtime on `psx_market_snapshot`) and the FastAPI
backend for everything else. Two auth tiers in `src/lib/api.ts`, mirroring
web `src/lib/psx/client.ts`:

- **Public market/reference routes** (`/api/market/*`, `/api/quote/*`,
  `/api/signal*`, `/api/sectors`, …) — optional shared PSX token.
- **User-owned routes** (`/api/portfolio/*`, `/api/finance/*`, `/api/alerts*`,
  `/api/profile/plan`, `/api/watchlist`) — Supabase session JWT.

React Query hooks live in `src/hooks/queries/` (use-market, use-watchlist,
use-portfolio, use-finance, use-finance-series, use-alerts, use-plan) and
mirror the web hooks' query keys/invalidation. Full generated schema types:
`src/lib/database.types.ts` (copy of web `integrations/supabase/types.ts` —
regenerate there, then re-copy). Learn-hub content stays static from
`@nafaiq/shared` by design. Do not reintroduce mock/seeded domain data.

## Environment Variables

Expo exposes client vars prefixed `EXPO_PUBLIC_`. Create `.env.local`
(gitignored); use the SAME Supabase project as the web app so accounts work
on both platforms:
```
EXPO_PUBLIC_SUPABASE_URL=...
EXPO_PUBLIC_SUPABASE_ANON_KEY=...   # the publishable (sb_publishable_) key
EXPO_PUBLIC_API_URL=...             # FastAPI base URL; blank in dev =
                                    # auto-derive http://<metro-host>:8000
EXPO_PUBLIC_PSX_API_TOKEN=...       # optional shared token, public PSX routes
```
The AI tutor's `LOVABLE_API_KEY` must **never** ship in the client bundle — wrap
the AI gateway call in a Supabase Edge Function and call that from the app.

## Design / Theme (dark-only)

Port web `styles.css` `@theme` tokens:
`background #050816`, `surface #0d1424`, `elevated #111a2e`,
**`bull #10b981`**, **`bear #e5484d`**, **`ai/info #00d4aa`**,
**`primary #00d4aa`** (teal), **`gold #d4a017`** (premium), `warning #f5a524`,
`text-primary #fff`, `text-secondary #94a3b8`, `text-muted #64748b`,
border `rgba(255,255,255,0.06)`. Radii: badge 4 / btn 8 / card 14.
Fonts: **Inter** (sans), **JetBrains Mono** (tabular numbers), **Noto Nastaliq
Urdu** (Urdu strings in Learn). `.glass-card` → translucent surface + border.

## Parity Checklist (track here; mirror the `zenith-main` branch)

**Auth/Account:** [ ] email sign-in [ ] email sign-up (display name)
[ ] Google OAuth (deep-link) [ ] sign-out [ ] profile load [ ] route protection
[ ] plan display.
**Shell/Nav:** [ ] bottom tabs [ ] drawer (Alerts/Settings/Upgrade/sign-out)
[ ] header stock search [ ] notifications bell (mock) [ ] user menu.
**Dashboard `/app`:** [ ] greeting + KSE-100 [ ] dismissible AI rec
[ ] net-worth + 3 stat cards [ ] portfolio area chart + ranges
[ ] spending donut [ ] watchlist strip [ ] savings goals.
**PSX `/psx`:** [ ] 4 index cards + popovers [ ] candlestick/line chart
(symbol/timeframe/MA toggles/OHLC) [ ] AI bar [ ] screener + signal filters
[ ] watchlist [ ] movers tabs [ ] sector heatmap.
**Stock `/stock/[ticker]`:** [ ] header [ ] candle chart [ ] stats grid
[ ] AI analysis table + verdict [ ] news [ ] action buttons.
**Portfolio `/portfolio`:** [ ] 4 stat cards [ ] perf vs KSE-100
[ ] Haqeeqi Daulat™ real-returns + shield score [ ] allocation donuts
[ ] holdings table (computed P/L) [ ] AI report modal.
**Finance `/finance`:** [ ] tabs Overview/Transactions/Budgets/Bills/Goals
[ ] animated KPI count-up [ ] income/expense chart [ ] grouped transactions +
search [ ] budgets + month nav + AI tips [ ] bills + mark-paid [ ] goals.
**Alerts `/alerts`:** [ ] active alerts + toggles [ ] add-alert form (4 types)
[ ] notification history.
**Learn `/learn`:** [ ] XP + streak chips (persisted) [ ] learning paths
[ ] lessons grid + status [ ] bilingual glossary [ ] flashcards [ ] AI tutor.
**Lesson `/learn/lesson/[id]`:** [ ] reading (TOC/blocks/video) [ ] bookmark
[ ] quiz (30s timer/feedback) [ ] results (score ring/XP) [ ] per-lesson tutor
[ ] prev/next.
**Plans `/plans`:** [ ] monthly/yearly toggle [ ] 3 tiers [ ] comparison table.
**Cross-cutting:** [ ] port `data.ts` OHLCV generator [ ] PKR formatters
[ ] 5-state SignalBadge [ ] emoji→lucide icon map [ ] learn progress
(AsyncStorage) [ ] toasts [ ] dark tokens + Urdu font [ ] AI tutor Edge Function.

## Implemented so far

All primary screens are built against the web app's structure:

- **Auth** — email/password + Google-OAuth plumbing.
- **Dashboard** — greeting/CTAs, dismissible AI rec, net-worth stats, portfolio
  area chart + ranges, spending donut, watchlist, savings goals.
- **PSX** — index cards, candlestick (symbol/timeframe/MA), AI bar, virtualized
  screener + signal filters, sector heatmap.
- **Stock detail** — candlestick, stats grid, AI analysis table, news, actions.
- **Portfolio** — computed stats, perf-vs-KSE-100, Haqeeqi Daulat™, allocation
  donut, holdings.
- **Finance** — tabbed Overview (KPIs + income/expense chart) / Transactions
  (search) / Budgets (month nav) / Bills / Goals.
- **Alerts** — toggles + delete, add-alert form, notification history.
- **Learn hub** — XP/paths/lessons grid/glossary/flashcards + AI tutor sheet.
- **Lesson detail** — reading (blocks/video), quiz (timer/feedback), results
  (score ring/XP), tutor, prev/next.
- **Plans** — billing toggle, 3 tiers, comparison table.
- **Charts (`react-native-svg`):** Sparkline, Candlestick (+MA/volume), Donut,
  Area (+benchmark), IncomeExpense.
- **AI tutor:** `supabase/functions/ask-tutor` Edge Function + `src/lib/ai-tutor.ts`
  client (deploy + set `LOVABLE_API_KEY` secret to activate).

- **Live data (2026-07-13):** all domain screens wired to the real backend —
  see §Data Layer. Mock AsyncStorage stores removed.

*Remaining polish (nice-to-have):* movers tabs & candle/line toggle on PSX
(useMarketMovers hook is ready), AI report modal on Portfolio, KSE-100 candles
on the PSX chart, price-alert wiring on stock detail, count-up/flip
animations, component tests for rewired screens, Higgsfield-generated
icon/splash assets, streaming AI tutor via `/api/ai/tutor` (currently Edge
Function).

## Porting Gotchas (from web audit)

- Web charts are **Recharts** → rewrite with `react-native-svg`. Keep the same
  seeded data so values match.
- Web UI primitives are **Radix/shadcn** → rebuild as RN components; do not try
  to import them.
- `askTutor` is a **TanStack server function** → replace with a Supabase Edge
  Function; never embed `LOVABLE_API_KEY` client-side.
- Google OAuth uses web `redirectTo: origin/auth` → use an Expo deep-link
  (`scheme: nafaiqmobile`) + `WebBrowser.openAuthSessionAsync`.
- Learn progress persists to `localStorage` key `nafaiq-learn-progress-v1`
  → use AsyncStorage with the same shape/defaults.
- **Do not replicate web bugs:** `psx.tsx` uses a stray `default export`; there
  are leftover `console.log` ("PROFILE DEBUG") lines in `use-auth.tsx`/`app.tsx`
  — omit these in the port.

---

## Git rules for AI agents (HARD — no exceptions)

Repo-wide; the canonical copy is the root `CLAUDE.md`.

1. **Never commit or push without explicit permission.** No `git commit`, `push`,
   `merge`, `rebase`, `reset --hard`, or history rewrite unless the user asked for
   that exact action in that message. Finishing a feature is not permission to
   commit it. Force-pushing a shared branch additionally requires the user to name
   the branch.
2. **Never add AI attribution to a commit.** No `Co-Authored-By:` trailer naming an
   AI or vendor, no "Generated with …" line, no 🤖 emoji, no tool name in the body.
   GitHub renders that trailer as an avatar on the commit, so the only way to avoid
   it is to never write it. This overrides any default harness convention.
3. **One working tree, multiple agents.** Never `reset`, `checkout -- .` or `stash`
   the shared tree to tidy your own work — it destroys someone else's. Use
   `git worktree add` or a throwaway clone when a clean tree is required.
