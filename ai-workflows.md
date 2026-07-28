# NafaIQ — AI Feature Workflows

One diagram per AI feature, tracing the real call chain from the HTTP route down
through the service layer to the Pydantic response. Every `file.py:NNN` is the
defining line; follow the arrows and you follow the code.

Legend: `──▶` a call / data flow · `└▶` a branch · `⟲` a loop (bounded).
All paths are under `backend/src/app/` unless noted.

---

## 1. Verified Reports — the 5 report surfaces

The flagship feature. **Five surfaces share one pipeline**; they differ only by
the `ReportSpec` (schema + prompt + context builder + provider routing) selected
at the route. Route → cache/quota gate → engine → verify/guardrails → schema →
cache.

```
HTTP route  (api/reports.py)
  market-brief :24 · stock/{symbol} :46 · portfolio :61 · finance :76 · dashboard-recommendation :86
      │  picks REPORT_SPECS[...]  (specs.py:60)  +  mode (SHARED | USER_QUOTA | USER_DAILY)
      ▼
report_service.serve(spec, mode, user, lang, force)     (report_service.py:166)
      │
      ├─ _cached_today() ─── hit? ──▶ return cached ReportResponse   (report_service.py:140)   ← day-cached
      ├─ quota.check_report_quota()  (USER_QUOTA, or forced USER_DAILY) ─ 429 if exhausted
      ├─ _recent_failures cooldown (300s)                            (report_service.py:102)
      └─ _single_flight(ckey) ── collapses a dashboard-open stampede onto ONE generation  (report_service.py:125)
                │
                ▼
        engine.generate_report(spec, user_id, subject, days, lang)   (engine.py:526)
                │
                │ 1. bundle = spec.context_builder(...)              ─────▶ context.py
                │        market_brief   -> build_market_brief_context   (context.py:157)
                │        stock_analysis -> build_stock_analysis_context (context.py:250)
                │        portfolio      -> build_portfolio_context      (context.py:368)
                │        finance        -> build_finance_context        (context.py:519)
                │        dashboard_rec  -> build_dashboard_rec_context  (context.py:713)  (reuses build_finance_context)
                │
                │ 2. filled = spec.prompt_template.format(            ─────▶ prompts/*.txt via load_prompt (prompts.py:28)
                │        lang, bundle_json=json(bundle),                      scaffold = report_scaffold.txt + surface body
                │        untrusted_data=_untrusted_block(bundle))     (engine.py:85)   ← prompt-injection defence
                │
                │ 3. client = make_report_client(confidential=spec.confidential)  (providers.py:572)
                │        confidential=False -> Gemini (shared) · confidential=True -> Groq (per-user data)
                │        └▶ HARD RAISE if confidential data would hit free Gemini tier
                │
                │ 4. report = generate_structured(client, response_model=spec.schema, ...)  (providers.py:650)
                │        └─────────────────────────────────────────▶ schemas/reports.py  (Instructor -> validated Pydantic)
                │             MarketBriefReport :151 · StockAnalysisReport :155 · PortfolioReport :160
                │             FinanceReport :198 · DashboardRecReport :236   (all carry citations + disclaimer)
                │        report = _normalize_generated_report(report, bundle)
                │
                │ 5. GATE:  vr = verify_report(report, bundle)        (verify.py:138)   every number cites a real bundle key
                │           violations = check_report(report)         (guardrails.py:225) no buy/sell/allocate imperatives
                │
                │      ├▶ fail? ⟲ REGENERATE ONCE with _correction_message  (engine.py:99) -> re-verify + re-check
                │      ├▶ still fails verify? -> _strip_orphan_numbers -> re-verify  (engine.py:604)
                │      └▶ still fails? -> raise -> serve maps to 503  (fail closed, never a wrong report)
                │
                ▼ verified GeneratedReport (report + verification + latency + flags)
        serve: persist row (day cache) ──▶ ReportResponse                (schemas/reports.py:260)
      ▼
HTTP response  → web glass popups (MarketBriefCard, DashboardRecommendation) / mobile
```

| Surface | Route (`api/reports.py`) | Mode | `confidential` → provider | Context builder | Schema (`schemas/reports.py`) |
|---|---|---|---|---|---|
| Market brief | `:24` | SHARED | False → Gemini | `build_market_brief_context:157` | `MarketBriefReport:151` |
| Stock analysis | `:46` | SHARED | False → Gemini | `build_stock_analysis_context:250` | `StockAnalysisReport:155` |
| Portfolio | `:61` | USER_QUOTA | True → Groq | `build_portfolio_context:368` | `PortfolioReport:160` |
| Finance | `:76` | USER_QUOTA | True → Groq | `build_finance_context:519` | `FinanceReport:198` |
| Dashboard nudge | `:86` | USER_DAILY | True → Groq | `build_dashboard_rec_context:713` | `DashboardRecReport:236` |

> The `verify → regenerate-once → strip → fail-closed` gate (engine.py:572-615) is
> what makes a report either fully cited-and-compliant or a clean 503 — never a
> plausible-but-wrong number.

---

## 2. AI Tutor — streaming chat (SSE)

The only streaming surface. No verifier (it's conversational, not a cited
report); safety comes from the system prompt + provider failover **before the
first token only**.

