# LearnHub AI Tutor — Phase 6 (free provider + streaming + history + quota)

**Date:** 2026-07-12
**Author:** Usman (branch `usman`)
**Status:** Approved design — ready for implementation plan
**Roadmap:** `recall/progress.md` Phase 6 (AI Features), partial — Tutor slice only

---

## 1. Problem & goal

The LearnHub **AI Tutor** chat UI is already built and already calls a real LLM
(`google/gemini-3-flash-preview`) — but **through the Lovable AI Gateway**
(`ai.gateway.lovable.dev`, `LOVABLE_API_KEY`), which is a credit-limited paid
proxy (note the current `402 out of credits` handling in
`frontend/packages/web/src/features/learn/ai-functions.ts`).

**Goal:** move the tutor onto a **direct free provider** (Google Gemini primary,
Groq fallback) served from the **Python FastAPI backend**, with **SSE streaming**,
**per-user daily quota** (via the existing `plan_features.ai_tutor_daily_limit`),
and **persisted chat history + usage** in Supabase — logged-in users only.
This removes the Lovable dependency and delivers the Tutor slice of Phase 6.

### Non-goals (deferred, not dropped)
- **Mobile** (`frontend/packages/mobile` — Tayyab's package/branch): repoint its
  `ask-tutor` edge function / client to the new endpoint later. Out of scope here.
- **Rest of Phase 6:** `ai_reports` table, Market Brief / Stock Analysis /
  Portfolio Report LLM calls.
- **Voice input** for the tutor — a separate future spec.
- Any change to unrelated UI, deployment/infra, or mobile settings.

---

## 2. Current state (as-found)

| Piece | Location | Notes |
|---|---|---|
| Chat UI | `frontend/packages/web/src/features/learn/hub/components/HubChatPanel.tsx` | Non-streaming; calls `askTutor` server fn; renders messages, presets, "Thinking…" |
| Launcher | `frontend/packages/web/src/features/learn/hub/LearnHub.tsx` | Floating AI Tutor button + chat sheet |
| Web LLM call | `frontend/packages/web/src/features/learn/ai-functions.ts` | TanStack `createServerFn` → Lovable gateway. **To be retired.** |
| User-auth HTTP pattern | `frontend/packages/web/src/lib/psx/client.ts` | `userGet/userPost` send Supabase `session.access_token` as bearer to FastAPI |
| Backend auth | `backend/src/app/services/auth.py` + `app/api/deps.py::require_user` | Validates Supabase JWT (JWKS or HS256) → `{user_id, email, plan, features}` |
| Plan limits | `backend/database/migrations/20260711000000_role_and_plans.sql` | `plan_features.ai_tutor_daily_limit` already exists. Plans: **Free / Pro / Premium** |
| Layering | `db/models → repositories → services → api` | e.g. `api/notifications.py` is a thin router over `services.notifications` |

**Key consequence:** the only secret the web server function protected was
`LOVABLE_API_KEY`. Once LLM keys live in FastAPI, the browser can call the backend
**directly** with the Supabase JWT — exactly as it already does for portfolio,
alerts, and zakat.

---

## 3. Decisions (locked)

1. **Architecture:** centralize all tutor LLM logic in **FastAPI**. One endpoint;
   web is a direct client. (Mobile deferred.)
2. **Transport:** browser → `POST /api/ai/tutor` **directly**, reading an **SSE**
   stream. Retire `ai-functions.ts::askTutor`.
3. **Providers:** **Gemini** primary, **Groq** fallback (both OpenAI-compatible).
4. **Keys:** backend env only — `GEMINI_API_KEY`, `GROQ_API_KEY` (Railway backend
   env vars). Never shipped to any client bundle.
5. **Access:** logged-in only, via `Depends(require_user)`.
6. **Quota:** per-plan daily message cap via `plan_features.ai_tutor_daily_limit`.
   **Free = 10/day, Pro = 100/day, Premium = unlimited (NULL).** Only change vs
   current seed: **Pro NULL → 100** (Free already 10, Premium already NULL).
   `NULL` = unlimited. Resets at **midnight UTC** (`usage_date` is a UTC date).
7. **Persistence:** `ai_chat_history` + `ai_usage` in Supabase (names per Phase 6).
8. **Prompt economy:** never send full lesson bodies. Each request carries only:
   current **lesson title**, an optional **short lesson context** (≤ ~500 chars),
   the **recent chat history** (last ≤ 12 turns), and the **user question**.
9. **Streaming UX** handles: quota-exceeded, 401 unauthenticated, provider failure,
   and client abort — all gracefully and bilingually (EN/UR).

---

## 4. Providers & fallback

| Role | Provider | Endpoint (OpenAI-compatible `/chat/completions`) | Model (config default) |
|---|---|---|---|
| Primary | Google Gemini (free) | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.5-flash` |
| Fallback | Groq (free) | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.3-70b-versatile` |

**Fallback rule:** attempt Gemini with `stream:true`. If it fails to *open* the
stream (HTTP 429/402/5xx, connection error, or timeout) **before any token is
forwarded to the client**, transparently retry with Groq. **Once tokens have been
sent to the browser, do not switch** — finish or end with a graceful error event.

Model names, endpoints, and timeouts are configurable in `config.py` (sane
defaults above), so a future model bump is a config change.

---

## 5. API contract

### `POST /api/ai/tutor` — streaming chat (SSE)
- **Auth:** `Depends(require_user)`.
- **Request body** (`schemas/ai.py::TutorRequest`):
  ```jsonc
  {
    "lessonTitle": "PSX investing basics",   // required, 1..200
    "lessonContext": "short blurb…",          // optional, <= 500 chars
    "lang": "en",                              // "en" | "ur", optional (default en)
    "messages": [                              // 1..12 recent turns
      { "role": "user", "content": "What is a candlestick?" }
    ]
  }
  ```
- **Response:** `text/event-stream`. Event payloads (each `data:` line is JSON):
  - `{ "type": "token", "text": "…" }` — incremental assistant text
  - `{ "type": "done", "usage": { "used": 3, "limit": 10 } }` — final, after persist
  - `{ "type": "error", "code": "quota"|"provider"|"auth", "message": "…" }`
- **Pre-stream checks (in order):**
  1. `require_user` fails → **HTTP 401** (no stream) → frontend shows sign-in prompt.
  2. Quota exceeded → single SSE `error` event `code:"quota"` (HTTP 200 stream),
     friendly bilingual message, **no LLM call, no history write, no usage increment**.
- **On success:** stream tokens; when the provider stream completes, persist the
  user message + assistant reply to `ai_chat_history` and upsert `ai_usage`
  (`message_count += 1`, add token counts when available), then emit `done`.
- **On provider failure after fallback:** emit `error` `code:"provider"`; **do not**
  persist the assistant message; **do not** increment usage.

### `GET /api/ai/tutor/history?limit=20` — restore recent conversation
- `Depends(require_user)`. Returns the user's most recent messages (newest-last),
  capped (default 20, max 50), for hydrating the panel on open.

### `GET /api/ai/tutor/usage` — today's usage vs limit
- `Depends(require_user)`. Returns `{ "used": int, "limit": int|null, "remaining": int|null }`
  (`limit: null` ⇒ unlimited). Drives the "X of N left today" hint.

---

## 6. Data model (new migration)

New file: `backend/database/migrations/20260712000000_ai_tutor_history_usage.sql`.
Applied via Supabase Dashboard SQL Editor (per AGENTS.md). RLS enabled; owner-only.

### `ai_chat_history`
| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` GENERATED ALWAYS AS IDENTITY PK | |
| `user_id` | `uuid NOT NULL` | `REFERENCES auth.users(id) ON DELETE CASCADE` |
| `role` | `text NOT NULL` | `CHECK (role IN ('user','assistant'))` |
| `content` | `text NOT NULL` | |
| `lesson_title` | `text` | nullable |
| `lang` | `text` | nullable, `'en'|'ur'` |
| `provider` | `text` | nullable — `'gemini'|'groq'` (assistant rows) |
| `model` | `text` | nullable |
| `tokens_in` | `int` | nullable |
| `tokens_out` | `int` | nullable |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

- Index: `idx_ai_chat_history_user_created (user_id, created_at DESC)`.
- **RLS:** enable; policy `USING (auth.uid() = user_id)` for `SELECT`; inserts are
  performed server-side with the service-role key (bypasses RLS). Grant `SELECT`
  to `authenticated`.

### `ai_usage`
| Column | Type | Notes |
|---|---|---|
| `user_id` | `uuid NOT NULL` | `REFERENCES auth.users(id) ON DELETE CASCADE` |
| `usage_date` | `date NOT NULL` | UTC date; quota window |
| `message_count` | `int NOT NULL DEFAULT 0` | |
| `tokens_in` | `int NOT NULL DEFAULT 0` | |
| `tokens_out` | `int NOT NULL DEFAULT 0` | |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | |

- PK: `(user_id, usage_date)` — O(1) daily lookup; increment via upsert
  (`ON CONFLICT (user_id, usage_date) DO UPDATE SET message_count = ai_usage.message_count + 1, …`).
- **RLS:** enable; owner-only `SELECT`; writes server-side via service role.

### `plan_features` seed update
- In the same migration (or a companion), set **Pro `ai_tutor_daily_limit` = 100**
  via the existing upsert pattern. Free (10) and Premium (NULL) unchanged.
- Regenerate `frontend/packages/web/src/integrations/supabase/types.ts` after apply
  (command in AGENTS.md) so the two new tables are typed.

---

## 7. Backend structure (layered, mirrors existing conventions)

```
db/models/ai.py            AiChatHistory, AiUsage (SQLAlchemy models, reflect/base)
schemas/ai.py              TutorMessage, TutorRequest, TutorUsage, HistoryItem
repositories/ai_repo.py    insert_message, recent_history, get_today_usage,
                           increment_usage  (Supabase REST or SQLAlchemy Core,
                           following how notifications/alerts repos are written)
services/ai/__init__.py
services/ai/providers.py   async httpx SSE clients: stream_gemini(), stream_groq();
                           parse OpenAI-style `data:` chunks → yield text deltas
services/ai/tutor.py       build_system_prompt(lang, lessonTitle, lessonContext);
                           stream_reply(): try Gemini → Groq; yields text; returns
                           final (provider, model, tokens) for persistence
services/ai/quota.py       check_quota(user) -> (allowed, used, limit);
                           record_usage(user_id, tokens_in, tokens_out)
api/ai.py                  APIRouter: POST /api/ai/tutor (StreamingResponse,
                           media_type="text/event-stream"), GET history, GET usage
config.py                  + gemini_api_key, groq_api_key,
                           ai_tutor_model_primary, ai_tutor_model_fallback,
                           ai_tutor_request_timeout_s
main.py                    include ai router (public-exempt list unchanged — tutor
                           is user-authed, not token-authed)
```

**System prompt** (ported from current `ai-functions.ts`, unchanged in spirit):
friendly PSX financial-education tutor; concise (< 150 words); Pakistan-specific
examples (HBL, ENGRO, KSE-100); politely redirect off-topic; reply fully in Urdu
when `lang == 'ur'` (keep tickers/app names Latin). Lesson title + optional short
context are interpolated; **no full lesson body**.

**Quota enforcement** happens in `api/ai.py` before streaming: read
`features.ai_tutor_daily_limit` (already on the `require_user` result) and today's
`ai_usage.message_count`. `limit is None` ⇒ unlimited. Increment only after a
successful assistant reply (so failed generations don't burn quota).

---

## 8. Frontend (web) changes

- **New:** `frontend/packages/web/src/lib/ai/tutor-client.ts`
  - `streamTutor(payload, { onToken, onDone, onError, signal })`: `fetch` the
    endpoint with `Authorization: Bearer <supabase access_token>` (reuse the
    session helper pattern from `psx/client.ts`), read `response.body` as a
    `ReadableStream`, parse SSE lines, dispatch callbacks. `AbortController`
    support for cancel-on-close.
  - `fetchTutorHistory(limit)`, `fetchTutorUsage()` thin GET helpers.
- **Edit:** `HubChatPanel.tsx`
  - Replace `askTutor` call with `streamTutor`; append `token` deltas to the live
    assistant bubble (typewriter). Keep presets, greeting, auto-scroll.
  - States: **signed-out** → replace input with "Sign in to chat with your tutor"
    CTA; **quota-exceeded** → inline banner ("Daily limit reached — upgrade or
    come back tomorrow", bilingual) and disable input; **provider error** → the
    existing "something went wrong" fallback line. Abort the stream on unmount/close.
  - Optional: on open, hydrate the last session via `fetchTutorHistory`.
- **Retire:** `frontend/packages/web/src/features/learn/ai-functions.ts` (and any
  now-unused `LOVABLE_API_KEY` wiring on the web tier). If the per-lesson tutor
  imports `askTutor`, repoint it to `tutor-client.ts` (same payload shape).
- **Env:** add `VITE_*` only if a *new* base URL is needed — reuse existing
  `API_BASE_URL` (already points at the FastAPI backend). No LLM keys client-side.

---

## 9. Error handling matrix

| Condition | Backend | Frontend |
|---|---|---|
| Not authenticated | HTTP 401 (no stream) | Sign-in CTA in panel |
| Quota exceeded | SSE `error code:"quota"`; no LLM call / no writes | Banner + disabled input, bilingual |
| Gemini fails pre-stream | Transparent Groq fallback | (invisible) |
| Both providers fail | SSE `error code:"provider"`; no assistant persist / no usage++ | "Something went wrong, try again" line |
| Client closes panel | Generator cancelled on disconnect | `AbortController.abort()` |

---

## 10. Testing (TDD — tests before implementation)

**Backend (`backend/tests/`, pytest, `httpx` mocked):**
- `require_user` rejects missing/invalid JWT → 401.
- Quota: under limit allows; at limit blocks with `quota` event and **no** usage
  increment / **no** history write; `NULL` limit ⇒ never blocks.
- Fallback: Gemini 429 → Groq used; assistant text streamed; `provider='groq'`
  persisted.
- Both fail → `provider` error event, no assistant row, usage unchanged.
- Success path persists exactly one `user` + one `assistant` row and increments
  `ai_usage` by 1.
- `GET history` / `GET usage` return owner-scoped data with correct shape.

**Web (component tests, `HubChatPanel`):**
- Streams tokens into the assistant bubble.
- Quota-exceeded event → banner + disabled input.
- Signed-out → sign-in CTA (no network call).
- Close mid-stream → abort called; no state update after unmount.

---

## 11. Configuration & secrets

`backend/.env` (and Railway backend env) — **new**:
```
GEMINI_API_KEY=<google ai studio free key>
GROQ_API_KEY=<groq free key>
# optional overrides
AI_TUTOR_MODEL_PRIMARY=gemini-2.5-flash
AI_TUTOR_MODEL_FALLBACK=llama-3.3-70b-versatile
AI_TUTOR_REQUEST_TIMEOUT_S=30
```
No client-side keys. `.env.example` updated with placeholders. Do not modify
deployment config beyond adding these env vars.

---

## 12. Rollout order (for the implementation plan)

1. Migration (`ai_chat_history`, `ai_usage`, Pro=100) + apply + regen `types.ts`.
2. Config keys + `db/models/ai.py` + `schemas/ai.py`.
3. `repositories/ai_repo.py` (+ tests).
4. `services/ai/providers.py`, `quota.py`, `tutor.py` (+ tests, httpx mocked).
5. `api/ai.py` router + register in `main.py` (+ endpoint tests).
6. Web `tutor-client.ts` + `HubChatPanel` streaming/quota/auth states (+ tests).
7. Retire `ai-functions.ts`; verify typecheck/lint; end-to-end manual check.

---

## 13. Open items / risks

- **Streaming through service-role Supabase writes:** persistence uses the backend
  service key (bypasses RLS); ensure history/usage rows always carry the correct
  `user_id` from `require_user`, never client-supplied.
- **Gemini OpenAI-compat quirks:** confirm SSE `data: [DONE]` handling and that
  `stream:true` is honored on the compat endpoint; `providers.py` must tolerate
  both providers' chunk shapes.
- **Free-tier limits (per earlier research):** Gemini free ≈ 10 RPM / 250k TPM /
  1500 RPD; Groq free ≈ 30 RPM / low TPM. Per-user daily caps (10/100) keep us
  well within these for classroom scale; revisit if concurrency grows.
```
