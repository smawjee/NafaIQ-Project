# LearnHub AI Tutor Phase 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the LearnHub AI Tutor off the Lovable gateway onto FastAPI with Gemini (primary) + Groq (fallback), SSE streaming, per-plan daily quota, and Supabase-persisted chat history + usage.

**Architecture:** One new FastAPI router (`/api/ai/tutor` SSE + two GETs) following the existing `repositories → services → api` layering; the browser calls FastAPI directly with the Supabase JWT (same pattern as `/api/portfolio`). Web panels share a new `useTutorChat` hook backed by a small SSE client; the TanStack `askTutor` server function is retired.

**Tech Stack:** Python 3.12, FastAPI, httpx (SSE streaming), SQLAlchemy Core (`text()` SQL via Supavisor pooler), pytest (+`asyncio_mode=auto`), React 19 + TanStack Start, vitest (new, minimal).

**Spec:** `docs/superpowers/specs/2026-07-12-learnhub-ai-tutor-phase6.md`

## Global Constraints

- Branch: `usman`. Commit prefixes: `feat(ai)` backend, `feat(web)` frontend, `docs`/`test` as fitting.
- Providers: Gemini primary (`gemini-2.5-flash`), Groq fallback (`llama-3.3-70b-versatile`), both via OpenAI-compatible `/chat/completions`, `stream: true`.
- Keys ONLY in backend env: `GEMINI_API_KEY`, `GROQ_API_KEY`. Never in any client bundle or `VITE_*` var.
- Access: logged-in only via `Depends(require_user)` (returns `{user_id, email, plan, features}`).
- Quota: `plan_features.ai_tutor_daily_limit` — Free 10 (already seeded), Pro 100 (this migration), Premium NULL = unlimited. Window = UTC date. Increment only after a successful reply.
- Prompt economy: request carries only `lessonTitle` (≤200), optional `lessonContext` (≤500 chars), ≤12 recent messages, each ≤4000 chars. Never full lesson bodies.
- Fallback rule: switch Gemini→Groq only if the stream fails BEFORE the first token reaches the client; never mid-stream.
- Do not touch mobile (`frontend/packages/mobile`), deployment config, or unrelated UI.
- Migrations run via Supabase Dashboard SQL Editor (per AGENTS.md); after applying, regenerate `types.ts`.
- Backend tests: `cd backend && pytest tests/<file> -v` (asyncio_mode=auto, pythonpath=src). Live-DB tests follow the existing pattern (`test_sqlalchemy_queries.py`) and must clean up rows they insert.
- Web checks: `cd frontend/packages/web && npx tsc --noEmit && npx eslint .` plus `npx vitest run` once Task 8 adds vitest.

## File Structure

| File | Responsibility |
|---|---|
| `backend/database/migrations/20260712000000_ai_tutor_history_usage.sql` | Create `ai_chat_history` + `ai_usage` (RLS, owner-only), set Pro tutor limit = 100 |
| `backend/src/app/config.py` (modify) | Provider keys, model names, timeout settings |
| `backend/src/app/schemas/ai.py` (create) | `TutorMessage`, `TutorRequest` pydantic models |
| `backend/src/app/repositories/ai_repo.py` (create) | Raw-SQL data access: history insert/read, usage read/increment |
| `backend/src/app/services/ai/__init__.py` (create) | Package marker |
| `backend/src/app/services/ai/providers.py` (create) | httpx SSE clients `stream_gemini` / `stream_groq`, `ProviderError` |
| `backend/src/app/services/ai/tutor.py` (create) | System prompt, provider fallback generator, persistence, history read |
| `backend/src/app/services/ai/quota.py` (create) | `check_quota`, `usage_summary` |
| `backend/src/app/api/ai.py` (create) | Router: `POST /ai/tutor` (SSE), `GET /ai/tutor/history`, `GET /ai/tutor/usage` |
| `backend/src/app/middleware/auth.py` (modify) | Add `/api/ai` to `USER_PATHS_PREFIXES` |
| `backend/src/app/main.py` (modify) | Register ai router |
| `frontend/packages/web/src/lib/ai/tutor-client.ts` (create) | SSE fetch client + pure `parseSseBuffer` + history/usage GETs |
| `frontend/packages/web/src/hooks/learn/use-tutor-chat.ts` (create) | Shared chat state machine (streaming, quota, auth, abort) |
| `frontend/packages/web/src/features/learn/hub/components/HubChatPanel.tsx` (rewrite) | Hub panel on the hook |
| `frontend/packages/web/src/features/learn/lesson/components/ChatPanel.tsx` (rewrite) | Lesson panel on the hook |
| `frontend/packages/web/src/features/learn/ai-functions.ts` (delete) | Retired Lovable server fn |

---

### Task 1: Database migration — `ai_chat_history`, `ai_usage`, Pro quota

**Files:**
- Create: `backend/database/migrations/20260712000000_ai_tutor_history_usage.sql`
- Create: `backend/tests/test_ai_migration.py`
- Modify (regenerate): `frontend/packages/web/src/integrations/supabase/types.ts`

**Interfaces:**
- Consumes: existing `plan_features` table (plan ∈ Free/Pro/Premium), `auth.users`.
- Produces: tables `public.ai_chat_history` (cols: `id, user_id, role, content, lesson_title, lang, provider, model, tokens_in, tokens_out, created_at`) and `public.ai_usage` (PK `(user_id, usage_date)`, cols `message_count, tokens_in, tokens_out, updated_at`) that Tasks 4–7 query.