```
HTTP route  POST /ai/tutor            (api/ai.py:36)
      │  quota.check_quota(user)      (quota.py:14)  ── 429 if daily tutor limit hit
      ▼
tutor.stream_reply(body)             (tutor.py:36)
      │  system = build_system_prompt(lessonTitle, lessonContext, lang)   (tutor.py:23)
      │  messages = [system] + body.messages
      │
      │  attempts = [ ("gemini", primary, providers.stream_gemini:270),
      │               ("groq",  fallback, providers.stream_groq:283) ]
      │        ⟲ for each provider:
      │            async for delta in fn(messages):  yield {"type":"token", text}   ── SSE to client
      │            └▶ ProviderError BEFORE first token -> try next provider
      │            └▶ ProviderError MID-stream        -> raise (never splice providers)
      │        yield {"type":"meta", provider, model}
      ▼
api/ai.py: after stream ends ──▶ tutor.persist_exchange(...)   (tutor.py:68)   ← writes turn to ai_repo
                                                                                  (history, not verified)

Sibling reads:  GET /ai/tutor/history :75 ─▶ tutor.get_history :90
                GET /ai/tutor/usage   :80 ─▶ quota usage
```

---

## 3. LearnHub RAG — quiz explanations & lesson summaries

Grounded generation: **retrieve first, then generate only from what was
retrieved.** If retrieval returns nothing, it returns `None` and the client falls
back to static content — the model is never allowed to answer ungrounded.

```
HTTP route  (api/learn_ai.py)
  POST /learn/ai/quiz-explanation :84        POST /learn/ai/summary :110
      │  _consume_allowance(user) :65  (learn_ai daily counter — separate from tutor quota)
      ▼
generation.explain_quiz_answer(...)  (generation.py:235)   |  generation.summarize(...)  (generation.py:284)
      │
      │ 1. rows = retrieval.search(query, mode=LESSON, lesson_id, limit)   ─────▶ §3a below (retrieval.py:220)
      │        └▶ if not rows: log "ungrounded" and return None   (client shows static explanation)
      │
      │ 2. system = _RULES.format(lang)  (generation.py:77)  +  load_prompt("learnhub_quiz" / "learnhub_summary")
      │        content_block = the retrieved lesson chunks, delimited as DATA (never instructions)
      │
      │ 3. result = _generate(response_model=QuizExplanation | LessonSummary, ...)  ─▶ providers.generate_structured (:650)
      │                                                                                └▶ schemas (Instructor-validated)
      │
      │ 4. result.sources = re-ground claimed ids to REAL retrieved section_ids  (generation.py:280)
      ▼
QuizExplanation | LessonSummary   (or None -> static fallback)
```

### 3a. `retrieval.search()` — hybrid RAG internals  (retrieval.py:220)

```
search(query, mode, lesson_id, limit)
      │  guard: query < 2 chars -> []
      │  asyncio.gather (with timeout):
      │        _vector_arm(q)  (retrieval.py:146) ── embed_gemini (providers.py:429, gemini-embedding-001 @768)
      │        │                                     -> pgvector cosine, calibrated relevance floor
      │        _fts_arm(q)     (retrieval.py:186) ── Postgres websearch_to_tsquery + ts_rank
      │
      │  ├▶ vector arm ran but cleared 0  -> return []   (positive "off-topic" verdict; FTS rows are noise)
      │  └▶ vector arm is None (embed failed) -> FTS-only  (the designed graceful fallback; Groq has no embeddings)
      │
      │  fuse: Reciprocal Rank Fusion over both arms  (score += 1/(RRF_K + rank + 1))
      ▼
ranked rows  (each with a real section_id the generator may cite)
```

Plain search route: `GET /learn/search :55` · `glossary/search :82` · `related :99`
(api/learn.py) call the same `retrieval.search()` and return rows directly (no LLM).

---

## 4. Email → Transaction Import — bank-alert ingestion

Not request/response — driven by a scheduler job or a manual sync button. Rules
first (deterministic), LLM only as fallback, then a confidence gate before any
row is written.

```
Trigger:  scheduler poll (jobs/scheduler.py)   OR   POST /api/integrations/email/sync (api/integrations.py:61)
      ▼
email_import/pipeline.py
      │  Gmail API pull (OAuth, gmail.readonly) — server-side filtered to bank senders
      │  senders.is_candidate() — drop OTP / declined / statement noise
      │
      │  parse:  rules.parse()  (deterministic per-bank)  ──fail──▶  llm.parse()  (llm.py:63)
      │                                                                 │ gemini complete_gemini_json (:374)
      │                                                                 │  └fail▶ groq complete_groq_json (:387)
      │                                                                 ▼
      │                                                          ParsedTransaction (models.py:35)  ← confidence gated
      │
      │  values["category"] = canonical_category(parsed.category)   (categories.py — one shared vocabulary)
      │  values["transaction_type"], amount, email_message_id, source="bank_email"
      ▼
finance_repo.insert_transaction_dedup(values)   ← partial unique index (user_id, email_message_id) = no double-book
      ▼
notifier.notify_activity(...)   ← "transaction recorded" email + in-app
```

The `canonical_category()` step is the same normaliser the manual transaction and
budget forms use, so an imported `"food & dining"` lands in the exact bucket a
`"Food & Dining"` budget joins against (`repositories/finance/budgets.py` live-spend
subquery, case-insensitive).

---

## Cross-cutting layers (every feature above passes through these)

```
providers.py     one OpenAI-SDK client, two providers via base_url:
                 GEMINI_BASE_URL :59  ·  GROQ_BASE_URL :60
                 key-pool rotation on 429/401/403 (_should_rotate :140, _condemns_key :124)
                 Gemini→Groq failover (tutor + email parser); reports pin one provider up front
                 confidential routing guard (_report_provider :548, make_report_client :572)

observability    langfuse.openai drop-in (providers.py:53) when keys set (config.py:203)
                 init_langfuse (main.py:87) / flush_langfuse (main.py:98) — traces every LLM call

prompts/         file-based, @lru_cache loader (prompts.py:28); scaffold + per-surface body
                 two-stage templating (specs._prompt :51); {{bundle_json}}/{{untrusted}} filled at gen time
```
