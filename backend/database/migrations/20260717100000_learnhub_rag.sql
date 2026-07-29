-- LearnHub RAG corpus store: one row per retrievable chunk of LearnHub
-- content (lesson sections, glossary terms, quiz explanations, ...), with a
-- 768-dim embedding for vector search and a generated tsvector for keyword
-- search. Populated by an offline export/embed pipeline through the backend
-- (service_role); read only by the backend at query time.
--
-- Why vector(768): must match settings.ai_embedding_dim — embed_gemini
-- truncates + re-normalizes every vector to 768 (gemini-embedding-001 is
-- MRL-trained, so the prefix is valid), which also keeps the column under
-- pgvector's 2000-dim index cap should an index ever be needed.
--
-- Access control — learned the hard way: Supabase's DEFAULT PRIVILEGES grant
-- table-level privileges to anon/authenticated on every new public table, so
-- enabling RLS alone is NOT enough; the grants below revoke explicitly. The
-- anon key ships in the browser bundle, and this table is backend-internal:
-- clients get RAG answers through /api/learn/*, never raw chunks via PostgREST.
--
-- Idempotent / re-runnable: IF NOT EXISTS on extension/table/indexes;
-- REVOKE-then-GRANT converges to the same state on every run.

BEGIN;

-- pgvector, in the extensions schema per Supabase convention (already there on
-- hosted projects; IF NOT EXISTS makes this a no-op then).
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.learnhub_knowledge_chunks (
    id bigserial PRIMARY KEY,
    source_type text NOT NULL CHECK (source_type IN (
        'lesson_section', 'lesson_overview', 'glossary_term',
        'quiz_explanation', 'learning_path'
    )),
    -- Stable id from the corpus export — the upsert key, so re-running the
    -- export updates chunks in place instead of duplicating them.
    source_id text NOT NULL UNIQUE,
    lesson_id text,
    section_id text,
    title text,
    heading text,
    text_en text NOT NULL,
    text_ur text,                                   -- NULL = no translation yet
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Hash of the source text: lets the pipeline skip re-embedding unchanged
    -- chunks (embedding rides the rate-limited Gemini free tier).
    content_hash text NOT NULL,
    embedding_model text NOT NULL,
    -- Nullable: a chunk row exists from export time; the embedding lands when
    -- the (rate-limited) embed pass reaches it.
    embedding extensions.vector(768),
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' || coalesce(heading, '') || ' ' || text_en)
    ) STORED,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learnhub_chunks_fts
    ON public.learnhub_knowledge_chunks USING gin (fts);
CREATE INDEX IF NOT EXISTS idx_learnhub_chunks_lesson_id
    ON public.learnhub_knowledge_chunks (lesson_id);
CREATE INDEX IF NOT EXISTS idx_learnhub_chunks_source_type
    ON public.learnhub_knowledge_chunks (source_type);

-- Deliberately NO index on `embedding`. The corpus is ~60-80 rows: an exact
-- sequential scan is sub-millisecond with 100% recall, while HNSW/IVFFlat are
-- APPROXIMATE — they would cost recall and buy nothing at this size. Revisit
-- only if this table ever exceeds ~10,000 rows; then add HNSW
-- (vector_cosine_ops) and measure recall.

ALTER TABLE public.learnhub_knowledge_chunks ENABLE ROW LEVEL SECURITY;

-- No policies on purpose: service_role bypasses RLS, and with zero policies
-- nothing else can read a row even if a grant ever leaks back in.

-- Supabase DEFAULT PRIVILEGES grant anon/authenticated access to every new
-- public table AND its sequences — revoke explicitly, don't rely on RLS alone.
REVOKE ALL ON TABLE public.learnhub_knowledge_chunks FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.learnhub_knowledge_chunks_id_seq FROM anon, authenticated;

GRANT ALL ON TABLE public.learnhub_knowledge_chunks TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.learnhub_knowledge_chunks_id_seq TO service_role;

COMMENT ON TABLE public.learnhub_knowledge_chunks IS
    'LearnHub RAG corpus: embedded + full-text-indexed content chunks. '
    'Backend-internal (service_role only) — clients query via /api/learn/*, '
    'gated by the LEARNHUB_RAG_ENABLED kill switch.';

-- ---------------------------------------------------------------------------
-- Related lessons: precomputed similarity, rebuilt wholesale on each ingest.
--
-- Precomputed rather than computed per request so /api/learn/related is a
-- plain indexed read: no embedding round-trip in the request path, so UI
-- latency stays predictable and a Gemini outage cannot slow the lesson page.
-- Rebuilt (not incrementally updated) because ~10 lessons make a full
-- recompute cheaper than reasoning about staleness.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learnhub_related (
    lesson_id         text NOT NULL,
    related_lesson_id text NOT NULL,
    score             real NOT NULL,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lesson_id, related_lesson_id),
    CONSTRAINT learnhub_related_not_self CHECK (lesson_id <> related_lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_learnhub_related_lookup
    ON public.learnhub_related (lesson_id, score DESC);

ALTER TABLE public.learnhub_related ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.learnhub_related FROM anon, authenticated;
GRANT ALL ON TABLE public.learnhub_related TO service_role;

COMMENT ON TABLE public.learnhub_related IS
    'Precomputed lesson-to-lesson similarity (cosine over section-embedding '
    'centroids). Rebuilt by scripts/ingest_learnhub.py; served by /api/learn/related.';

COMMIT;
