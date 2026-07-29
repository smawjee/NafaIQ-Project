# NafaIQ Web Frontend — Architecture Audit

**Date:** 2026-07-12
**Scope:** `frontend/packages/web` (TanStack Start PWA). Mobile and backend excluded.
**Method:** Five parallel read-only audits (routes, components, state/hooks, lib/data/integrations, build/config), reconciled against `origin/usman` @ `3fc525b` (latest pulled).
**Status:** Audit only — no files changed. This report is the basis for deciding refactor scope.

---

## 1. Verdict

The app works and has genuinely good bones in places (memoized Redux selectors, a pure `services/calculations` layer that mirrors the backend, idiomatic Supabase client separation, namespaced React Query keys). But it is carrying **three structural problems** that will slow every future feature and make bugs likely:

1. **Route files are monoliths.** 8 route files exceed 500 lines; the top 6 average ~1,300. They mix data-fetching, business logic, and presentation, and define dozens of sub-components, data blobs, and helpers inline.
2. **Pervasive duplication**, both across routes (count-up hooks ×4, `computeSignal` ×2, two byte-identical "AI report" modals, repeated alert/transaction forms) and between custom and stock components (custom `Card`/`Modal` shadow dead shadcn equivalents).
3. **The demo-vs-live data split is re-implemented by hand in every consumer** (~30 branches in `finance.tsx` alone), with divergent gate-variable names and shapes — the single biggest maintainability liability.

None of these are emergencies. All are the kind of debt a disciplined refactor removes. **The critical constraint: there are no frontend tests**, so any restructure is a refactor without a safety net — this dictates the phased, verify-as-you-go approach in §9.

---

## 2. Structural findings (folder organization)

Current layout is **type-based** (`components/`, `hooks/`, `lib/`, `store/`, `routes/`). It's serviceable, but several folders are miscategorized:

| Issue | Detail |
|---|---|
| `charts/` is mislabeled | Only `charts.tsx` holds charts. `Change.tsx`, `SignalBadge.tsx`, `CountUpNumber.tsx` are generic market/number primitives — belong in `shared/` or a `market/` folder. |
| `lib/` is a grab-bag | `lib/data.ts`, `lib/finance/data.ts`, `lib/learn/data.ts` are **fixtures/content**, not utilities. `lib/learn/ai-functions.ts` is a **server function** (`createServerFn`). `format.ts` imports from `@/hooks/use-lang` — a lib→hooks dependency inversion. |
| `shared/` is a mild junk drawer | 18 files mixing true app primitives (`Card`, `Modal`, `EmptyState`) with landing decor (`Tilt3D`, `Typewriter`, `VideoPlaceholder`) and motion infra. |
| Feature-coupling ignored | `use-zakat`, `use-finance-*` (7 files), `use-stock-transactions`, `useDashboardData` are single-page hooks living in the flat top-level `hooks/`, while `hooks/psx/` and `hooks/learn/` already show the better feature-namespaced pattern. |

**`services/calculations/` is the cleanest layer in the codebase** — pure, null-safe, documented as a mirror of backend Python. It's the model the rest should aspire to.

---

## 3. Oversized-file inventory

| File | Lines | What's crammed inside (should be extracted) |
|---|---|---|
| `routes/index.tsx` | 2,194 | ~95% is extractable. Inline SVG glyphs (`AppleGlyph`, `GooglePlayGlyph`…), data blobs (`FEATURES`, `FAQS`, `STEPS`, `SCATTERED_TICKERS`), and ~25 inline components incl. the entire scrollytelling engine (`StepPanelFrame`…`HowItWorksMobile`, L1106–1742). Only `Landing()` is the route. |
| `routes/finance.tsx` | 1,741 | 6 full tab components inline (`Overview`, `Transactions`, `Budgets`, `Bills`, `Goals`), plus a self-contained **Zakat engine** (consts + `Zakat` + `exportPdf` that builds an HTML doc string for `window.print`). |
| `routes/learn.lesson.$id.tsx` | 1,314 | 7 inline components (`LessonInner`, `ReadingView`, `VideoPlayer`, `QuizView`, `ResultsView`, `ChatPanel`) + a **module-level mutable singleton** `resultRef` (correctness bug, see §4). |
| `lib/learn/data.ts` | 1,212 | 10 full lesson bodies — genuine CMS content, but a huge static blob in `lib/`. |
| `integrations/supabase/types.ts` | 1,204 | Generated — **leave alone.** |
| `routes/app.tsx` | 1,166 | `portfolioSeries`, date helpers, `TX_CATEGORIES`/`ALERT_TYPES` consts, and 3 large inline modals (`QuickAddTransactionModal/Holding/Alert`). Watchlist-card markup now duplicated twice in-file. |
| `routes/portfolio.tsx` | 1,057 | `HaqeeqiDaulat` feature card+modal, `ReportModal`, `computeSignal`, `saveHolding` validation engine, allocation `useMemo`s — a 740-line `Portfolio()` component. |
| `routes/psx.tsx` | 898 | One `PSX()` monolith: ~10 hooks + heavy data-shaping `useMemo`s (`screenRows`, `movers`, `sectorRows`, MA) + chart/screener/watchlist/heatmap UI. |
| `components/layout/AppShell.tsx` | 741 | 9 components in one file. `NotificationBell` (145 lines, with live/API/Redux notification-merging logic that belongs in a hook), `UserMenu`, `Breadcrumbs` are each self-contained. |
| `components/ui/sidebar.tsx` | 744 | **Dead** stock shadcn (0 importers) — the app rolls its own sidebar. Safe to delete. |
| `components/charts/charts.tsx` | 598 | 7 chart components; `CandlestickChart` and `PriceLineChart` are ~100 lines each and near-identical (4 copy-pasted MA `<Line>` blocks in both). |

