# NafaIQ — Presentation Preparation Guide

> **Live:** https://nafaiq.vercel.app  
> **Tagline:** *PSX. Finance. AI. One Terminal.*

---

## Table of Contents

1. [What is NafaIQ?](#1-what-is-nafaiq)
2. [Tech Stack & Why](#2-tech-stack--why)
3. [Architecture Overview](#3-architecture-overview)
4. [Project Structure](#4-project-structure)
5. [File-by-File Breakdown](#5-file-by-file-breakdown)
   - [5.1 Routes (Pages)](#51-routes-pages)
   - [5.2 Components](#52-components)
   - [5.3 Hooks (State Management)](#53-hooks-state-management)
   - [5.4 Lib (Data & Utilities)](#54-lib-data--utilities)
   - [5.5 Integrations](#55-integrations)
   - [5.6 Config Files](#56-config-files)
6. [Key Features Explained](#6-key-features-explained)
7. [Data Flow](#7-data-flow)
8. [Common Interview Q&A](#8-common-interview-qa)
9. [Talking Points for Each Role](#9-talking-points-for-each-role)

---

## 1. What is NafaIQ?

NafaIQ is a **Progressive Web App (PWA)** that serves as a premium financial terminal for the Pakistan Stock Exchange (PSX), combined with a personal finance manager and AI-powered financial education platform. It's built specifically for **Pakistani investors** who face unique challenges like PKR devaluation, halal investing requirements, and limited access to Bloomberg-grade tools.

### Core Value Propositions

| Feature | Description |
|---------|-------------|
| **PSX Terminal** | Live candlestick charts, watchlists, heatmaps, AI-driven trading signals |
| **Haqeeqi Daulat™** | World-first feature showing devaluation-adjusted real wealth (not just nominal PKR gains) |
| **AI Financial Tutor** | 24/7 AI tutor powered by Google Gemini for financial education |
| **Personal Finance** | Expense tracking, budgets, goals, bills — all in PKR |
| **Islamic Finance** | Halal stock screening, Zakat calculator, Islamic savings goals |
| **Learn Hub** | Structured financial courses in English & Urdu with quizzes, XP, and progress tracking |
| **Bilingual** | Full Urdu (right-to-left) interface alongside English |

---

## 2. Tech Stack & Why

### Frontend / Rendering

| Technology | Why We Chose It |
|------------|----------------|
| **React 19** | Latest React with concurrent features, improved SSR streaming, and enhanced hooks. Industry standard with massive ecosystem |
| **TypeScript 5.8** | Type safety across the entire codebase — catches bugs at compile time, provides excellent IDE autocomplete, and makes refactoring safe |
| **TanStack Router v1** | File-based routing (like Next.js pages), type-safe routes, built-in SSR/SSG support, scroll restoration, and deep integration with TanStack Query. Unlike Next.js, it's framework-agnostic and works with any Vite setup |
| **TanStack React Query v5** | Server state management — caching, deduplication, background refetching. Eliminates boilerplate for API calls and keeps UI in sync with server state |
| **TanStack React Start** | Meta-framework on top of TanStack Router that adds SSR, server functions, middleware, and Nitro deployment. Think of it as "Next.js but built on TanStack" |
| **Vite 8** | Blazing-fast dev server with HMR, optimized production builds, and first-class support for modern JS/TS |

### Styling

| Technology | Why We Chose It |
|------------|----------------|
| **Tailwind CSS v4** | Utility-first CSS — no context-switching between HTML and CSS files, consistent design tokens via `@theme`, tiny production bundles via purging |
| **tw-animate-css** | Tailwind-compatible animation utilities for micro-interactions |
| **shadcn/ui** (46 components) | Copy-paste component library built on Radix UI primitives — full control over the source code (no black-box dependency), accessible by default, and styled with Tailwind |
| **Radix UI** (20+ primitives) | Headless, accessible React primitives — handles ARIA, keyboard navigation, focus management so we don't have to |
| **framer-motion** | Declarative animations — page transitions, scroll-triggered reveals, spring physics, and the `AnimatePresence` pattern for enter/exit animations |
| **recharts** | Composable chart library built on D3 — responsive containers, theme-aware tooltips, and support for area/line/bar/composed/pie charts |

### Backend / Infrastructure

| Technology | Why We Chose It |
|------------|----------------|
| **Supabase** | Open-source Firebase alternative — provides auth (email/password + Google OAuth), PostgreSQL database, and real-time subscriptions. Self-hostable, no vendor lock-in |
| **Nitro** (via React Start) | Universal server engine — deploys to Node.js, Vercel Edge, Cloudflare Workers, or Deno with zero config changes |
| **Lovable Gateway** | AI gateway that proxies requests to Gemini (and other models) — handles rate limiting, key management, and model routing |

### AI / Data

| Technology | Why We Chose It |
|------------|----------------|
| **Google Gemini 3 Flash** (via Lovable Gateway) | Powering the AI tutor — fast, cost-effective, and handles both English and Urdu fluently |
| **Zod** | Runtime schema validation for server function inputs — ensures type safety across the client-server boundary |
| **date-fns** | Lightweight date utilities — tree-shakeable, immutable, functional |

### Developer Experience

| Technology | Why We Chose It |
|------------|----------------|
| **ESLint 9** (flat config) | Static analysis — catches unused variables, missing dependencies, and anti-patterns |
| **Prettier** | Consistent code formatting across the team — no more style debates |
| **class-variance-authority** + **tailwind-merge** + **clsx** | The `cn()` utility combines and deduplicates Tailwind classes with proper precedence |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                   Browser (PWA)                  │
│  ┌───────────────────────────────────────────┐  │
│  │         TanStack React Start              │  │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │  │
│  │  │  React   │ │ TanStack │ │ TanStack  │  │  │
│  │  │   19     │ │  Router  │ │   Query   │  │  │
│  │  └─────────┘ └──────────┘ └───────────┘  │  │
│  │  ┌───────────────────────────────────┐   │  │
│  │  │       Radix UI + shadcn/ui        │   │  │
│  │  └───────────────────────────────────┘   │  │
│  │  ┌───────────────────────────────────┐   │  │
│  │  │    Tailwind CSS v4 + framer-motion│   │  │
│  │  └───────────────────────────────────┘   │  │
│  └───────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────┘
                  │ SSR / Server Functions
┌─────────────────▼───────────────────────────────┐
│              Nitro Server (SSR)                  │
│  ┌──────────┐ ┌────────────┐ ┌──────────────┐  │
│  │Supabase  │ │ Lovable    │ │ Server Fns   │  │
│  │ Auth API │ │ AI Gateway │ │ (Zod-valid)  │  │
│  └──────────┘ └────────────┘ └──────────────┘  │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│           Supabase (Backend-as-a-Service)        │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Auth    │ │PostgreSQL│ │  Storage       │  │
│  │(Google+  │ │(profiles,│ │  (avatars, etc)│  │
│  │ EmailPW) │ │ data)    │ │                │  │
│  └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Rendering Strategy

- **Landing page (`/`)**: Static HTML with client-side hydration (fast first paint)
- **Auth page (`/auth`)**: Client-side rendered (no SSR needed)
- **App pages (`/app`, `/psx`, etc.)**: SSR with client-side hydration. The server renders the initial HTML, then React takes over for SPA-like navigation
- **Server Functions**: `createServerFn` creates RPC-style endpoints that run on the server — used for the AI tutor chat

---

## 4. Project Structure

```
nafa-iq-zenith-1/
├── public/                    # Static assets (served as-is)
│   ├── icons/                 # PWA icons (192x, 512x, maskable, apple-touch)
│   ├── hero-bg.webp           # Landing page background
│   ├── manifest.webmanifest   # PWA manifest
│   └── robots.txt
├── src/
│   ├── assets/                # Build-processed assets
│   │   ├── logo.png           # App logo (imported in components)
│   │   └── auth-bg.png.asset.json
│   ├── components/            # Reusable UI components
│   │   ├── ui/                # 68 shadcn/ui components (Radix + Tailwind)
│   │   ├── shared/AppShell.tsx   # Authenticated app layout (sidebar + topbar)
│   │   ├── shared/Card.tsx       # Glass-card with framer-motion hover
│   │   ├── charts/charts.tsx     # recharts wrappers (theme-aware)
│   │   ├── shared/ThemeToggle.tsx # Sun/Moon toggle button
│   │   ├── shared/AiGlyph.tsx    # Gemini-style spark SVG icon
│   │   ├── shared/animations.tsx # framer-motion presets + CountUp
│   │   └── ... (15 more)
│   ├── hooks/                 # React hooks + context providers
│   │   ├── use-auth.tsx       # Supabase Auth context
│   │   ├── use-landing-theme.tsx # Dark/light theme context
│   │   ├── use-theme.ts       # Re-exports useLandingTheme as useTheme
│   │   ├── use-lang.ts        # English/Urdu language switcher
│   │   ├── use-learn.tsx      # Learn Hub progress + XP state
│   │   ├── use-finance-store.ts # Finance app local state
│   │   └── use-mobile.tsx     # Mobile detection hook
│   ├── integrations/          # Third-party service adapters
│   │   ├── supabase/          # Supabase client + auth middleware
│   │   └── nafaiq/            # NafaIQ internal API client
│   ├── lib/                   # Pure functions, data, utilities
│   │   ├── data.ts            # OHLCV generator + stock market data
│   │   ├── finance/data.ts    # Finance mock data (goals, txns, budgets)
│   │   ├── learn/data.ts      # Lesson content + quizzes (1212 lines)
│   │   ├── learn/ur.ts        # Urdu translations for learn content
│   │   ├── lang-ur.ts         # UI Urdu dictionary (606 keys)
│   │   ├── format.ts          # PKR/number/percent formatting
│   │   ├── utils.ts           # cn() utility (clsx + tailwind-merge)
│   │   ├── learn/ai-functions.ts # AI tutor server function
│   │   ├── errors/capture.ts  # SSR error capture utility
│   │   ├── errors/page.ts     # 500 error page renderer
│   │   └── errors/reporting.ts # Lovable error reporting
│   ├── routes/                # TanStack Router file-based routes
│   │   ├── __root.tsx         # Root layout (providers + auth gate)
│   │   ├── index.tsx          # Landing page (2168 lines)
│   │   ├── auth.tsx           # Login/signup page
│   │   ├── app.tsx            # Dashboard (net worth, portfolio, spending)
│   │   ├── psx.tsx            # PSX Market page
│   │   ├── portfolio.tsx      # Portfolio page
│   │   ├── finance.tsx        # Personal finance page
│   │   ├── learn.tsx          # Learn Hub layout (sidebar)
│   │   ├── learn.index.tsx    # Learn Hub home + AI chat
│   │   ├── learn.lesson.$id.tsx # Individual lesson page + AI chat
│   │   ├── plans.tsx          # Pricing/upgrade page
│   │   ├── settings.tsx       # Settings (theme, language, account)
│   │   ├── alerts.tsx         # Notifications/alerts
│   │   ├── team.tsx           # About the team
│   │   ├── urdu-qa.tsx        # Urdu Q&A landing page
│   │   ├── stock.$ticker.tsx  # Individual stock detail
│   │   └── sitemap[.]xml.ts   # Dynamic sitemap for SEO
│   ├── routeTree.gen.ts       # Auto-generated route tree
│   ├── server.ts              # SSR entry point (error wrapper)
│   ├── start.ts               # TanStack Start instance config
│   ├── router.tsx             # Router factory with QueryClient
│   └── styles.css             # Global styles + Tailwind theme tokens
├── vite.config.ts             # Vite config (delegates to @lovable.dev config)
├── tsconfig.json              # TypeScript config
├── package.json               # Dependencies + scripts
├── eslint.config.js           # ESLint flat config
└── .prettierrc                # Prettier config
```

---

## 5. File-by-File Breakdown

### 5.1 Routes (Pages)

#### `src/routes/__root.tsx` — Root Layout (251 lines)
- **Purpose**: The shell that wraps every page. Sets up all providers, auth gating, and the HTML document shell
- **Key responsibilities**:
  - `<html>` tag with inline pre-hydration script (reads localStorage for theme, applies `.theme-light`/`.landing-light` classes before React mounts — prevents FOUC)
  - `<AuthGate>` component: redirects unauthenticated users to `/auth` (except for public pages: `/`, `/auth`, `/plans`, `/urdu-qa`, `/team`)
  - `<AppShell>`: Wraps authenticated pages with sidebar + topbar navigation
  - `<PageTransition>`: framer-motion fade transitions between pages
  - Provider hierarchy: `QueryClientProvider` > `AuthProvider` > `LearnProvider` > `LandingThemeProvider`
  - Error boundary + 404 component
  - SEO meta tags, font preconnects, PWA manifest link, OG images

#### `src/routes/index.tsx` — Landing Page (2168 lines)
- **Purpose**: Public-facing marketing site. No auth required
- **Key sections**:
  - Hero with animated ticker tape (PSX stock prices scrolling horizontally)
  - Phone mockup showing the app UI
  - "How it Works" 3-step explanation
  - Haqeeqi Daulat™ interactive demo (flip card showing nominal vs real returns)
  - Testimonials carousel
  - FAQ accordion
  - Footer with contact info
- **Key components used**: `PhoneMockup`, `Tilt3D`, `Particles`, `Typewriter`, `Accordion`, framer-motion scroll animations

#### `src/routes/auth.tsx` — Auth Page (647 lines)
- **Purpose**: Login / signup / email confirmation
- **States**: Tab-based toggle between login and signup. Form fields for email, password, display name. Google OAuth button
- **Validation**: Email format, password strength (min 8 chars, uppercase, number, special char), password confirmation match
- **Edge cases**: Email confirmation required (shows "check your email" screen), redirect back to original page after login

#### `src/routes/app.tsx` — Dashboard (731 lines)
- **Purpose**: Main authenticated dashboard — first thing users see after login
- **Sections**: Portfolio value with area chart, net worth card, spending breakdown donut, watchlist with sparklines, recent transactions, goals progress, budget bars
- **Key data**: Uses mock data from `@/lib/data` and `@/lib/finance-data`
- **AI integration**: Has an AI insights section with natural-language portfolio summaries

#### `src/routes/psx.tsx` — PSX Market Page
- **Purpose**: Full market overview with candlestick charts, market heatmap, top gainers/losers, AI signal badges
- **Key components**: `charts.tsx` (CandlestickChart, Sparkline), `SignalBadge`

#### `src/routes/portfolio.tsx` — Portfolio Page
- **Purpose**: Detailed portfolio breakdown with holdings, P&L, asset allocation

#### `src/routes/finance.tsx` — Finance Page
- **Purpose**: Personal finance management — transactions, budgets, bills, goals

#### `src/routes/learn.tsx` + `learn.index.tsx` + `learn.lesson.$id.tsx` — Learn Hub
- **Purpose**: Financial education platform with structured lessons, quizzes, and AI tutor chat
- **learn.tsx**: Layout with sidebar for learning paths
- **learn.index.tsx**: Course catalog with progress cards, AI tutor chat popup
- **learn.lesson.$id.tsx**: Individual lesson content (sections, quizzes, flashcards), AI tutor chat popup
- **Key feature**: Bilingual content (English/Urdu), lesson progress persisted to localStorage, XP system

#### `src/routes/settings.tsx` — Settings Page
- **Purpose**: Theme toggle (dark/light), language toggle (English/Urdu), profile info, plan info
- **Uses**: `useLandingTheme` for theme, `useLang` for language, `useAuth` for profile

#### Other Routes
- **`plans.tsx`**: Pricing page with Free/Pro/Business tiers
- **`alerts.tsx`**: Notification center
- **`team.tsx`**: About the team
- **`urdu-qa.tsx`**: Urdu-language landing page
- **`stock.$ticker.tsx`**: Individual stock detail page (e.g., `/stock/HBL`)
- **`sitemap[.]xml.ts`**: Auto-generated XML sitemap for SEO

### 5.2 Components

#### `src/components/shared/AppShell.tsx` — App Layout (648 lines)
- **Purpose**: The authenticated app's chrome — sidebar navigation, top bar, bottom mobile nav, notification panel, AI chat button
- **Key features**:
  - Collapsible sidebar (desktop) + bottom tab bar (mobile)
  - Active route highlighted in sidebar
  - Notification panel with slide-out drawer
  - AI chat button (opens AI tutor popup)
  - Theme-aware: applies `theme-light landing-light` classes when light mode is active
  - Logo, user avatar dropdown, search button

#### `src/components/shared/Card.tsx` — Glass Card (57 lines)
- **Purpose**: Reusable glassmorphism card with hover animation
- **Also exports**: `StatCard` — value+label card with scroll-triggered entrance animation
- **Uses**: `motion` from framer-motion, respects `prefers-reduced-motion`

#### `src/components/charts/charts.tsx` — Chart Components (573 lines)
- **Purpose**: Reusable, theme-aware chart components wrapping recharts
- **Exports**: `Sparkline`, `CandlestickChart`, `DonutChart`, `PortfolioAreaChart`, `MiniChart`
- **Key feature**: `useChartTheme()` hook returns theme-appropriate colors (grid, tooltip, teal, expense) — switches automatically when theme changes
- **Export**: `DONUT_LIGHT_PALETTE` for white-card-friendly donut colors

#### `src/components/shared/ThemeToggle.tsx` — Theme Button (30 lines)
- **Purpose**: Simple sun/moon icon button. Pure presentational — receives `isDark` and `onToggle` props
- **Used in**: AppShell sidebar, Settings page

#### `src/components/shared/AiGlyph.tsx` — AI Spark Icon (36 lines)
- **Purpose**: Gemini-style 4-point spark SVG icon. Uses `currentColor` so it inherits text color
- **Used in**: AI chat button, AI tutor header

#### `src/components/shared/animations.tsx` — Animation Utilities
- **Purpose**: Centralized animation helpers
- **Exports**: `CountUp` (animated number counter that fires on scroll), `SPRING_UI` spring preset, re-exports from framer-motion for convenience
- **Edge case**: Respects `useReducedMotion` — skips animations for accessibility

#### `src/components/ui/` — shadcn/ui Components (46 files)
- Complete set of accessible UI primitives: button, input, dialog, select, accordion, tabs, dropdown, tooltip, popover, sheet, drawer, command palette, carousel, calendar, form validation, avatar, badge, checkbox, radio group, switch, slider, progress, skeleton, scroll area, resizable panels, table, pagination, breadcrumb, context menu, navigation menu, menubar, alert dialog, hover card, toggle, toggle group, separator, card, aspect ratio, collapsible, input-otp, label, textarea, sheet, sonner (toast), chart, sidebar
- **Installation**: Copy-pasted (per shadcn/ui philosophy), not a dependency — full control to customize

#### Other Components
- **`Modal.tsx`**: Reusable modal dialog with backdrop, transition, and form field classes
- **`PhoneMockup.tsx`**: Animated phone frame for the landing page hero
- **`Particles.tsx`**: Animated particle background for landing page
- **`Tilt3D.tsx`**: 3D tilt-on-hover card effect
- **`Typewriter.tsx`**: Typewriter text animation
- **`SignalBadge.tsx`**: Buy/Hold/Sell badge with colored styling
- **`Change.tsx`**: Green/red percentage change indicator
- **`CountUpNumber.tsx`**: Animated counting numbers + animated bars
- **`PageSkeleton.tsx`**: Loading skeleton screens
- **`ScrollToTop.tsx`**: Scrolls to top on route change
- **`TestimonialsSection.tsx`**: Testimonials carousel for landing page
- **`VideoPlaceholder.tsx`**: Placeholder for video content
- **`CollapsibleColumn.tsx`**: Collapsible UI panel
- **`ConfirmDialog.tsx`**: Confirmation modal
- **`icons.tsx`**: Custom SVG icons (CrescentIcon, PkBadge, EmojiIcon)
- **`Change.tsx`**: Percentage change display component

### 5.3 Hooks (State Management)

#### `src/hooks/use-auth.tsx` — Auth Context (149 lines)
- **Purpose**: Provides authentication state and methods to the entire app
- **State**: `session`, `user`, `profile`, `loading`
- **Methods**: `signInWithPassword`, `signUpWithPassword`, `signInWithGoogle`, `signOut`
- **Integration**: Uses `supabase.auth.onAuthStateChange` listener for real-time session sync
- **Edge cases**:
  - `needsConfirmation` flag for email-required signups
  - Redirect back to original page after login (via `redirect` search param)
  - Loads user profile from `profiles` table after auth
  - Loading state prevents flash of unauthorized content

#### `src/hooks/use-landing-theme.tsx` — Theme Context (72 lines)
- **Purpose**: Dark/light theme state, persisted to localStorage
- **Storage key**: `nafaiq-landing-theme`
- **Classes applied**: `theme-light` and `landing-light` on `<html>` element
- **Methods**: `setTheme`, `toggleTheme`
- **Key detail**: Pre-hydration inline script in `__root.tsx` reads localStorage and applies classes before React hydrates — prevents flash of wrong theme

#### `src/hooks/use-theme.ts` — Theme Re-export (10 lines)
- **Purpose**: Re-exports `useLandingTheme` as `useTheme` so the rest of the app uses a single import
- **Why**: Originally there were two parallel theme systems (one for landing, one for app). This file unifies them under one name

#### `src/hooks/use-lang.ts` — Language Hook (65 lines)
- **Purpose**: English/Urdu language switcher using `useSyncExternalStore` (reads from external `localStorage` without React state lag)
- **Implements**: `useLang()` returns `{ lang, setLang, t, isUrdu }`
- **`t(key)`**: Translates a key using the `UR` dictionary, falls back to `LEARN_UR`, then returns the key itself
- **`localizeDigits()`**: Returns Western digits unchanged (deliberate — numbers stay in Western numerals for readability)
- **Performance**: Uses external store + `useSyncExternalStore` instead of React context to avoid unnecessary re-renders

#### `src/hooks/use-learn.tsx` — Learn Progress Context (114 lines)
- **Purpose**: Manages learning progress (XP, lesson completion, bookmarks)
- **Persistence**: localStorage key `nafaiq-learn-progress-v1`
- **Methods**: `statusOf(id)`, `completeLesson(id, xpGain)`, `toggleBookmark(id)`, `pathProgress(lessonIds)`
- **Edge cases**: Merges stored data with defaults on load (handles partial/corrupt localStorage gracefully)

#### Other Hooks
- **`use-finance-store.ts`**: Local state for finance page (transactions, budgets, goals, bills)
- **`use-mobile.tsx`**: Boolean hook for responsive breakpoint detection

### 5.4 Lib (Data & Utilities)

#### `src/lib/data.ts` — Market Data (362 lines)
- **Purpose**: Central source of stock market mock data + OHLCV chart data generator
- **Exports**: `STOCKS`, `WATCHLIST`, `TICKER_ITEMS`, `generateOHLCV()`, `fmtPKR`, `fmtNum`, `sma()`
- **`generateOHLCV()`**: Seeded PRNG (mulberry32) produces deterministic but realistic candlestick data with trends, corrections, and volatility
- **`sma()`**: Simple Moving Average calculation for chart overlays

#### `src/lib/finance-data.ts` — Finance Mock Data (388 lines)
- **Purpose**: All finance-related mock data
- **Exports**: `GOALS`, `TRANSACTIONS`, `BUDGETS`, `BILLS`, `SPENDING`, `GLOSSARY`
- **Structured for**: Realistic PKR amounts, Pakistani merchant names (K-Electric, Cheezious, Careem, etc.)

#### `src/lib/learn-data.ts` — Lesson Content (1212 lines)
- **Purpose**: All educational content for Learn Hub
- **Exports**: `LESSON_CONTENT` (array of lessons), `LEARNING_PATHS` (structured course paths)
- **Each lesson has**: Sections (with paragraphs, callouts, formulas, tables), quizzes (with explanations), flashcards, duration, level, category
- **Topics**: Candlesticks, RSI, Moving Averages, Stop Loss, Support/Resistance, Volume, MACD, Bollinger Bands, Risk Management

#### `src/lib/format.ts` — Formatting (48 lines)
- **Purpose**: Single source of truth for number/currency/percent formatting
- **Key decisions**: Western 3-digit grouping (not lakh/crore) for consistency across the app. Leading sign always (e.g., `+2.27%`, `-PKR 500`)
- **Exports**: `formatNumber`, `formatPKR`, `formatSigned`, `formatSignedPercent`, `formatSignedPKR`

#### `src/lib/lang-ur.ts` — Urdu Dictionary (606 lines)
- **Purpose**: Key-value translation dictionary for the UI
- **Structure**: English keys, Urdu values — covers nav, settings, common UI text

#### `src/lib/learn/ur.ts` — Learn Urdu Translations (452 lines)
- **Purpose**: Urdu translations specifically for Learn Hub content
- **Note**: Auto-generated (per file header)

#### `src/lib/learn/ai-functions.ts` — AI Tutor Server Function
- **Purpose**: Server function (`askTutor`) that proxies chat requests to Google Gemini via Lovable Gateway
- **Features**:
  - Zod schema validation on input (role, content, lesson context, language)
  - System prompt that contextualizes the tutor as a "friendly PSX finance tutor"
  - Urdu/English response support
  - Graceful fallbacks for: missing API key, rate limit (429), out of credits (402), network errors
  - Model: `google/gemini-3-flash-preview`

#### Error Handling Files
- **`errors/capture.ts`**: Captures uncaught errors/unhandled rejections globally with a TTL cache, so `server.ts` can reference them when Nitro swallows the error
- **`errors/page.ts`**: Renders a styled 500 error HTML page for SSR failures
- **`errors/reporting.ts`**: Reports React error boundary catches to Lovable's monitoring service
- **`utils.ts`**: Just the `cn()` utility (`clsx` + `tailwind-merge`)

### 5.5 Integrations

#### `src/integrations/supabase/`
- **`client.ts`**: Supabase client singleton (uses Proxy for lazy initialization). Reads env vars `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Configures auth persistence via localStorage
- **`client.server.ts`**: Server-side Supabase client (for SSR)
- **`auth-attacher.ts`**: Middleware that attaches Supabase session to server function context
- **`auth-middleware.ts`**: Auth middleware for route protection
- **`types.ts`**: Database type definitions (auto-generated from Supabase schema)

#### `src/integrations/nafaiq/`
- **`index.ts`**: Internal API client for NafaIQ-specific endpoints

### 5.6 Config Files

| File | Purpose |
|------|---------|
| **`vite.config.ts`** | Vite config — delegates to `@lovable.dev/vite-tanstack-config` which includes TanStack Start, React plugin, Tailwind, tsconfig paths, Nitro build, component tagger |
| **`tsconfig.json`** | TypeScript config — ES2022 target, React JSX, bundler module resolution, `@/` path alias |
| **`package.json`** | 61 dependencies, 6 scripts (dev/build/preview/lint/format) |
| **`eslint.config.js`** | ESLint flat config with TypeScript, React hooks, Prettier, React Refresh plugins |
| **`.prettierrc`** | Prettier formatting rules |

---

## 6. Key Features Explained

### 6.1 Haqeeqi Daulat™ (Real Wealth)
- **The problem**: PKR lost ~16% against USD in a year. A 12% PSX gain might mean a -3.2% real return in USD terms. Most Pakistani investors don't know this.
- **How NafaIQ solves it**: Shows devaluation-adjusted portfolio returns in USD/AED/SAR, calculates a Devaluation Shield Score, and recommends hedging strategies
- **UI**: Interactive flip card on the landing page + dashboard widget

### 6.2 AI Tutor
- **Architecture**: Server function (`askTutor`) → Lovable Gateway → Gemini 3 Flash
- **Context-aware**: Knows which lesson the user is reading, which section they're in
- **Bilingual**: Responds in Urdu or English based on app language
- **Safety**: URLs blocked, finance-only focus, max 4000 chars per message
- **Fallback chain**: API key missing → rate limited → out of credits → network error → each has a friendly Urdu/English message

### 6.3 Theme System (Dark/Light)
- **Single source of truth**: `nafaiq-landing-theme` localStorage key
- **Pre-hydration**: Inline `<script>` in `__root.tsx` reads localStorage and applies classes before React mounts (0ms flash)
- **Post-hydration**: `useEffect` in `LandingThemeProvider` keeps classes in sync
- **CSS scoping**: Both `.theme-light` and `.landing-light` classes used so landing page and app page styles both switch correctly
- **Smooth transitions**: 0.3s CSS transitions on `background-color`, `color`, `border-color`, `box-shadow`, `fill`, `stroke` — respects `prefers-reduced-motion`

### 6.4 Bilingual (English/Urdu)
- **Mechanism**: `useSyncExternalStore` hook reading from localStorage — re-renders only when language actually changes
- **Dictionary**: 606 UI keys + 452 Learn Hub keys
- **Edge cases**: Numbers stay in Western digits (deliberate UX decision), Urdu uses Noto Nastaliq font

### 6.5 Learn Hub
- **Structured learning**: Learning paths (Beginner → Intermediate), individual lessons, sections, quizzes
- **Progress tracking**: XP system, lesson completion status, bookmarks — all persisted to localStorage
- **Content types**: Paragraphs, callouts (tip/warning/example/note), formulas, tables
- **Quiz format**: Multiple choice with explanations for correct/incorrect answers

---

## 7. Data Flow

### User Authentication Flow
```
User submits email+password
  → supabase.auth.signInWithPassword() [use-auth.tsx]
  → Supabase Auth API validates
  → onAuthStateChange fires → session + user set
  → loadProfile() fetches from profiles table
  → AuthGate in __root.tsx sees user → renders AppShell + Outlet
  → If no user → redirect to /auth?redirect=/original-path
```

### AI Tutor Flow
```
User types message in Learn Hub chat popup
  → askTutor() server function called [learn-ai.functions.ts]
  → Zod validates input (lesson title, section, messages, lang)
  → Server constructs system prompt (Pakistan-specific, finance-focused)
  → POST to Lovable Gateway → Gemini 3 Flash
  → Response streamed back (or error fallback returned)
  → Chat UI updates with AI reply
```

### Theme Toggle Flow
```
User clicks theme toggle
  → toggleTheme() in LandingThemeContext
  → Updates React state + localStorage
  → useEffect fires → applyToDocument() adds/removes classes on <html>
  → CSS transitions animate the color changes (~300ms)
  → All components using useTheme() re-render with new theme
```

### Language Switch Flow
```
User selects Urdu in Settings
  → setLang('ur') in use-lang.ts
  → Updates localStorage + notifies listeners
  → useSyncExternalStore triggers re-render in subscribed components
  → t('Dashboard') looks up UR['Dashboard'] → 'ڈیش بورڈ'
  → If key not found → falls back to LEARN_UR → falls back to English key
```

---

## 8. Common Interview Q&A

### "Why TanStack Router instead of Next.js or Remix?"

TanStack Router is framework-agnostic (works with any Vite + React setup), gives us type-safe routes, file-based routing, built-in SSR via TanStack Start, and deep first-class integration with TanStack Query. Next.js would have locked us into their opinionated data-fetching patterns (server components, `fetch` caching). We wanted control over our rendering strategy — the landing page is fully static, auth is client-only, and app pages are SSR. Next.js doesn't give you that granularity without workarounds.

### "Why Supabase instead of a custom backend?"

Supabase handles auth, PostgreSQL, and real-time subscriptions out of the box — that's three services in one. For a financial app, we need proper auth with MFA support, row-level security, and a relational database. Building all that from scratch would take months. Supabase is also open-source and self-hostable, so there's no vendor lock-in if we need to migrate.

### "How do you handle the Flash of Wrong Theme (FOUC)?"

The pre-hydration inline script in `__root.tsx` runs synchronously before React mounts. It reads `localStorage` and adds `.theme-light` and `.landing-light` classes to `<html>` immediately. By the time React hydrates, the correct theme is already applied. The `useEffect` in `LandingThemeProvider` then keeps subsequent toggles in sync. This gives us a 0ms flash window.

### "How is the AI tutor different from a generic ChatGPT wrapper?"

Three things: (1) Context-awareness — the tutor knows what lesson the user is reading and what section they're in, so answers are relevant. (2) Pakistan-specific knowledge — uses KSE-100, PSX stocks (HBL, ENGRO, etc.), PKR devaluation, and Zakat concepts. (3) Full Urdu support — responds in Urdu when the app language is set to Urdu. Most generic chatbots don't handle financial Urdu well.

### "Why mock data instead of live APIs?"

The PSX doesn't have a free, publicly available real-time API suitable for development. We generate deterministic OHLCV data using a seeded PRNG (mulberry32) that produces realistic price movements with trends and corrections. The data structure (`Candle` interface with OHLCV) matches what a real API would return, so switching to a live feed is just a matter of replacing the data source — no UI changes needed.

### "How did you handle the bilingual challenge?"

We use a dictionary-based approach (`UR` object in `lang-ur.ts`) rather than i18n libraries like `react-intl`. This keeps things simple — no ICU message syntax, no build-time extraction. The `t()` function does a three-level lookup: UI dictionary → Learn Hub dictionary → fallback to the English key itself. For numbers, we deliberately keep Western digits because Urdu numerals are less familiar on financial screens. The font stack includes `Noto Nastaliq Urdu` for proper calligraphic Urdu rendering.

### "How does the Haqeeqi Daulat™ feature work?"

It's a concept feature demonstrating NafaIQ's thesis. PKR devaluation (e.g., 16% per year) erodes nominal PSX gains. We calculate the "real" USD-equivalent return by converting PKR portfolio values at historical exchange rates. The UI shows two numbers side by side: "PSX shows you +12.73%" vs "Real USD return -3.2%". This is implemented as a frontend calculation using mock exchange rate data — the architecture is designed to plug in real SBP/forex data later.

### "What's the biggest technical challenge you faced?"

The dual-theme system (dark + light) across landing and app pages. Originally there were two separate implementations — one for the marketing site, one for the authenticated app. They read/wrote different localStorage keys and applied different CSS classes. Unifying them into a single source of truth (`nafaiq-landing-theme` key, both `.theme-light` and `.landing-light` classes on `<html>`) while ensuring the pre-hydration script, the React context, and the CSS transitions all played nicely was tricky. The CRLF line-ending issue across the codebase also caused persistent lint warnings.

---

## 9. Talking Points for Each Role

### For Frontend Engineer Role
- **Strong points**: TypeScript throughout, theme-aware components (charts.tsx `useChartTheme()`), accessible UI (Radix primitives), responsive design (mobile bottom nav vs desktop sidebar), framer-motion page transitions with reduced-motion respect, PWA with manifest, pre-hydration script for FOUC prevention
- **Be ready to discuss**: How you'd add real-time PSX data, state management choices, performance optimization strategies

### For Full-Stack Engineer Role
- **Strong points**: Supabase auth + database integration, server functions with Zod validation, SSR with error recovery (server.ts error wrapper), Nitro deployment config, AI gateway proxy architecture, bilingual content pipeline
- **Be ready to discuss**: How you'd handle WebSocket-based real-time updates, database schema design, API rate limiting strategies

### For Product / Startup Role
- **Strong points**: Clear problem-solution fit (PKR devaluation awareness), market targeting (Pakistani investors), PWA-first approach (no app store friction), bilingual accessibility, halal/Zakat-aware features, freemium model (free terminal, paid AI reports)
- **Be ready to discuss**: User acquisition strategy, competitive landscape (vs. Bloomberg, vs. local brokers), monetization roadmap

### For AI / ML Role
- **Strong points**: Contextual AI tutor (lesson-aware prompt engineering), bilingual LLM interaction (English + Urdu), graceful fallback chain for API errors, safety constraints (finance-only, URL blocking)
- **Be ready to discuss**: Prompt engineering techniques, model selection rationale (Gemini 3 Flash vs GPT-4o vs Claude), fine-tuning possibilities for financial Urdu

---

## Quick Stats (Good to Mention)

| Metric | Value |
|--------|-------|
| **Dependencies** | 61 packages |
| **Components** | 22 custom + 46 shadcn/ui |
| **Routes** | 16 pages |
| **Largest file** | Landing page (`index.tsx`) — 2168 lines |
| **Lines of UI translation** | 606 English→Urdu keys |
| **Lines of lesson content** | 1212 lines |
| **Hooks** | 7 custom hooks |
| **CSS** | 1326 lines of Tailwind + custom styles |
| **Framework** | React 19 + TanStack Router + Vite 8 |

---

*Generated for NafaIQ presentation prep. Last updated: July 2026.*
