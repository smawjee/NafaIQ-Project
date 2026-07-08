# NafaIQ Monorepo — Project Guide

## Team

| Person | Module | Branch |
|---|---|---|
| **Usman** | ML signals, PSX architecture, cross-cutting | `feat/ml-signals` |
| **Shakir** | Finance module | `feat/finance` |
| **Tayyab** | Mobile app (React Native) | `feat/mobile` |
| **Misbah** | TBD | TBD |

## Architecture

Monorepo with Turborepo + pnpm workspaces.
Separated frontend and backend per mentor's specification.

```
frontend/
└── packages/
    ├── web/      # React 19 + TanStack Start PWA
    ├── mobile/   # React Native app (Tayyab)
    └── shared/   # Shared types, utils, hooks

backend/           # Python FastAPI (shared by both web and mobile)
├── src/app/       # Application code
├── tests/         # Python tests (pytest)
├── database/
│   └── migrations/ # Supabase SQL migrations
└── pyproject.toml # Python dependencies
```

## Data flow

```
  Web PWA ───────┐
                  ├──► Python FastAPI ──► Supabase Postgres
  Mobile App ────┘        │
                          └──► Supabase REST (PostgREST)
```

## Getting started

```bash
# Install all JS dependencies
pnpm install

# Install Python dependencies
cd backend
pip install -e ".[dev]"

# Start web dev server
pnpm run dev                    # from root (or cd frontend/packages/web && pnpm dev)

# Start Python API
cd backend && python -m uvicorn src.app.main:app --reload --port 8000

# Typecheck
pnpm run typecheck

# Lint
pnpm run lint

# Format
pnpm run format

# API tests
cd backend && pytest tests/ -v
```

## Git workflow

```
main ────────► tagged releases (v0.2.0, v0.3.0)
  │
  └── develop ► integration branch — all PRs merge here
        │
        ├── feat/ml-signals  (Usman)
        ├── feat/finance     (Shakir)
        ├── feat/mobile      (Tayyab)
        └── feat/<module>    (Misbah)
```

### Branch naming
```
feat/<module>     — new features
fix/<description> — bug fixes
refactor/<what>   — code restructuring
chore/<what>      — maintenance
docs/<what>       — documentation
```

### Commit convention
```
feat(scope): description
fix(scope): description
refactor(scope): description
```

### Merge strategy
- Squash-merge feature branches into develop
- Fast-forward develop into main on releases
- Delete feature branches after merge

## Supabase

- Project ref: `gmonfgxmjgzipnbhgimv`
- Regenerate types after schema change:
  ```bash
  npx supabase gen types typescript --project-id gmonfgxmjgzipnbhgimv --schema public > frontend/packages/web/src/integrations/supabase/types.ts
  ```
- Migrations: `backend/database/migrations/` — run via Supabase Dashboard SQL Editor

## Environment variables

### frontend/packages/web/.env
```
VITE_SUPABASE_URL=https://gmonfgxmjgzipnbhgimv.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
VITE_PSX_API_URL=http://localhost:8000
VITE_PSX_API_TOKEN=<api-token>
```

### backend/.env
```
SUPABASE_URL=https://gmonfgxmjgzipnbhgimv.supabase.co
SUPABASE_SECRET_KEY=<sb_secret_key>
SUPABASE_SERVICE_ROLE_KEY=<legacy-jwt>
SUPABASE_DATABASE_PASSWORD=<db-password>
SUPABASE_POOLER_HOST=aws-1-ap-southeast-1.pooler.supabase.com
SUPABASE_POOLER_PORT=6543
SUPABASE_POOLER_USER=postgres.gmonfgxmjgzipnbhgimv
PSX_API_TOKEN=<api-token>
```

## Recall files

Always read `recall/` before starting any task:
- `recall/progress.md` — current phase status
- `recall/project.md` — architecture overview
- `recall/explaination.md` — decision log (40+ entries)
- `recall/plan.md` — PSX data sources
- `recall/Complete Project Plan.md` — master implementation plan