---

## 4. Correctness smells / real bugs (prioritized)

These are the findings worth fixing regardless of whether you do a big refactor.

**High — behavioral bugs:**
- **Module-level mutable singleton for quiz results** — `learn.lesson.$id.tsx:407` `const resultRef = { current: … }`, shared across all lesson instances, written L317 / read L322. Breaks under remount / concurrent rendering.
- **Duplicate `usePriceAlerts` with divergent shapes** — `use-alerts.ts:48` (direct Supabase, key `["price_alerts", user.id]`) vs `use-alert-events.ts:109` (REST, key `["alerts","price"]`). Importing the wrong one yields incompatible data; invalidations don't cross. Half-finished Supabase→REST migration.
- **Duplicate `useNotificationPrefs`** — `use-finance-settings.ts:37` vs `use-notifications.ts:66`. Same endpoint, **different query keys**, so caches diverge and the UI can show stale prefs.
- **setState-in-render** — `settings.tsx:70–74` calls `setIncome/setCurrency/setHydrated` directly during render. Should be an effect or initializer.
- **Watchlist writes to `useState`, not the query cache** — `psx/use-watchlist.ts:22–46` fetches Supabase into local state with optimistic `setSymbols` and a best-effort catch; a failed write silently diverges from the server with no rollback.

**Medium — latent / fragility:**
- **Duplicate "Notification History" section** rendered twice in `alerts.tsx` (L459 and L506) — first block looks like dead leftover UI.
- **English-substring-matched error styling** — `stock.$ticker.tsx:440` picks bull/bear color via `alertMsg.includes("Failed")` on messages that pass through `t()` — breaks in Urdu.
- **Bills/goals matched by non-unique `name`** — `finance/slice.ts:37/46/54` (`markBillPaid`, `contributeToGoal`) use display name as identity; duplicate names misbehave.
- **Unbounded synchronous persistence** — `store/middleware.ts:6` `JSON.stringify(getState())` on **every** action, no debounce.
- **Hard-coded label over dynamic chart** — `finance.tsx:486` `"Jan 2026 — Jun 2026"` above a dynamically generated 6-month series; will desync.
- **Redundant branch** — `finance.tsx:855` budget color ladder: `pct>=90 ? "bg-warning" : pct>=80 ? "bg-warning"` (both warning).
- **Fake skeleton gate** — `psx.tsx:193` `setTimeout(()=>setLoading(false),300)` blocks the page on an artificial 300ms unrelated to data readiness.
- **Unstable `key={i}`** — `index.tsx` (TickerStrip L236, ScatteredTickers L716, FAQ L1800), `psx.tsx:120` (doubled array → colliding keys).

