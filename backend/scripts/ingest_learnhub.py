"""Ingest LearnHub content into learnhub_knowledge_chunks (chunk + embed + upsert).

Also the admin re-index command: idempotent by content_hash, so a re-run on an
unchanged corpus embeds nothing.

Runs the TS corpus export FIRST and refuses to continue if it fails. The
corpus JSON is a generated artifact (gitignored) — regenerating it here is what
makes drift from the TypeScript source structurally impossible, since this repo
has no CI to enforce a committed artifact stays fresh.

    cd backend && python scripts/ingest_learnhub.py [--skip-export]

Needs Node/pnpm on PATH (dev machine — the backend Docker image never runs
ingest), GEMINI_API_KEY, and the DB credentials. Apply migration
20260717100000_learnhub_rag.sql first.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
CORPUS = BACKEND / "data" / "learn_corpus.json"

# Small enough that one 429 rotation re-does little work.
_EMBED_BATCH = 32


def run_export() -> None:
    """Regenerate learn_corpus.json from the TypeScript source of truth."""
    print("-> exporting corpus from shared/src ...")
    proc = subprocess.run(
        ["pnpm", "--filter", "@nafaiq/shared", "run", "export:learn-corpus"],
        cwd=REPO,
        capture_output=True,
        text=True,
        shell=sys.platform == "win32",  # pnpm is a .cmd shim on Windows
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(
            "corpus export failed — refusing to ingest a possibly stale corpus"
        )
    print((proc.stdout or "").strip())


def load_corpus() -> list[dict[str, Any]]:
    if not CORPUS.exists():
        raise SystemExit(f"{CORPUS} not found — run the export first")
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    chunks = data.get("chunks") or []
    if not chunks:
        raise SystemExit("corpus is empty — refusing to deactivate the whole index")
    return chunks


def content_hash(chunk: dict[str, Any]) -> str:
    """Covers everything that would change retrieval or display. text_ur is
    included so an Urdu-only fix reaches the served snippet — it costs a
    re-embed of one chunk, which at this corpus size is free."""
    payload = "|".join(
        [
            chunk["source_id"],
            chunk["text_en"],
            chunk.get("text_ur") or "",
            chunk.get("title") or "",
            chunk.get("heading") or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def main() -> int:
    if "--skip-export" not in sys.argv:
        run_export()

    from sqlalchemy import text

    from app.config import settings
    from app.repositories.base import begin, connect
    from app.services.ai.providers import embed_gemini

    if not settings.gemini_api_key_pool:
        print("GEMINI_API_KEY / GEMINI_API_KEYS not set — cannot embed.", file=sys.stderr)
        return 1

    chunks = load_corpus()
    for c in chunks:
        c["content_hash"] = content_hash(c)

    async with connect() as conn:
        res = await conn.execute(
            text(
                "SELECT source_id, content_hash, embedding_model "
                "FROM learnhub_knowledge_chunks"
            )
        )
        existing = {r[0]: (r[1], r[2]) for r in res.fetchall()}

    # Compare the MODEL too, not just the content hash. retrieval._vector_arm
    # filters on `embedding_model = :model`, so rows embedded by a previous
    # model match nothing: changing AI_EMBEDDING_MODEL used to be a silent
    # no-op here (content unchanged => "unchanged"), leaving the vector arm
    # permanently empty while ingest reported success.
    model = settings.ai_embedding_model
    fresh = [
        c
        for c in chunks
        if existing.get(c["source_id"]) != (c["content_hash"], model)
    ]
    print(f"-> {len(chunks)} chunks, {len(fresh)} new/changed")

    embedded = 0
    for i in range(0, len(fresh), _EMBED_BATCH):
        batch = fresh[i : i + _EMBED_BATCH]
        vectors = await embed_gemini([c["text_en"] for c in batch])
        rows = []
        for c, vec in zip(batch, vectors):
            rows.append(
                {
                    "source_type": c["source_type"],
                    "source_id": c["source_id"],
                    "lesson_id": c.get("lesson_id"),
                    "section_id": c.get("section_id"),
                    "title": c.get("title"),
                    "heading": c.get("heading"),
                    "text_en": c["text_en"],
                    "text_ur": c.get("text_ur"),
                    "metadata": json.dumps(c.get("metadata") or {}),
                    "content_hash": c["content_hash"],
                    "embedding_model": settings.ai_embedding_model,
                    "embedding": "[" + ",".join(f"{x:.7f}" for x in vec) + "]",
                }
            )
        async with begin() as conn:
            for r in rows:
                await conn.execute(
                    text(
                        """
                        INSERT INTO learnhub_knowledge_chunks
                            (source_type, source_id, lesson_id, section_id, title,
                             heading, text_en, text_ur, metadata, content_hash,
                             embedding_model, embedding, is_active, updated_at)
                        VALUES
                            (:source_type, :source_id, :lesson_id, :section_id, :title,
                             :heading, :text_en, :text_ur, CAST(:metadata AS jsonb),
                             :content_hash, :embedding_model,
                             CAST(:embedding AS extensions.vector), true, now())
                        ON CONFLICT (source_id) DO UPDATE SET
                            source_type = EXCLUDED.source_type,
                            lesson_id = EXCLUDED.lesson_id,
                            section_id = EXCLUDED.section_id,
                            title = EXCLUDED.title,
                            heading = EXCLUDED.heading,
                            text_en = EXCLUDED.text_en,
                            text_ur = EXCLUDED.text_ur,
                            metadata = EXCLUDED.metadata,
                            content_hash = EXCLUDED.content_hash,
                            embedding_model = EXCLUDED.embedding_model,
                            embedding = EXCLUDED.embedding,
                            is_active = true,
                            updated_at = now()
                        """
                    ),
                    r,
                )
        embedded += len(batch)
        print(f"  embedded {embedded}/{len(fresh)}")

    # Content removed from the corpus must stop being retrievable. Soft delete:
    # is_active=false rather than DELETE, so a bad export is recoverable by
    # re-running rather than by re-embedding from scratch.
    live_ids = [c["source_id"] for c in chunks]
    async with begin() as conn:
        res = await conn.execute(
            text(
                """
                UPDATE learnhub_knowledge_chunks
                SET is_active = false, updated_at = now()
                WHERE NOT (source_id = ANY(:ids)) AND is_active
                """
            ),
            {"ids": live_ids},
        )
        deactivated = res.rowcount or 0

    await rebuild_related()

    print(
        f"done: total={len(chunks)} embedded={embedded} "
        f"unchanged={len(chunks) - len(fresh)} deactivated={deactivated}"
    )
    return 0


async def rebuild_related() -> None:
    """Precompute lesson-to-lesson similarity so /api/learn/related is a plain
    indexed read — no embedding call in the request path, predictable latency.

    Centroid = mean of a lesson's section embeddings, normalized. With ~10
    lessons this is a 10x10 matrix; recomputing it wholesale each ingest is
    cheaper than reasoning about incremental correctness.
    """
    from sqlalchemy import text

    from app.repositories.base import begin, connect

    async with connect() as conn:
        res = await conn.execute(
            text(
                """
                SELECT lesson_id, AVG(embedding)::text AS centroid
                FROM learnhub_knowledge_chunks
                WHERE is_active AND embedding IS NOT NULL
                  AND lesson_id IS NOT NULL
                  AND source_type IN ('lesson_section', 'lesson_overview')
                GROUP BY lesson_id
                """
            )
        )
        centroids = {r[0]: r[1] for r in res.fetchall()}

    if len(centroids) < 2:
        print("  related: fewer than 2 lessons — nothing to relate")
        return

    async with begin() as conn:
        await conn.execute(text("DELETE FROM learnhub_related"))
        for lesson_id, centroid in centroids.items():
            await conn.execute(
                text(
                    """
                    INSERT INTO learnhub_related (lesson_id, related_lesson_id, score)
                    SELECT :lesson_id, x.lesson_id,
                           1 - (x.centroid <=> CAST(:centroid AS extensions.vector))
                    FROM (
                        SELECT lesson_id, AVG(embedding) AS centroid
                        FROM learnhub_knowledge_chunks
                        WHERE is_active AND embedding IS NOT NULL
                          AND lesson_id IS NOT NULL
                          AND lesson_id <> :lesson_id
                          AND source_type IN ('lesson_section', 'lesson_overview')
                        GROUP BY lesson_id
                    ) x
                    """
                ),
                {"lesson_id": lesson_id, "centroid": centroid},
            )
    print(f"  related: rebuilt for {len(centroids)} lessons")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
