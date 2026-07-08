# Design System Master File

> **LOGIC:** When building a specific page, first check `design/pages/[page-name].md` if it exists. Otherwise, strictly follow the rules below.

---

**Project:** NafaIQ
**Generated:** 2026-07-01 17:59:08
**Category:** Pakistan Stock Exchange Intelligence Platform

---

## Global Rules

### Color Palette

| Role            | Hex       | CSS Variable             |
|-----------------|-----------|--------------------------|
| Primary         | `#00d4aa` | `--color-primary`        |
| On Primary      | `#020617` | `--color-primary-alt`    |
| Background      | `#0a0a0f` | `--color-background`     |
| Foreground      | `#ffffff` | `--color-foreground`     |
| Surface         | `rgba(18, 18, 26, 0.8)` | `--color-surface` |
| Surface Alt     | `#101018` | `--color-surface-alt`    |
| Elevated        | `#16161f` | `--color-elevated`       |
| Gold (Premium)  | `#d4a017` | `--color-gold`           |
| Gold Hover      | `#e3b324` | `--color-gold-hover`     |
| Bull (Up)       | `#10b981` | `--color-bull`           |
| Bear (Down)     | `#e5484d` | `--color-bear`           |
| Warning         | `#f5a524` | `--color-warning`        |
| Neutral         | `#64748b` | `--color-neutral`        |
| Info            | `#00d4aa` | `--color-info`           |
| Border          | `rgba(255, 255, 255, 0.06)` | `--color-border` |
| Border Hover    | `rgba(255, 255, 255, 0.12)` | `--color-border-hover` |
| Ring            | `#00d4aa` | `--color-ring`           |
| AI / Accent     | `#00d4aa` | `--color-ai`             |

**Color Notes:** Dark-first glassmorphism with teal primary and gold premium accents. Market-driven semantic colors (bull/bear).

### Typography

| Role       | Font                  | CSS Variable    |
|------------|-----------------------|-----------------|
| Sans (UI)  | Inter                 | `--font-sans`   |
| Display    | Inter                 | `--font-display`|
| Mono       | JetBrains Mono        | `--font-mono`   |
| Urdu Body  | Noto Naskh Arabic     | `--font-urdu`   |
| Urdu Display | Noto Nastaliq Urdu | `--font-nastaliq` |

**Google Fonts:** Inter, JetBrains Mono, Noto Naskh Arabic, Noto Nastaliq Urdu

### Spacing Tokens

| Token          | Value   | Usage                  |
|----------------|---------|------------------------|
| `--space-xs`   | `4px`   | Tight gaps, badge padding |
| `--space-sm`   | `8px`   | Icon gaps, inline spacing |
| `--space-md`   | `16px`  | Standard padding       |
| `--space-lg`   | `24px`  | Section padding        |
| `--space-xl`   | `32px`  | Large gaps             |
| `--space-2xl`  | `48px`  | Section margins        |
| `--space-3xl`  | `64px`  | Hero padding           |

### Border Radius Tokens

| Token             | Value   | Usage                           |
|-------------------|---------|---------------------------------|
| `--radius-badge`  | `4px`   | Badges, small indicators        |
| `--radius-btn`    | `8px`   | Buttons, inputs, dialogs        |
| `--radius-card`   | `14px`  | Cards, surfaces                 |
| `--radius-modal`  | `14px`  | Modals, drawers, dialogs        |

Use utility classes: `rounded-badge`, `rounded-btn`, `rounded-card`, `rounded-modal`.

### Glassmorphism Surface

```css
background: rgba(18, 18, 26, 0.8);
backdrop-filter: blur(12px);
border: 1px solid rgba(255, 255, 255, 0.06);
```

---

## Component Specs

### Buttons

- **Radius:** `rounded-btn` (8px)
- **Primary:** `bg-primary text-primary-foreground hover:opacity-90`
- **Gold (Premium):** `bg-gold text-gold-foreground hover:bg-gold-hover`
- **Ghost:** `bg-transparent text-foreground hover:bg-hover`
- **Padding:** `px-4 py-2` (or `px-6 py-3` for larger)
- **Transition:** `transition-all duration-200`

### Cards

- **Radius:** `rounded-card` (14px)
- **Surface:** `bg-surface backdrop-blur-xl border border-border`
- **Shadow:** `shadow-card`
- **Padding:** `p-4` to `p-6`
- **Hover:** `hover:border-border-hover hover:bg-[rgba(18,18,26,0.9)]`

### Inputs

- **Radius:** `rounded-btn` (8px)
- **Background:** `bg-input`
- **Border:** `border-border focus:border-ring focus:ring-1 focus:ring-ring`
- **Padding:** `px-3 py-2`

### Modals / Dialogs

- **Radius:** `rounded-modal` (14px)
- **Background:** `bg-elevated`
- **Overlay:** `bg-black/60 backdrop-blur-sm`
- **Padding:** `p-6`

### Badges

- **Radius:** `rounded-badge` (4px)
- **Padding:** `px-1.5 py-0.5`
- **Font:** `text-xs font-medium`
- **Bull:** `bg-bull/15 text-bull`
- **Bear:** `bg-bear/15 text-bear`
- **Gold:** `bg-gold/15 text-gold`

---

## Style Guidelines

**Style:** Dark Glassmorphism + Premium Market Intelligence

**Keywords:** dark-first, glass, blur, teal accent, gold premium, stock market, data-heavy, terminal-inspired, real-time, Pakistan Stock Exchange, Urdu support, responsive

**Key Effects:**
- Backdrop blur surfaces (12px default)
- Subtle borders on surfaces (`rgba(255,255,255,0.06)`)
- Teal primary glow on focus/active states
- Gold shimmer on premium badges
- Flash animations for price changes (green flash up, red flash down)
- Smooth transitions (150-300ms ease-out)

---

## Anti-Patterns (Do NOT Use)

- ❌ Light backgrounds or light mode colors
- ❌ Flat no-blur surfaces
- ❌ Blue primary (use teal `#00d4aa`)
- ❌ Emojis as icons — Use SVG icons (Lucide, Heroicons)
- ❌ Missing `cursor:pointer` — All clickable elements must have cursor:pointer
- ❌ Layout-shifting hovers — Avoid scale transforms that shift layout
- ❌ Low contrast text — Maintain 4.5:1 minimum contrast ratio
- ❌ Instant state changes — Always use transitions (150-300ms)
- ❌ Invisible focus states — Focus states must be visible for a11y
- ❌ Hardcoded radius values — Use `rounded-badge/btn/card/modal` utilities
- ❌ Hardcoded spacing — Use Tailwind spacing scale or `--space-*` tokens

---

## Pre-Delivery Checklist

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Lucide/Heroicons)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Dark theme only — no light mode needed
- [ ] Glassmorphism surfaces use `bg-surface backdrop-blur-xl border border-border`
- [ ] Radius utilities used instead of hardcoded values
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] Urdu text uses appropriate font family
- [ ] No horizontal scroll on mobile