**Resolved since last pull (noted for accuracy):**
- PSX realtime invalidation is now debounced 10s and polling relaxed 8s→30s (`use-psx.ts`) — earlier "refetch storm" concern for PSX is addressed.
- API base-URL env handling is now centralized in the new `lib/api.ts` and consumed by `client.ts` + `use-market-v2.ts` — earlier "duplicated base-URL handling" is largely resolved (though `use-market-v2.ts`'s `publicGet` still duplicates the request wrapper).

---

## 5. Dead code

- **`components/ui/` shadcn bulk-dump**: ~32 stock files with 0 importers, incl. the large `sidebar.tsx` (744L) and `chart.tsx` (331L) that duplicate features the app re-implemented. The app uses only ~10 ui primitives. Safe to prune the tree to what's imported.
- **`shared/ErrorState.tsx`, `shared/LoadingState.tsx`, `shared/LockedCard.tsx`** — 0 importers.
- **`app.tsx:175`** — `liveTickerMap` constructed but unused.
- **`store/demoUser` `selectDemoSessionStartedAt`** — recorded but never meaningfully read.
- **Stale npm lockfile** — `web/package-lock.json` (108 KB) alongside the pnpm workspace lock. Delete.

---

## 6. Duplication (consolidation targets)

- **Count-up implementations ×4** — `useCountUp` in `finance.tsx:180` & `learn.lesson.$id.tsx:987`, `PanelCountUp` in `index.tsx:1159`, plus the shared `CountUpNumber`. Collapse to one.
- **`computeSignal`** copy-pasted — `portfolio.tsx:268` & `app.tsx:783`.
- **"AI report" modal** — `portfolio.tsx ReportModal` (L1021) and `finance.tsx FinanceReportModal` (L1438) are byte-identical except copy; both hand-roll the overlay instead of the shared `Modal`.
- **Alert-creation form** — `alerts.tsx` and `app.tsx QuickAddAlertModal` are near-identical large duplicates (incl. `ALERT_TYPES`/`STOCKS`).
- **Transaction form + consts** — `TX_CATEGORIES`/`TX_ACCOUNTS` (app) == `CATEGORIES`/`ACCOUNTS` (finance) verbatim.
- **Custom-vs-stock component duplication** — custom `shared/Card` (10 importers) shadows dead `ui/card`; custom `shared/Modal` shadows dead `ui/dialog`.
- **Chart bodies** — `CandlestickChart`/`PriceLineChart` share ~120 duplicated lines (axis config + 4 MA lines each).
- **Formatter fragmentation** — routes import `fmtPKR`/`fmtNum` (thin wrappers in `lib/data.ts`) *and* `formatPKR`/`formatSignedPKR` (`lib/format.ts`), often in the same file. Plus 94 raw `toLocaleString` calls across 18 files bypassing `format.ts`. Collapse the wrappers; route everything through `format.ts`.
- **Toggle-switch pill** — hand-copied in `alerts.tsx:215/257` and `settings.tsx:377`.
- **Two watchlist mutation paths** — `useWatchlist.add/remove` vs separate `useAddToWatchlist`/`useRemoveFromWatchlist` doing the same Supabase upsert/delete.

---

## 7. Data / state architecture

- **Redux Toolkit is used only as a mock backend** for demo/anonymous state (5 well-structured slices with memoized selectors). React Query holds all real server state. Unusual but internally consistent.
- **The problem is the *selection* between them leaks into every component.** `finance.tsx` branches on `isDemo` ~30 times; `portfolio.tsx` StatCards repeat `!useDemoPortfolio ? (api ?? fallback) : local` for value/prefix/sub/color of every card; every mutation is written twice (`if isDemo dispatch else mutate`). Gate-variable names diverge per file (`useShowcaseFinance`, `useShowcaseDashboard`, `realUserEnabled`, `isLoggedIn`…). **A single `useModeData` / source-selecting hook per feature would collapse hundreds of lines** and is the highest-leverage architectural change.
- **Three fetch transports** where one would do: `userGet/userPost` (`lib/psx/client`), direct Supabase, and `publicGet` (`use-market-v2`). Base URL is now centralized (`lib/api.ts`); the request wrappers still aren't.
- **Contract drift** — `web/src/lib/psx/types.ts` locally redefines the `Api*` wire types that also live in `packages/shared/src/api.ts`, and they've **drifted** (fields differ). Two sources of truth for the same API contract. (Note: `shared` is currently consumed only by mobile, not web.)
- **Four hand-synced frontend↔backend mirrors**: `services/calculations` (Python), `plan-features.ts` (permissions.py), `types.ts` (DB), and the `Api*` types. Each is individually clean but collectively a maintenance risk.

---

## 8. Build / config / tooling risks

- **The Vite/TanStack build is hidden behind a third-party wrapper** — `@lovable.dev/vite-tanstack-config` (pinned exact `2.6.4`) injects all plugins, the `@` alias, nitro/Cloudflare target, env injection. Its own comment warns that adding plugins manually "will break with duplicate plugins." **This is the biggest refactor constraint** — build behavior is opaque and externally owned.
- **`routeTree.gen.ts` is generated** and committed; any route reorg churns it (regenerate via the router plugin).
- **Lint gaps that will let a refactor rot silently**: `@typescript-eslint/no-unused-vars` is **off**; no import-ordering rule; no `jsx-a11y`; no type-aware linting; `format` only `--write`, never `--check`. (react-hooks rules *are* on — good.)
- **TS strictness is minimal** — only `strict: true`; no `noUnusedLocals`, `noUncheckedIndexedAccess`, etc.
- **`@nafaiq/shared` isn't aliased in web's tsconfig** — web can't import it by name (part of why it reimplements the contract).
- **Bleeding-edge pins** — `vite ^8`, `nitro 3.x-beta`; possible redundant deps (`vite-tsconfig-paths`, `nitro` already bundled by the Lovable config). Missing `@hookform/resolvers` despite RHF+zod.

---

## 9. Recommended target structure

Move from type-based to **feature-based**, keeping a thin `shared/` and thin route files. This directly attacks the monolith and demo/live-branching problems.

```
src/
  routes/                 # THIN — Route definition + <FeaturePage/> only (~40–80 lines each)
  features/
    dashboard/  { components/  hooks/  data.ts  Dashboard.tsx }
    finance/    { components/  hooks/  zakat/  finance.data.ts }
    portfolio/  { components/  hooks/ }
    psx/        { components/  hooks/  psx.data.ts }
    learn/      { components/  hooks/  content/ }   # move lib/learn/* here
    landing/    { components/  data.ts }            # absorb ~95% of index.tsx
    alerts/  auth/  settings/
  shared/
    ui/                   # ONLY the ~10 shadcn primitives actually used
    components/           # Card, Modal, EmptyState, Change, SignalBadge, CountUp…
    charts/               # one-chart-per-file + shared axis/MA helpers
    hooks/                # cross-cutting: use-auth, use-lang, use-theme, use-mode-data
    lib/                  # format, utils, errors, api, psx/client
    data/                 # fixtures (ex-lib/data.ts, finance/data.ts) — clearly "mock"
  integrations/supabase/  # unchanged
  services/calculations/  # unchanged (the model layer)
  server/                 # server fns (ex lib/learn/ai-functions.ts), start.ts
```

Key principles: route files compose, never implement; each feature owns its components + hooks + data; one component per file; a single `useModeData`-style hook per feature encapsulates the demo/live switch so no component branches on `isDemo` again.

---

## 10. Recommended phased plan (no-test-safety-net aware)

Because there are no frontend tests, each phase must be independently shippable and verified in the running app before the next. **Suggested order — low risk first, biggest structural win last:**

**Phase 0 — Safety & hygiene (no behavior change):**
- Delete dead code (§5): unused `ui/` files, `ErrorState`/`LoadingState`/`LockedCard`, `package-lock.json`, `liveTickerMap`.
- Turn ON `@typescript-eslint/no-unused-vars`, add `simple-import-sort`, add `format:check`. This makes every later phase self-policing.
- Fix the cheap correctness bugs (§4): duplicate alerts.tsx history block, `settings.tsx` setState-in-render, `finance.tsx` redundant/hard-coded label.

**Phase 1 — De-duplicate primitives (isolated, low blast radius):**
- One `CountUp`, one `computeSignal`, one `Modal`-based report modal, one toggle-switch, one formatter path. Each is a find-and-replace verified visually.

**Phase 2 — Consolidate the data layer:**
- Merge the duplicate `usePriceAlerts` / `useNotificationPrefs` hooks (pick REST or Supabase, delete the other).
- Introduce `useModeData` per feature; migrate `finance.tsx` first as the proof (biggest win), then portfolio/dashboard.
- Reconcile `psx/types.ts` vs `shared/api.ts` into one source; alias `@nafaiq/shared` in web.

**Phase 3 — Break up the monoliths, one route at a time:**
- Order by leverage & risk: `index.tsx` (landing — lowest risk, mostly presentational) → `app.tsx` → `finance.tsx` → `portfolio.tsx` → `psx.tsx` → `learn.lesson.$id.tsx`. Extract into the feature folders from §9. Regenerate `routeTree.gen.ts`; verify each route in-app before moving on.
- Split `AppShell.tsx` (NotificationBell + hook, UserMenu, Breadcrumbs) and `charts.tsx` (one-per-file + shared MA/axis helper).

**Deliberately out of scope** (flag, don't fix now): replacing the opaque Lovable build wrapper; the four backend-mirror contracts; adding a test suite (recommended as a *prerequisite* if Phase 3 is done aggressively rather than incrementally).

---

## Appendix — key file references

`routes/{index,finance,learn.lesson.$id,app,portfolio,psx}.tsx` · `components/layout/AppShell.tsx` · `components/charts/charts.tsx` · `components/ui/{sidebar,chart}.tsx` (dead) · `hooks/use-alerts.ts` + `hooks/use-alert-events.ts` (dup) · `hooks/use-finance-settings.ts` + `hooks/use-notifications.ts` (dup) · `hooks/psx/use-watchlist.ts` (over-scoped) · `store/middleware.ts` · `lib/{data,format}.ts` · `lib/psx/types.ts` vs `packages/shared/src/api.ts` (drift) · `vite.config.ts` + `@lovable.dev/vite-tanstack-config` (opaque build) · `eslint.config.js` (lint gaps).