- [ ] **Step 1: Write the failing test (tables don't exist yet)**

Create `backend/tests/test_ai_migration.py`:

```python
"""Verifies the 20260712000000_ai_tutor_history_usage migration is applied."""
from __future__ import annotations

import pytest
from sqlalchemy import text


async def _scalar(sql: str, **params):
    from app.db.sqlalchemy import get_engine

    async with get_engine().connect() as conn:
        result = await conn.execute(text(sql), params)
        return result.scalar()


@pytest.mark.asyncio
async def test_ai_chat_history_table_exists():
    assert await _scalar("SELECT to_regclass('public.ai_chat_history')") is not None


@pytest.mark.asyncio
async def test_ai_usage_table_exists():
    assert await _scalar("SELECT to_regclass('public.ai_usage')") is not None


@pytest.mark.asyncio
async def test_ai_usage_pk_is_user_and_date():
    count = await _scalar(
        """
        SELECT COUNT(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'public' AND table_name = 'ai_usage'
          AND constraint_name IN (
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'ai_usage' AND constraint_type = 'PRIMARY KEY'
          )
        """
    )
    assert count == 2  # (user_id, usage_date)


@pytest.mark.asyncio
async def test_plan_tutor_limits():
    free = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Free'")
    pro = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Pro'")
    premium = await _scalar("SELECT ai_tutor_daily_limit FROM plan_features WHERE plan = 'Premium'")
    assert free == 10
    assert pro == 100
    assert premium is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_ai_migration.py -v`
Expected: FAIL — `to_regclass` returns `None` for both tables, and Pro limit is `None` (not 100).

- [ ] **Step 3: Write the migration**

Create `backend/database/migrations/20260712000000_ai_tutor_history_usage.sql`:

```sql
-- AI Tutor Phase 6: persisted chat history + daily usage tracking + Pro quota.
-- Spec: docs/superpowers/specs/2026-07-12-learnhub-ai-tutor-phase6.md
-- Apply via Supabase Dashboard SQL Editor.

-- ============ ai_chat_history ============
CREATE TABLE IF NOT EXISTS public.ai_chat_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    lesson_title TEXT,
    lang         TEXT CHECK (lang IN ('en', 'ur')),
    provider     TEXT,
    model        TEXT,
    tokens_in    INT,
    tokens_out   INT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_chat_history_user_created
    ON public.ai_chat_history (user_id, created_at DESC);

ALTER TABLE public.ai_chat_history ENABLE ROW LEVEL SECURITY;

-- Owner-only reads; all writes happen server-side via the service role.
DROP POLICY IF EXISTS "ai_chat_history_owner_select" ON public.ai_chat_history;
CREATE POLICY "ai_chat_history_owner_select" ON public.ai_chat_history
    FOR SELECT USING (auth.uid() = user_id);

GRANT SELECT ON public.ai_chat_history TO authenticated;
GRANT ALL ON public.ai_chat_history TO service_role;

-- ============ ai_usage ============
CREATE TABLE IF NOT EXISTS public.ai_usage (
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_date    DATE NOT NULL,
    message_count INT NOT NULL DEFAULT 0,
    tokens_in     INT NOT NULL DEFAULT 0,
    tokens_out    INT NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, usage_date)
);

ALTER TABLE public.ai_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_usage_owner_select" ON public.ai_usage;
CREATE POLICY "ai_usage_owner_select" ON public.ai_usage
    FOR SELECT USING (auth.uid() = user_id);

GRANT SELECT ON public.ai_usage TO authenticated;
GRANT ALL ON public.ai_usage TO service_role;

-- ============ plan quota ============
-- Free already 10, Premium already NULL (unlimited). Pro: NULL -> 100/day.
UPDATE public.plan_features SET ai_tutor_daily_limit = 100 WHERE plan = 'Pro';
```

- [ ] **Step 4: Apply the migration**

Manual step (per AGENTS.md): open Supabase Dashboard → SQL Editor → paste the file contents → Run. Confirm "Success" with no errors.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && pytest tests/test_ai_migration.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Regenerate Supabase types**

Run from repo root:
```bash
npx supabase gen types typescript --project-id gmonfgxmjgzipnbhgimv --schema public > frontend/packages/web/src/integrations/supabase/types.ts
```
Expected: `types.ts` now contains `ai_chat_history` and `ai_usage` table types. Then `cd frontend/packages/web && npx tsc --noEmit` — expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/database/migrations/20260712000000_ai_tutor_history_usage.sql backend/tests/test_ai_migration.py frontend/packages/web/src/integrations/supabase/types.ts
git commit -m "feat(ai): add ai_chat_history + ai_usage tables and Pro tutor quota"
```

---

### Task 2: Backend config — provider keys and models

**Files:**
- Modify: `backend/src/app/config.py` (add fields after `resend_from_email`, ~line 58)
- Create or modify: `backend/.env.example` (placeholders only)
- Test: `backend/tests/test_ai_config.py`

**Interfaces:**
- Produces: `settings.gemini_api_key: str`, `settings.groq_api_key: str`, `settings.ai_tutor_model_primary: str`, `settings.ai_tutor_model_fallback: str`, `settings.ai_tutor_request_timeout_s: float` — consumed by Task 5.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_config.py`:

```python
"""AI tutor settings exist with sane defaults (keys default empty)."""
from __future__ import annotations

from app.config import Settings


def test_ai_settings_defaults():
    s = Settings(_env_file=None)  # ignore .env: assert pure defaults
    assert s.gemini_api_key == ""
    assert s.groq_api_key == ""
    assert s.ai_tutor_model_primary == "gemini-2.5-flash"
    assert s.ai_tutor_model_fallback == "llama-3.3-70b-versatile"
    assert s.ai_tutor_request_timeout_s == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'gemini_api_key'` (pydantic: field not defined).

- [ ] **Step 3: Add the settings fields**

In `backend/src/app/config.py`, after the `resend_from_email` line, add:

```python
    # AI tutor providers (Phase 6). Keys live ONLY in backend env (Railway) —
    # never shipped to any client bundle. Gemini is primary, Groq is fallback.
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ai_tutor_model_primary: str = "gemini-2.5-flash"
    ai_tutor_model_fallback: str = "llama-3.3-70b-versatile"
    ai_tutor_request_timeout_s: float = 30.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_config.py -v`
Expected: PASS.

- [ ] **Step 5: Add env placeholders**

If `backend/.env.example` exists, append; otherwise create it with:

```
# AI tutor (Phase 6) — get free keys from Google AI Studio and console.groq.com
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key
# optional overrides
# AI_TUTOR_MODEL_PRIMARY=gemini-2.5-flash
# AI_TUTOR_MODEL_FALLBACK=llama-3.3-70b-versatile
# AI_TUTOR_REQUEST_TIMEOUT_S=30
```

Also add real keys to your local `backend/.env` (and later Railway env) — NOT committed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/config.py backend/.env.example backend/tests/test_ai_config.py
git commit -m "feat(ai): add Gemini/Groq provider settings"
```

---

### Task 3: Request schemas

**Files:**
- Create: `backend/src/app/schemas/ai.py`
- Test: `backend/tests/test_ai_schemas.py`

**Interfaces:**
- Produces: `TutorMessage(role: Literal["user","assistant"], content: str)` and `TutorRequest(lessonTitle: str, lessonContext: str | None, lang: Literal["en","ur"] = "en", messages: list[TutorMessage])` — consumed by Tasks 6–7. Field names are camelCase to match the existing frontend payload shape.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_schemas.py`:

```python
"""TutorRequest validation bounds (mirrors the old zod schema)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _valid_payload(**overrides):
    payload = {
        "lessonTitle": "PSX investing basics",
        "lang": "en",
        "messages": [{"role": "user", "content": "What is KSE-100?"}],
    }
    payload.update(overrides)
    return payload


def test_valid_request_parses():
    from app.schemas.ai import TutorRequest

    req = TutorRequest(**_valid_payload())
    assert req.lessonTitle == "PSX investing basics"
    assert req.lang == "en"
    assert req.lessonContext is None
    assert req.messages[0].role == "user"


def test_rejects_empty_messages():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[]))


def test_rejects_more_than_12_messages():
    from app.schemas.ai import TutorRequest

    msgs = [{"role": "user", "content": f"q{i}"} for i in range(13)]
    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=msgs))


def test_rejects_long_lesson_context():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(lessonContext="x" * 501))


def test_rejects_bad_role_and_long_content():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[{"role": "system", "content": "hack"}]))
    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[{"role": "user", "content": "x" * 4001}]))


def test_lang_defaults_to_en():
    from app.schemas.ai import TutorRequest

    payload = _valid_payload()
    del payload["lang"]
    assert TutorRequest(**payload).lang == "en"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.ai'`.

- [ ] **Step 3: Write the schemas**

Create `backend/src/app/schemas/ai.py`:

```python
"""AI tutor request schemas.

Field names are camelCase to match the web client payload (the shape the old
TanStack askTutor server fn accepted), so the frontend swap is drop-in.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TutorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class TutorRequest(BaseModel):
    lessonTitle: str = Field(min_length=1, max_length=200)
    # Short lesson context only (e.g. active section heading) — never full
    # lesson bodies; keeps token usage inside free-tier budgets.
    lessonContext: str | None = Field(default=None, max_length=500)
    lang: Literal["en", "ur"] = "en"
    messages: list[TutorMessage] = Field(min_length=1, max_length=12)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_schemas.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/schemas/ai.py backend/tests/test_ai_schemas.py
git commit -m "feat(ai): add TutorRequest/TutorMessage schemas"
```

---

### Task 4: Repository — history + usage data access

**Files:**
- Create: `backend/src/app/repositories/ai_repo.py`
- Test: `backend/tests/test_ai_repo.py` (live-DB integration, self-cleaning)

**Interfaces:**
- Consumes: Task 1 tables; `app.repositories.base.connect/begin` (`conn` is a SQLAlchemy `AsyncConnection`).
- Produces (all `async`, first arg `conn: Executor`):
  - `insert_message(conn, user_id: str, role: str, content: str, *, lesson_title: str | None = None, lang: str | None = None, provider: str | None = None, model: str | None = None) -> None`
  - `recent_history(conn, user_id: str, limit: int) -> list[dict]` — oldest-first, keys: `id, role, content, lesson_title, lang, created_at`
  - `get_today_usage(conn, user_id: str) -> int` — today's (UTC) `message_count`, 0 if no row
  - `increment_usage(conn, user_id: str, tokens_in: int = 0, tokens_out: int = 0) -> None` — upsert +1

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_repo.py`:

```python
"""Integration tests for ai_repo against the live DB (pattern of
test_sqlalchemy_queries.py). Uses an existing profile row as the user and
cleans up everything it inserts."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.repositories.base import begin, connect


async def _any_user_id() -> str | None:
    async with connect() as conn:
        result = await conn.execute(text("SELECT id FROM profiles LIMIT 1"))
        row = result.first()
    return str(row[0]) if row else None


async def _cleanup(user_id: str) -> None:
    async with begin() as conn:
        await conn.execute(
            text("DELETE FROM ai_chat_history WHERE user_id = :uid AND content LIKE 'TESTAI%'"),
            {"uid": user_id},
        )
        await conn.execute(
            text("DELETE FROM ai_usage WHERE user_id = :uid AND usage_date = (now() AT TIME ZONE 'utc')::date"),
            {"uid": user_id},
        )


@pytest.mark.asyncio
async def test_history_roundtrip_oldest_first():
    from app.repositories import ai_repo

    user_id = await _any_user_id()
    if not user_id:
        pytest.skip("no profiles row in DB")
    try:
        async with begin() as conn:
            await ai_repo.insert_message(
                conn, user_id, "user", "TESTAI question", lesson_title="PSX basics", lang="en"
            )
            await ai_repo.insert_message(
                conn, user_id, "assistant", "TESTAI answer",
                lesson_title="PSX basics", lang="en", provider="gemini", model="gemini-2.5-flash",
            )
        async with connect() as conn:
            rows = await ai_repo.recent_history(conn, user_id, limit=10)
        test_rows = [r for r in rows if str(r["content"]).startswith("TESTAI")]
        assert [r["role"] for r in test_rows] == ["user", "assistant"]  # oldest-first
        assert test_rows[0]["lesson_title"] == "PSX basics"
    finally:
        await _cleanup(user_id)


@pytest.mark.asyncio
async def test_usage_starts_at_zero_and_increments():
    from app.repositories import ai_repo

    user_id = await _any_user_id()
    if not user_id:
        pytest.skip("no profiles row in DB")
    try:
        async with begin() as conn:
            await conn.execute(
                text("DELETE FROM ai_usage WHERE user_id = :uid AND usage_date = (now() AT TIME ZONE 'utc')::date"),
                {"uid": user_id},
            )
        async with connect() as conn:
            assert await ai_repo.get_today_usage(conn, user_id) == 0
        async with begin() as conn:
            await ai_repo.increment_usage(conn, user_id)
        async with begin() as conn:
            await ai_repo.increment_usage(conn, user_id, tokens_in=10, tokens_out=20)
        async with connect() as conn:
            assert await ai_repo.get_today_usage(conn, user_id) == 2
    finally:
        await _cleanup(user_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories.ai_repo'` (or ImportError inside the test body).

- [ ] **Step 3: Write the repository**

Create `backend/src/app/repositories/ai_repo.py`:

```python
"""AI tutor data access: chat history + daily usage counters.

All writes run server-side with the service connection (bypasses RLS), so
user_id MUST always come from the verified JWT (require_user), never the client.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def insert_message(
    conn: Executor,
    user_id: str,
    role: str,
    content: str,
    *,
    lesson_title: Optional[str] = None,
    lang: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO ai_chat_history
                (user_id, role, content, lesson_title, lang, provider, model)
            VALUES (:uid, :role, :content, :lesson_title, :lang, :provider, :model)
            """
        ),
        {
            "uid": user_id,
            "role": role,
            "content": content,
            "lesson_title": lesson_title,
            "lang": lang,
            "provider": provider,
            "model": model,
        },
    )


async def recent_history(conn: Executor, user_id: str, limit: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            SELECT id, role, content, lesson_title, lang, created_at
            FROM ai_chat_history
            WHERE user_id = :uid
            ORDER BY created_at DESC, id DESC
            LIMIT :lim
            """
        ),
        {"uid": user_id, "lim": limit},
    )
    rows = [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "lesson_title": r["lesson_title"],
            "lang": r["lang"],
            "created_at": str(r["created_at"]),
        }
        for r in result.mappings().all()
    ]
    rows.reverse()  # oldest-first for direct rendering
    return rows


async def get_today_usage(conn: Executor, user_id: str) -> int:
    result = await conn.execute(
        text(
            """
            SELECT message_count FROM ai_usage
            WHERE user_id = :uid
              AND usage_date = (now() AT TIME ZONE 'utc')::date
            """
        ),
        {"uid": user_id},
    )
    row = result.first()
    return int(row[0]) if row else 0


async def increment_usage(
    conn: Executor, user_id: str, tokens_in: int = 0, tokens_out: int = 0
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO ai_usage (user_id, usage_date, message_count, tokens_in, tokens_out)
            VALUES (:uid, (now() AT TIME ZONE 'utc')::date, 1, :tin, :tout)
            ON CONFLICT (user_id, usage_date) DO UPDATE SET
                message_count = ai_usage.message_count + 1,
                tokens_in = ai_usage.tokens_in + EXCLUDED.tokens_in,
                tokens_out = ai_usage.tokens_out + EXCLUDED.tokens_out,
                updated_at = now()
            """
        ),
        {"uid": user_id, "tin": tokens_in, "tout": tokens_out},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_repo.py -v`
Expected: 2 PASS (or SKIP if the DB has no profiles — it does, so PASS).

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/repositories/ai_repo.py backend/tests/test_ai_repo.py
git commit -m "feat(ai): add ai_repo for chat history and daily usage"
```

---

### Task 5: Provider clients — Gemini + Groq SSE streaming

**Files:**
- Create: `backend/src/app/services/ai/__init__.py` (empty)
- Create: `backend/src/app/services/ai/providers.py`
- Test: `backend/tests/test_ai_providers.py` (httpx.MockTransport — no network)

**Interfaces:**
- Consumes: Task 2 settings.
- Produces:
  - `class ProviderError(Exception)`
  - `stream_gemini(messages: list[dict[str, str]], *, transport: httpx.AsyncBaseTransport | None = None) -> AsyncIterator[str]`
  - `stream_groq(messages: list[dict[str, str]], *, transport: httpx.AsyncBaseTransport | None = None) -> AsyncIterator[str]`
  - Module constants `GEMINI_URL`, `GROQ_URL`.
  - Both raise `ProviderError` on missing key, non-200, or transport error; yield text deltas otherwise. `transport` exists solely for test injection.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_providers.py`:

```python
"""Provider SSE clients, tested with httpx.MockTransport (no network)."""
from __future__ import annotations

import httpx
import pytest

SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":" PSX"}}]}\n\n'
    b'data: {"choices":[{"delta":{}}]}\n\n'
    b"data: [DONE]\n\n"
)

MESSAGES = [{"role": "user", "content": "hi"}]


def _ok_transport() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=SSE_BODY, headers={"content-type": "text/event-stream"}
        )
    )


def _error_transport(status: int) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "x"}))


@pytest.mark.asyncio
async def test_stream_gemini_yields_deltas(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    chunks = [c async for c in providers.stream_gemini(MESSAGES, transport=_ok_transport())]
    assert chunks == ["Hello", " PSX"]


@pytest.mark.asyncio
async def test_stream_groq_yields_deltas(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    chunks = [c async for c in providers.stream_groq(MESSAGES, transport=_ok_transport())]
    assert chunks == ["Hello", " PSX"]


@pytest.mark.asyncio
async def test_http_429_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=_error_transport(429)):
            pass


@pytest.mark.asyncio
async def test_missing_key_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_gemini(MESSAGES, transport=_ok_transport()):
            pass


@pytest.mark.asyncio
async def test_connect_error_raises_provider_error(monkeypatch):
    from app.config import settings
    from app.services.ai import providers

    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    def boom(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(providers.ProviderError):
        async for _ in providers.stream_groq(MESSAGES, transport=httpx.MockTransport(boom)):
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai'`.

- [ ] **Step 3: Write the providers**

Create empty `backend/src/app/services/ai/__init__.py`, then create `backend/src/app/services/ai/providers.py`:

```python
"""Async SSE clients for OpenAI-compatible chat-completion providers.

Gemini (primary) and Groq (fallback) both expose /chat/completions with
`stream: true` returning `data: {json}` SSE lines terminated by `data: [DONE]`.
The `transport` kwarg exists only for test injection (httpx.MockTransport).
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx

from app.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class ProviderError(Exception):
    """Provider unusable: missing key, HTTP error, transport error."""


async def _stream_chat(
    url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    if not api_key:
        raise ProviderError(f"no API key configured for {url}")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        async with httpx.AsyncClient(
            timeout=settings.ai_tutor_request_timeout_s, transport=transport
        ) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as res:
                if res.status_code != 200:
                    await res.aread()
                    raise ProviderError(f"{url}: HTTP {res.status_code}")
                async for line in res.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue  # tolerate malformed keep-alive lines
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
    except httpx.HTTPError as e:
        raise ProviderError(f"{url}: {e}") from e


def stream_gemini(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GEMINI_URL, settings.gemini_api_key, settings.ai_tutor_model_primary, messages, transport
    )


def stream_groq(
    messages: list[dict[str, str]],
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AsyncIterator[str]:
    return _stream_chat(
        GROQ_URL, settings.groq_api_key, settings.ai_tutor_model_fallback, messages, transport
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_providers.py -v`
Expected: 5 PASS. (Note: the missing-key `ProviderError` raises on first `anext`, not at call time — the test iterates, so this is covered.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/ai/__init__.py backend/src/app/services/ai/providers.py backend/tests/test_ai_providers.py
git commit -m "feat(ai): add Gemini/Groq SSE provider clients"
```

---

### Task 6: Tutor service — prompt, fallback, persistence, quota

**Files:**
- Create: `backend/src/app/services/ai/tutor.py`
- Create: `backend/src/app/services/ai/quota.py`
- Test: `backend/tests/test_ai_tutor_service.py`

**Interfaces:**
- Consumes: Task 3 `TutorRequest`; Task 4 `ai_repo`; Task 5 `providers` (`stream_gemini`, `stream_groq`, `ProviderError`); `app.repositories.base.connect/begin`.
- Produces:
  - `tutor.build_system_prompt(lesson_title: str, lesson_context: str | None, lang: str) -> str`
  - `tutor.stream_reply(body: TutorRequest, *, transport=None) -> AsyncIterator[dict]` — yields `{"type":"token","text":str}` then finally `{"type":"meta","provider":str,"model":str}`; raises `ProviderError` if all providers fail (or mid-stream failure)
  - `tutor.persist_exchange(user_id: str, question: str, reply: str, *, lesson_title: str, lang: str, provider: str | None, model: str | None) -> None`
  - `tutor.get_history(user_id: str, limit: int = 20) -> list[dict]`
  - `quota.check_quota(user: dict) -> tuple[bool, int, int | None]` — `(allowed, used_today, limit)`; `limit None` = unlimited
  - `quota.usage_summary(user: dict) -> dict` — `{"used": int, "limit": int | None, "remaining": int | None}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_tutor_service.py`:

```python
"""Tutor service: prompt building, provider fallback, quota math.

Provider calls are faked by monkeypatching app.services.ai.providers functions
(no network); quota DB reads are faked by monkeypatching ai_repo.
"""
from __future__ import annotations

import pytest

from app.schemas.ai import TutorRequest
from app.services.ai import providers


def _request(**overrides) -> TutorRequest:
    payload = {
        "lessonTitle": "Candlesticks",
        "lang": "en",
        "messages": [{"role": "user", "content": "What is a doji?"}],
    }
    payload.update(overrides)
    return TutorRequest(**payload)


async def _gen(chunks):
    for c in chunks:
        yield c


async def _failing_gen():
    raise providers.ProviderError("boom")
    yield  # pragma: no cover — makes this an async generator


def test_system_prompt_english_mentions_lesson_and_examples():
    from app.services.ai import tutor

    prompt = tutor.build_system_prompt("Candlesticks", None, "en")
    assert "Candlesticks" in prompt
    assert "KSE-100" in prompt
    assert "Reply in English" in prompt


def test_system_prompt_urdu_and_context():
    from app.services.ai import tutor

    prompt = tutor.build_system_prompt("Candlesticks", "Doji section", "ur")
    assert "Doji section" in prompt
    assert "Urdu" in prompt


@pytest.mark.asyncio
async def test_stream_reply_uses_gemini_when_healthy(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _gen(["A", "B"]))
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _failing_gen())
    events = [e async for e in tutor.stream_reply(_request())]
    assert [e["text"] for e in events if e["type"] == "token"] == ["A", "B"]
    meta = events[-1]
    assert meta["type"] == "meta" and meta["provider"] == "gemini"


@pytest.mark.asyncio
async def test_stream_reply_falls_back_to_groq(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _failing_gen())
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _gen(["G"]))
    events = [e async for e in tutor.stream_reply(_request())]
    assert [e["text"] for e in events if e["type"] == "token"] == ["G"]
    assert events[-1]["provider"] == "groq"


@pytest.mark.asyncio
async def test_stream_reply_raises_when_all_fail(monkeypatch):
    from app.services.ai import tutor

    monkeypatch.setattr(providers, "stream_gemini", lambda m, transport=None: _failing_gen())
    monkeypatch.setattr(providers, "stream_groq", lambda m, transport=None: _failing_gen())
    with pytest.raises(providers.ProviderError):
        async for _ in tutor.stream_reply(_request()):
            pass


@pytest.mark.asyncio
async def test_mid_stream_failure_does_not_fall_back(monkeypatch):
    from app.services.ai import tutor

    async def _breaks_mid_stream(m, transport=None):
        yield "partial"
        raise providers.ProviderError("mid-stream")

    called = {"groq": False}

    def _groq(m, transport=None):
        called["groq"] = True
        return _gen(["nope"])

    monkeypatch.setattr(providers, "stream_gemini", _breaks_mid_stream)
    monkeypatch.setattr(providers, "stream_groq", _groq)
    received = []
    with pytest.raises(providers.ProviderError):
        async for e in tutor.stream_reply(_request()):
            received.append(e)
    assert [e["text"] for e in received] == ["partial"]
    assert called["groq"] is False  # never switched mid-stream


@pytest.mark.asyncio
async def test_check_quota_under_at_and_unlimited(monkeypatch):
    from app.repositories import ai_repo
    from app.services.ai import quota

    async def _used(conn, uid):
        return 9

    monkeypatch.setattr(ai_repo, "get_today_usage", _used)

    user = {"user_id": "u1", "features": {"ai_tutor_daily_limit": 10}}
    allowed, used, limit = await quota.check_quota(user)
    assert (allowed, used, limit) == (True, 9, 10)

    async def _at_limit(conn, uid):
        return 10

    monkeypatch.setattr(ai_repo, "get_today_usage", _at_limit)
    allowed, used, limit = await quota.check_quota(user)
    assert allowed is False

    unlimited = {"user_id": "u1", "features": {"ai_tutor_daily_limit": None}}
    allowed, used, limit = await quota.check_quota(unlimited)
    assert allowed is True and limit is None

    no_features = {"user_id": "u1", "features": {}}
    allowed, used, limit = await quota.check_quota(no_features)
    assert allowed is True and limit is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_tutor_service.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` for `app.services.ai.tutor`.

- [ ] **Step 3: Write quota.py**

Create `backend/src/app/services/ai/quota.py`:

```python
"""Daily AI-tutor quota: plan_features.ai_tutor_daily_limit vs ai_usage.

The limit arrives on the require_user result (features dict) — no extra DB
read. Only today's used-count is queried. limit None => unlimited.
"""
from __future__ import annotations

from typing import Any, Optional

from app.repositories import ai_repo
from app.repositories.base import connect


async def check_quota(user: dict[str, Any]) -> tuple[bool, int, Optional[int]]:
    limit = (user.get("features") or {}).get("ai_tutor_daily_limit")
    async with connect() as conn:
        used = await ai_repo.get_today_usage(conn, user["user_id"])
    if limit is None:
        return True, used, None
    return used < int(limit), used, int(limit)


async def usage_summary(user: dict[str, Any]) -> dict[str, Any]:
    _, used, limit = await check_quota(user)
    remaining = None if limit is None else max(0, limit - used)
    return {"used": used, "limit": limit, "remaining": remaining}
```

- [ ] **Step 4: Write tutor.py**

Create `backend/src/app/services/ai/tutor.py`:

```python
"""Tutor orchestration: system prompt, provider fallback, persistence.

Fallback contract: Gemini first; if it fails BEFORE any token was yielded,
retry transparently with Groq. Once a token has been yielded, a failure
propagates (the API layer ends the SSE stream with an error event) — we never
splice two providers' output into one reply.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.repositories import ai_repo
from app.repositories.base import begin, connect
from app.schemas.ai import TutorRequest
from app.services.ai import providers


def build_system_prompt(lesson_title: str, lesson_context: Optional[str], lang: str) -> str:
    is_urdu = lang == "ur"
    context = f' (currently in the "{lesson_context}" section)' if lesson_context else ""
    lang_rule = (
        "Reply entirely in Urdu, except stock symbols, app names, and market tickers."
        if is_urdu
        else "Reply in English."
    )
    return (
        "You are a friendly financial education tutor for NafaIQ, a Pakistan "
        f'Stock Exchange app. The user is currently reading a lesson about "{lesson_title}"'
        f"{context}. Keep answers concise (under 150 words), use simple language, "
        "and give Pakistan-specific examples where possible (use stocks like HBL, "
        "ENGRO, KSE-100). If asked about a topic unrelated to finance, politely "
        f"redirect. {lang_rule}"
    )


async def stream_reply(
    body: TutorRequest, *, transport: Any = None
) -> AsyncIterator[dict[str, Any]]:
    """Yield {"type":"token","text":...} events, then a final
    {"type":"meta","provider":...,"model":...}. Raises ProviderError if all
    providers fail before the first token, or on mid-stream failure."""
    system = build_system_prompt(body.lessonTitle, body.lessonContext, body.lang)
    oai_messages = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content} for m in body.messages
    ]
    attempts = [
        ("gemini", settings.ai_tutor_model_primary, providers.stream_gemini),
        ("groq", settings.ai_tutor_model_fallback, providers.stream_groq),
    ]
    last_err: Exception | None = None
    for name, model, fn in attempts:
        started = False
        try:
            async for delta in fn(oai_messages, transport=transport):
                started = True
                yield {"type": "token", "text": delta}
            yield {"type": "meta", "provider": name, "model": model}
            return
        except providers.ProviderError as e:
            if started:
                raise  # mid-stream: never switch providers
            last_err = e
            continue
    raise providers.ProviderError(f"all providers failed: {last_err}")


async def persist_exchange(
    user_id: str,
    question: str,
    reply: str,
    *,
    lesson_title: str,
    lang: str,
    provider: Optional[str],
    model: Optional[str],
) -> None:
    """One transaction: user turn + assistant turn + usage increment."""
    async with begin() as conn:
        await ai_repo.insert_message(
            conn, user_id, "user", question, lesson_title=lesson_title, lang=lang
        )
        await ai_repo.insert_message(
            conn, user_id, "assistant", reply,
            lesson_title=lesson_title, lang=lang, provider=provider, model=model,
        )
        await ai_repo.increment_usage(conn, user_id)


async def get_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 50))
    async with connect() as conn:
        return await ai_repo.recent_history(conn, user_id, limit)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_tutor_service.py -v`
Expected: 7 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/services/ai/tutor.py backend/src/app/services/ai/quota.py backend/tests/test_ai_tutor_service.py
git commit -m "feat(ai): tutor service with Gemini->Groq fallback and quota"
```

---

### Task 7: API router — SSE endpoint + history/usage + middleware + registration

**Files:**
- Create: `backend/src/app/api/ai.py`
- Modify: `backend/src/app/middleware/auth.py` (`USER_PATHS_PREFIXES`, ~line 18)
- Modify: `backend/src/app/main.py` (import + `include_router`, ~lines 13 & 158)
- Test: `backend/tests/test_ai_api.py`

**Interfaces:**
- Consumes: Task 3 `TutorRequest`; Task 6 `tutor` + `quota` services; `app.api.deps.require_user`; `providers.ProviderError`.
- Produces HTTP contract (spec §5):
  - `POST /api/ai/tutor` → SSE `data:` JSON events `{"type":"token","text"}`, `{"type":"done","usage":{"used","limit"}}`, `{"type":"error","code":"quota"|"provider","message"}`; HTTP 401 pre-stream when unauthenticated.
  - `GET /api/ai/tutor/history?limit=20` → `list[dict]` oldest-first.
  - `GET /api/ai/tutor/usage` → `{"used","limit","remaining"}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_api.py`:

```python
"""AI tutor endpoint tests over a minimal FastAPI app (router-only, DI-overridden
auth, monkeypatched services — no network, no DB)."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
    "features": {"ai_tutor_daily_limit": 10},
}

PAYLOAD = {
    "lessonTitle": "Candlesticks",
    "lang": "en",
    "messages": [{"role": "user", "content": "What is a doji?"}],
}


def _make_app() -> FastAPI:
    from app.api import ai as ai_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


async def _sse_events(client: httpx.AsyncClient, payload: dict) -> list[dict]:
    events = []
    async with client.stream("POST", "/api/ai/tutor", json=payload) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        async for line in res.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


@pytest.mark.asyncio
async def test_streams_tokens_then_done_and_persists(monkeypatch):
    from app.services.ai import quota, tutor

    async def _ok_quota(user):
        return True, 3, 10

    async def _fake_stream(body, transport=None):
        yield {"type": "token", "text": "Hello"}
        yield {"type": "token", "text": " trader"}
        yield {"type": "meta", "provider": "gemini", "model": "gemini-2.5-flash"}

    persisted = {}

    async def _fake_persist(user_id, question, reply, **kw):
        persisted.update({"user_id": user_id, "question": question, "reply": reply, **kw})

    monkeypatch.setattr(quota, "check_quota", _ok_quota)
    monkeypatch.setattr(tutor, "stream_reply", _fake_stream)
    monkeypatch.setattr(tutor, "persist_exchange", _fake_persist)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert tokens == ["Hello", " trader"]
    done = events[-1]
    assert done["type"] == "done"
    assert done["usage"] == {"used": 4, "limit": 10}
    assert persisted["user_id"] == FAKE_USER["user_id"]
    assert persisted["question"] == "What is a doji?"
    assert persisted["reply"] == "Hello trader"
    assert persisted["provider"] == "gemini"


@pytest.mark.asyncio
async def test_quota_exceeded_blocks_without_llm_call(monkeypatch):
    from app.services.ai import quota, tutor

    async def _blocked(user):
        return False, 10, 10

    called = {"stream": False}

    async def _fake_stream(body, transport=None):
        called["stream"] = True
        yield {"type": "token", "text": "x"}

    monkeypatch.setattr(quota, "check_quota", _blocked)
    monkeypatch.setattr(tutor, "stream_reply", _fake_stream)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    assert len(events) == 1
    assert events[0]["type"] == "error" and events[0]["code"] == "quota"
    assert called["stream"] is False


@pytest.mark.asyncio
async def test_provider_failure_emits_error_and_skips_persist(monkeypatch):
    from app.services.ai import providers, quota, tutor

    async def _ok_quota(user):
        return True, 0, 10

    async def _fail_stream(body, transport=None):
        raise providers.ProviderError("all providers failed")
        yield  # pragma: no cover

    persisted = {"called": False}

    async def _fake_persist(*a, **kw):
        persisted["called"] = True

    monkeypatch.setattr(quota, "check_quota", _ok_quota)
    monkeypatch.setattr(tutor, "stream_reply", _fail_stream)
    monkeypatch.setattr(tutor, "persist_exchange", _fake_persist)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        events = await _sse_events(client, PAYLOAD)

    assert events[-1]["type"] == "error" and events[-1]["code"] == "provider"
    assert persisted["called"] is False


@pytest.mark.asyncio
async def test_history_and_usage_endpoints(monkeypatch):
    from app.services.ai import quota, tutor

    async def _fake_history(user_id, limit=20):
        return [{"id": 1, "role": "user", "content": "q", "lesson_title": None, "lang": "en", "created_at": "2026-07-12"}]

    async def _fake_summary(user):
        return {"used": 2, "limit": 10, "remaining": 8}

    monkeypatch.setattr(tutor, "get_history", _fake_history)
    monkeypatch.setattr(quota, "usage_summary", _fake_summary)

    transport = httpx.ASGITransport(app=_make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        hist = await client.get("/api/ai/tutor/history?limit=5")
        usage = await client.get("/api/ai/tutor/usage")

    assert hist.status_code == 200 and hist.json()[0]["content"] == "q"
    assert usage.json() == {"used": 2, "limit": 10, "remaining": 8}


def test_ai_path_is_user_authenticated():
    from app.middleware.auth import _is_user_path

    assert _is_user_path("/api/ai/tutor") is True
    assert _is_user_path("/api/ai/tutor/history") is True
    assert _is_user_path("/api/aibogus") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'ai'` (router missing) and the middleware test failing (`/api/ai/tutor` not a user path).

- [ ] **Step 3: Write the router**

Create `backend/src/app/api/ai.py`:

```python
"""AI tutor routes: SSE chat stream + history + usage (thin over services.ai).

Auth: require_user (Supabase JWT). Quota is checked BEFORE any provider call;
usage increments only after a fully successful reply, so failed generations
never burn quota. If the client disconnects mid-stream, the generator is
cancelled and nothing is persisted (by design)."""
from __future__ import annotations

import json
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import require_user
from app.schemas.ai import TutorRequest
from app.services.ai import quota, tutor
from app.services.ai.providers import ProviderError

router = APIRouter(tags=["ai"])

_QUOTA_MSG = {
    "en": "You've reached today's AI tutor limit. Upgrade your plan or come back tomorrow.",
    "ur": "آپ آج کی اے آئی ٹیوٹر حد تک پہنچ گئے ہیں۔ اپنا پلان اپ گریڈ کریں یا کل دوبارہ آئیں۔",
}
_PROVIDER_MSG = {
    "en": "Sorry, I couldn't reach the AI tutor just now. Please try again.",
    "ur": "معذرت، ابھی اے آئی ٹیوٹر تک رسائی نہیں ہو سکی۔ براہ کرم دوبارہ کوشش کریں۔",
}


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ai/tutor")
async def tutor_stream(body: TutorRequest, user: Annotated[dict, Depends(require_user)]):
    allowed, used, limit = await quota.check_quota(user)

    async def events() -> AsyncIterator[str]:
        if not allowed:
            yield _sse({"type": "error", "code": "quota", "message": _QUOTA_MSG[body.lang]})
            return
        parts: list[str] = []
        provider: str | None = None
        model: str | None = None
        try:
            async for ev in tutor.stream_reply(body):
                if ev["type"] == "token":
                    parts.append(ev["text"])
                    yield _sse(ev)
                elif ev["type"] == "meta":
                    provider, model = ev["provider"], ev["model"]
        except ProviderError:
            yield _sse({"type": "error", "code": "provider", "message": _PROVIDER_MSG[body.lang]})
            return
        await tutor.persist_exchange(
            user["user_id"],
            body.messages[-1].content,
            "".join(parts),
            lesson_title=body.lessonTitle,
            lang=body.lang,
            provider=provider,
            model=model,
        )
        yield _sse({"type": "done", "usage": {"used": used + 1, "limit": limit}})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/ai/tutor/history")
async def tutor_history(user: Annotated[dict, Depends(require_user)], limit: int = 20):
    return await tutor.get_history(user["user_id"], limit)


@router.get("/ai/tutor/usage")
async def tutor_usage(user: Annotated[dict, Depends(require_user)]):
    return await quota.usage_summary(user)
```

- [ ] **Step 4: Register the path prefix and router**

In `backend/src/app/middleware/auth.py`, add to `USER_PATHS_PREFIXES` (keep alphabetical-ish grouping):

```python
USER_PATHS_PREFIXES = (
    "/api/ai",
    "/api/portfolio",
    "/api/profile",
    "/api/watchlist",
    "/api/notifications",
    "/api/alerts",
    "/api/finance",
    "/api/finance-extended",
)
```

In `backend/src/app/main.py`: add `ai,` to the `from app.api import (...)` block and append after the last `include_router` line:

```python
app.include_router(ai.router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_api.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Run the whole backend suite (no regressions)**

Run: `cd backend && pytest tests/ -v`
Expected: all previous tests still pass (plus the new ones; `fx_rates` skip is pre-existing).

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/api/ai.py backend/src/app/middleware/auth.py backend/src/app/main.py backend/tests/test_ai_api.py
git commit -m "feat(ai): SSE tutor endpoint with quota, history and usage routes"
```

---

### Task 8: Web SSE client — `tutor-client.ts` + minimal vitest

**Files:**
- Create: `frontend/packages/web/src/lib/ai/tutor-client.ts`
- Create: `frontend/packages/web/src/lib/ai/tutor-client.test.ts`
- Modify: `frontend/packages/web/package.json` (add `vitest` devDep + `test` script)

**Interfaces:**
- Consumes: `API_BASE_URL`/`apiUrl` from `@/lib/api`; supabase client at `@/integrations/supabase/client` (session token — same pattern as `psx/client.ts`).
- Produces (consumed by Task 9):
  - `type TutorEvent = { type: "token"; text: string } | { type: "done"; usage: { used: number; limit: number | null } } | { type: "error"; code: "quota" | "provider" | "auth"; message: string }`
  - `interface TutorPayload { lessonTitle: string; lessonContext?: string; lang: "en" | "ur"; messages: { role: "user" | "assistant"; content: string }[] }`
  - `parseSseBuffer(buffer: string): { events: TutorEvent[]; rest: string }` (pure)
  - `streamTutor(payload: TutorPayload, handlers: { onToken(text: string): void; onDone(usage: { used: number; limit: number | null }): void; onError(code: "quota" | "provider" | "auth", message: string): void }, signal?: AbortSignal): Promise<void>`
  - `fetchTutorHistory(limit?: number): Promise<{ role: "user" | "assistant"; content: string }[]>`
  - `fetchTutorUsage(): Promise<{ used: number; limit: number | null; remaining: number | null }>`

- [ ] **Step 1: Add vitest**

```bash
cd frontend/packages/web && pnpm add -D vitest
```

Then add to `package.json` scripts: `"test": "vitest run"`. No config file needed — the tests are pure TS running in node.

- [ ] **Step 2: Write the failing parser test**

Create `frontend/packages/web/src/lib/ai/tutor-client.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseSseBuffer, type TutorEvent } from "./tutor-client";

describe("parseSseBuffer", () => {
  it("parses complete data blocks and keeps the partial tail", () => {
    const buffer =
      'data: {"type":"token","text":"Hello"}\n\n' +
      'data: {"type":"token","text":" PSX"}\n\n' +
      'data: {"type":"do'; // incomplete block
    const { events, rest } = parseSseBuffer(buffer);
    expect(events).toEqual<TutorEvent[]>([
      { type: "token", text: "Hello" },
      { type: "token", text: " PSX" },
    ]);
    expect(rest).toBe('data: {"type":"do');
  });

  it("parses done and error events", () => {
    const buffer =
      'data: {"type":"done","usage":{"used":4,"limit":10}}\n\n' +
      'data: {"type":"error","code":"quota","message":"limit"}\n\n';
    const { events, rest } = parseSseBuffer(buffer);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "done", usage: { used: 4, limit: 10 } });
    expect(events[1]).toEqual({ type: "error", code: "quota", message: "limit" });
    expect(rest).toBe("");
  });

  it("ignores non-data lines and malformed JSON", () => {
    const buffer = ": keep-alive\n\ndata: {broken\n\ndata: {\"type\":\"token\",\"text\":\"ok\"}\n\n";
    const { events } = parseSseBuffer(buffer);
    expect(events).toEqual([{ type: "token", text: "ok" }]);
  });

  it("returns everything as rest when no complete block", () => {
    const { events, rest } = parseSseBuffer("data: {\"type\":\"token\"");
    expect(events).toEqual([]);
    expect(rest).toBe("data: {\"type\":\"token\"");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend/packages/web && npx vitest run src/lib/ai/tutor-client.test.ts`
Expected: FAIL — cannot resolve `./tutor-client`.

- [ ] **Step 4: Write the client**

Create `frontend/packages/web/src/lib/ai/tutor-client.ts`:

```ts
// SSE client for the FastAPI AI tutor (POST /api/ai/tutor).
// Auth mirrors psx/client.ts user* helpers: Supabase session JWT as bearer.

import { apiUrl } from "@/lib/api";

export type TutorEvent =
  | { type: "token"; text: string }
  | { type: "done"; usage: { used: number; limit: number | null } }
  | { type: "error"; code: "quota" | "provider" | "auth"; message: string };

export interface TutorPayload {
  lessonTitle: string;
  lessonContext?: string;
  lang: "en" | "ur";
  messages: { role: "user" | "assistant"; content: string }[];
}

export interface TutorHandlers {
  onToken(text: string): void;
  onDone(usage: { used: number; limit: number | null }): void;
  onError(code: "quota" | "provider" | "auth", message: string): void;
}

/** Pure SSE parser: extracts complete `data: {json}` blocks, returns the
 * unterminated tail as `rest` for the next chunk. Exported for tests. */
export function parseSseBuffer(buffer: string): { events: TutorEvent[]; rest: string } {
  const events: TutorEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    for (const line of block.split("\n")) {
      if (!line.startsWith("data:")) continue;
      try {
        events.push(JSON.parse(line.slice(5).trim()) as TutorEvent);
      } catch {
        // tolerate keep-alives / malformed lines
      }
    }
  }
  return { events, rest };
}

async function getAccessToken(): Promise<string | null> {
  const { supabase } = await import("@/integrations/supabase/client");
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function streamTutor(
  payload: TutorPayload,
  handlers: TutorHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = await getAccessToken();
  if (!token) {
    handlers.onError("auth", "Not signed in");
    return;
  }
  let res: Response;
  try {
    res = await fetch(apiUrl("/api/ai/tutor"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (e) {
    if (signal?.aborted) return; // user closed the panel — not an error
    handlers.onError("provider", String(e));
    return;
  }
  if (res.status === 401) {
    handlers.onError("auth", "Session expired");
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError("provider", `HTTP ${res.status}`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer(buffer);
      buffer = parsed.rest;
      for (const ev of parsed.events) {
        if (ev.type === "token") handlers.onToken(ev.text);
        else if (ev.type === "done") handlers.onDone(ev.usage);
        else handlers.onError(ev.code, ev.message);
      }
    }
  } catch (e) {
    if (!signal?.aborted) handlers.onError("provider", String(e));
  }
}

async function authedGet<T>(path: string): Promise<T> {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(apiUrl(path), { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchTutorHistory(
  limit = 12,
): Promise<{ role: "user" | "assistant"; content: string }[]> {
  return authedGet(`/api/ai/tutor/history?limit=${limit}`);
}

export function fetchTutorUsage(): Promise<{
  used: number;
  limit: number | null;
  remaining: number | null;
}> {
  return authedGet("/api/ai/tutor/usage");
}
```

- [ ] **Step 5: Run tests + typecheck**

Run: `cd frontend/packages/web && npx vitest run src/lib/ai/tutor-client.test.ts && npx tsc --noEmit`
Expected: 4 PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/web/src/lib/ai/tutor-client.ts frontend/packages/web/src/lib/ai/tutor-client.test.ts frontend/packages/web/package.json pnpm-lock.yaml
git commit -m "feat(web): SSE tutor client with parser tests (adds vitest)"
```

---

### Task 9: Shared hook + rewire both panels + retire `askTutor`

**Files:**
- Create: `frontend/packages/web/src/hooks/learn/use-tutor-chat.ts`
- Rewrite: `frontend/packages/web/src/features/learn/hub/components/HubChatPanel.tsx`
- Rewrite: `frontend/packages/web/src/features/learn/lesson/components/ChatPanel.tsx`
- Delete: `frontend/packages/web/src/features/learn/ai-functions.ts`

**Interfaces:**
- Consumes: Task 8 `streamTutor`, `fetchTutorHistory`, `TutorPayload`; `useLang` from `@/hooks/use-lang`; supabase client.
- Produces: `useTutorChat(opts: { lessonTitle: string; lessonContext?: string; greeting: string; hydrate?: boolean }) -> { messages: {role,content}[]; loading: boolean; quotaExceeded: boolean; signedOut: boolean; send(text: string): void }`.

- [ ] **Step 1: Write the hook**

Create `frontend/packages/web/src/hooks/learn/use-tutor-chat.ts`:

```ts
// Shared AI-tutor chat state for HubChatPanel and lesson ChatPanel.
// Streams tokens into the last assistant bubble; handles quota, auth, abort.

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTutorHistory, streamTutor } from "@/lib/ai/tutor-client";
import { useLang } from "@/hooks/use-lang";

export interface TutorChatMsg {
  role: "user" | "assistant";
  content: string;
}

export interface UseTutorChatOptions {
  lessonTitle: string;
  lessonContext?: string;
  greeting: string;
  /** Load recent server-side history on mount (hub panel). */
  hydrate?: boolean;
}

export function useTutorChat(opts: UseTutorChatOptions) {
  const { lang } = useLang();
  const [messages, setMessages] = useState<TutorChatMsg[]>([
    { role: "assistant", content: opts.greeting },
  ]);
  const [loading, setLoading] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Refresh the greeting when the language toggles (pre-existing behavior).
  useEffect(() => {
    setMessages((current) =>
      current.length === 1 && current[0]?.role === "assistant"
        ? [{ role: "assistant", content: opts.greeting }]
        : current,
    );
  }, [opts.greeting]);

  // Signed-in check (+ optional history hydration) on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { supabase } = await import("@/integrations/supabase/client");
      const { data } = await supabase.auth.getSession();
      if (cancelled) return;
      if (!data.session) {
        setSignedOut(true);
        return;
      }
      if (opts.hydrate) {
        try {
          const history = await fetchTutorHistory(12);
          if (!cancelled && history.length > 0) {
            setMessages([
              { role: "assistant", content: opts.greeting },
              ...history.map((h) => ({ role: h.role, content: h.content })),
            ]);
          }
        } catch {
          // hydration is best-effort; keep the greeting
        }
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading || quotaExceeded || signedOut) return;
      setLoading(true);
      let history: TutorChatMsg[] = [];
      setMessages((current) => {
        history = [...current, { role: "user", content: trimmed }];
        // Empty assistant bubble that streaming tokens append into.
        return [...history, { role: "assistant", content: "" }];
      });
      const controller = new AbortController();
      abortRef.current = controller;

      const appendToLast = (delta: string) =>
        setMessages((current) => {
          const next = [...current];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { role: "assistant", content: last.content + delta };
          }
          return next;
        });

      const replaceLast = (content: string) =>
        setMessages((current) => {
          const next = [...current];
          next[next.length - 1] = { role: "assistant", content };
          return next;
        });

      void streamTutor(
        {
          lessonTitle: opts.lessonTitle,
          lessonContext: opts.lessonContext,
          lang,
          // last 12 turns, excluding greeting-only context bloat is fine —
          // the backend caps at 12 messages anyway
          messages: history.slice(-12),
        },
        {
          onToken: appendToLast,
          onDone: () => setLoading(false),
          onError: (code, message) => {
            if (code === "quota") {
              setQuotaExceeded(true);
              replaceLast(message);
            } else if (code === "auth") {
              setSignedOut(true);
              replaceLast(message);
            } else {
              replaceLast(message);
            }
            setLoading(false);
          },
        },
        controller.signal,
      );
    },
    [loading, quotaExceeded, signedOut, lang, opts.lessonTitle, opts.lessonContext],
  );

  return { messages, loading, quotaExceeded, signedOut, send };
}
```

- [ ] **Step 2: Rewrite HubChatPanel**

Replace the full contents of `frontend/packages/web/src/features/learn/hub/components/HubChatPanel.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useTutorChat } from "@/hooks/learn/use-tutor-chat";
import { HUB_PRESETS } from "@/features/learn/hub/hub.data";

export function HubChatPanel() {
  const { t } = useLang();
  const { messages, loading, quotaExceeded, signedOut, send } = useTutorChat({
    lessonTitle: "PSX investing basics",
    greeting: t(
      "Hi! I'm your NafaIQ tutor. Ask me anything about PSX investing, terms, or strategies.",
    ),
    hydrate: true,
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m, i) => (
          <div key={i} className={cn("max-w-[88%]", m.role === "user" ? "ml-auto" : "")}>
            <div
              className={cn(
                "px-3 py-2 text-sm leading-relaxed",
                m.role === "user"
                  ? "rounded-[12px] rounded-br-none bg-bull text-bull-foreground"
                  : "rounded-[12px] rounded-bl-none bg-elevated text-text-primary",
              )}
            >
              {m.content}
            </div>
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {HUB_PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => submit(p)}
                className="block w-full rounded-full border border-border px-3 py-1.5 text-left text-[11px] text-text-secondary hover:border-bull hover:text-bull"
              >
                {t(p)}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Sparkles className="h-3.5 w-3.5 animate-pulse text-bull" /> {t("Thinking…")}
          </div>
        )}

        {quotaExceeded && (
          <div className="rounded-[8px] border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            {t("Daily tutor limit reached — upgrade your plan or come back tomorrow.")}
          </div>
        )}
      </div>

      {signedOut ? (
        <div className="border-t border-border p-3 text-center">
          <Link
            to="/auth"
            className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-4 py-2 text-xs font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Sign in to chat with your tutor")}
          </Link>
        </div>
      ) : (
        <div className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(input)}
            placeholder={t("Ask about investing…")}
            disabled={quotaExceeded}
            className="flex-1 rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            onClick={() => submit(input)}
            disabled={loading || quotaExceeded}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-bull text-bull-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Rewrite lesson ChatPanel**

Replace the full contents of `frontend/packages/web/src/features/learn/lesson/components/ChatPanel.tsx` (note: `Typewriter` is no longer needed — real streaming replaces the fake typewriter; header and presets keep their existing look):

```tsx
import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Send, Sparkles } from "lucide-react";
import { AiGlyph } from "@/components/icons/AiGlyph";
import { type LessonContent } from "@/lib/learn/data";
import { useTutorChat } from "@/hooks/learn/use-tutor-chat";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

export function ChatPanel({
  lesson,
  activeSection,
  embedded,
}: {
  lesson: LessonContent;
  activeSection?: string;
  embedded?: boolean;
}) {
  const { t } = useLang();
  const sectionHeading = lesson.sections.find((s) => s.id === activeSection)?.heading;
  const { messages, loading, quotaExceeded, signedOut, send } = useTutorChat({
    lessonTitle: lesson.title,
    lessonContext: sectionHeading,
    greeting: `${t("Hi! I'm here to help you understand")} ${t(lesson.title)}. ${t("What would you like to know?")}`,
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut;

  return (
    <div
      className={cn(
        "flex h-full flex-col overflow-hidden rounded-card border border-border bg-surface",
        embedded && "rounded-none border-0",
      )}
    >
      <div className="border-b border-border p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-bull/15 text-bull">
            <AiGlyph className="h-3.5 w-3.5" />
          </span>
          {t("AI Tutor")}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="text-[11px] text-text-secondary">
            {t("Ask anything about this lesson")}
          </span>
          <span className="rounded-full bg-ai/15 px-1.5 py-0.5 text-[9px] font-semibold text-ai">
            {t("Powered by AI")}
          </span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m, i) => (
          <div key={i} className={cn("max-w-[88%]", m.role === "user" ? "ml-auto" : "")}>
            <div
              className={cn(
                "px-3 py-2 text-sm leading-relaxed",
                m.role === "user"
                  ? "rounded-card rounded-br-none bg-bull text-bull-foreground"
                  : "rounded-card rounded-bl-none bg-elevated text-text-primary",
              )}
            >
              {m.content}
            </div>
            {i === 0 && <div className="mt-1 text-[10px] text-text-muted">{t("just now")}</div>}
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {lesson.presets.map((p) => (
              <button
                key={p}
                onClick={() => submit(p)}
                className="block w-full rounded-full border border-border px-3 py-1.5 text-left text-[11px] text-text-secondary hover:border-bull hover:text-bull"
              >
                {t(p)}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Sparkles className="h-3.5 w-3.5 animate-pulse text-bull" /> {t("Thinking…")}
          </div>
        )}

        {quotaExceeded && (
          <div className="rounded-btn border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            {t("Daily tutor limit reached — upgrade your plan or come back tomorrow.")}
          </div>
        )}
      </div>

      {signedOut ? (
        <div className="border-t border-border p-3 text-center">
          <Link
            to="/auth"
            className="inline-flex items-center gap-1.5 rounded-btn bg-bull px-4 py-2 text-xs font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Sign in to chat with your tutor")}
          </Link>
        </div>
      ) : (
        <div className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(input)}
            placeholder={t("Ask about this lesson…")}
            disabled={quotaExceeded}
            className="flex-1 rounded-btn border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            onClick={() => submit(input)}
            disabled={loading || quotaExceeded}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-btn bg-bull text-bull-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Retire the server function**

```bash
rm frontend/packages/web/src/features/learn/ai-functions.ts
```

Then verify nothing references it:

Run: `grep -rn "ai-functions\|askTutor" frontend/packages/web/src`
Expected: no matches.

- [ ] **Step 5: Typecheck, lint, tests**

Run: `cd frontend/packages/web && npx tsc --noEmit && npx eslint . && npx vitest run`
Expected: all clean / PASS. (If `Typewriter` is now unused anywhere, leave the shared component in place — other screens may use it; only its import was removed here.)

- [ ] **Step 6: Commit**

```bash
git add -A frontend/packages/web/src
git commit -m "feat(web): stream AI tutor via FastAPI SSE; retire Lovable askTutor"
```

---

### Task 10: End-to-end verification (manual, evidence required)

**Files:** none (verification only). Use the `superpowers:verification-before-completion` skill before claiming done.

- [ ] **Step 1: Configure keys and start both servers**

Add real `GEMINI_API_KEY` + `GROQ_API_KEY` to `backend/.env`, then:

```bash
cd backend && python -m uvicorn src.app.main:app --reload --port 8000
# separate terminal:
pnpm run dev
```

- [ ] **Step 2: Verify streaming happy path**

Sign in on the web app → `/learn` → open the AI Tutor sheet → ask "What is KSE-100?".
Expected: reply streams in token-by-token (visibly incremental, not one blob); content is finance-related.

- [ ] **Step 3: Verify persistence**

In Supabase Dashboard SQL Editor:

```sql
SELECT role, left(content, 40), provider, model FROM ai_chat_history ORDER BY created_at DESC LIMIT 4;
SELECT * FROM ai_usage ORDER BY updated_at DESC LIMIT 3;
```

Expected: one `user` + one `assistant` row per exchange (assistant has `provider`/`model`); `ai_usage.message_count` matches the number of exchanges today.

- [ ] **Step 4: Verify quota block**

Simulate a burned quota for your test user (Free = 10):

```sql
UPDATE ai_usage SET message_count = 10
WHERE user_id = '<your-user-id>' AND usage_date = (now() AT TIME ZONE 'utc')::date;
```

Ask another question. Expected: friendly limit message + warning banner + disabled input; `message_count` stays 10 (no increment). Reset afterwards:

```sql
UPDATE ai_usage SET message_count = 2
WHERE user_id = '<your-user-id>' AND usage_date = (now() AT TIME ZONE 'utc')::date;
```

- [ ] **Step 5: Verify fallback + signed-out**

- Temporarily set `GEMINI_API_KEY=` (empty) in `backend/.env`, restart backend, ask a question. Expected: reply still streams (Groq); `ai_chat_history.provider = 'groq'` for the new row. Restore the key.
- Sign out → open the tutor sheet. Expected: "Sign in to chat with your tutor" CTA instead of the input; no network call to `/api/ai/tutor`.

- [ ] **Step 6: Verify Urdu + lesson panel**

Switch app language to Urdu, ask a question. Expected: Urdu reply. Open a lesson → lesson ChatPanel → ask about the lesson. Expected: streams the same way with the lesson title in context.

- [ ] **Step 7: Final suite + update recall**

```bash
cd backend && pytest tests/ -v
cd frontend/packages/web && npx tsc --noEmit && npx eslint . && npx vitest run
```

Expected: all pass. Then update `recall/progress.md` Phase 6: mark the Tutor slice done (tables `ai_chat_history`/`ai_usage` created; Market Brief/Reports still pending) and commit:

```bash
git add recall/progress.md
git commit -m "docs(recall): mark Phase 6 tutor slice complete"
```

---

## Deviations from spec (intentional, minor)

- **No `db/models/ai.py`:** spec §7 listed ORM models, but the repository layer convention (`notifications_repo`, `alerts/*`) is raw SQL via `text()` — following the codebase pattern; the migration is the schema's source of truth.
- **Token counts not tracked in v1:** OpenAI-compat streaming chunks don't reliably carry usage data; columns exist (nullable / default 0) and `increment_usage` accepts counts for later wiring.
- **Client abort skips persistence:** if the user closes mid-stream, the generator is cancelled — no history row, no quota burn (favourable to the user, simplest correct behavior).
- **Web component tests:** the web package had zero test infrastructure; a minimal vitest setup covers the pure SSE parser, and UI states are verified manually in Task 10 (adding a full DOM-testing harness was out of scope per "don't touch unrelated settings").
