"""Durable LearnHub Studio worker entrypoint for a dedicated Railway service."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import socket

import structlog
from PIL import features
from sqlalchemy import text

from app.config import settings
from app.db.supabase import get_supabase
from app.repositories import learnhub_studio as repo
from app.repositories.base import connect
from app.services.learnhub.studio import (
    artifact_fingerprint,
    generate_study_pack,
    generate_study_pack_from_sources,
    private_pdf_fingerprint,
)
from app.services.learnhub.studio_media import render_study_pack_video
from app.services.learnhub.studio_pdf import StudioPdfError, extract_pdf_sources

log = structlog.get_logger(__name__)


async def _database_readiness() -> tuple[int, int]:
    async with connect() as connection:
        row = (await connection.execute(text("""
            SELECT count(*) FILTER (WHERE is_active) AS active,
                   count(*) FILTER (WHERE is_active AND embedding IS NOT NULL) AS embedded
            FROM learnhub_knowledge_chunks
        """))).mappings().one()
    return int(row["active"]), int(row["embedded"])


async def _storage_ready() -> None:
    await asyncio.to_thread(
        get_supabase().storage.get_bucket,
        settings.learn_studio_media_bucket,
    )


async def preflight() -> dict[str, object]:
    """Fail fast when a worker deployment cannot complete a real Studio job."""
    problems: list[str] = []
    if not settings.learnhub_rag_enabled:
        problems.append("LEARNHUB_RAG_ENABLED must be true")
    if not settings.learn_studio_enabled:
        problems.append("LEARN_STUDIO_ENABLED must be true")
    if not settings.gemini_api_key_pool:
        problems.append("GEMINI_API_KEY or GEMINI_API_KEYS is required")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            problems.append(f"{binary} is not installed")
    if not features.check_feature("raqm"):
        problems.append("Pillow RAQM support is required for correctly shaped Urdu slides")

    active = embedded = 0
    try:
        active, embedded = await _database_readiness()
        if active <= 0:
            problems.append("LearnHub corpus is empty; run scripts/data/ingest_learnhub.py")
        elif embedded <= 0:
            problems.append("LearnHub corpus has no embeddings; rerun corpus ingest")
    except Exception as exc:
        problems.append(f"LearnHub database readiness failed: {type(exc).__name__}: {exc}")

    try:
        await _storage_ready()
    except Exception as exc:
        problems.append(
            f"private storage bucket {settings.learn_studio_media_bucket!r} is unavailable: "
            f"{type(exc).__name__}: {exc}"
        )

    if problems:
        raise RuntimeError("LearnHub Studio worker is not ready:\n- " + "\n- ".join(problems))
    return {
        "bucket": settings.learn_studio_media_bucket,
        "active_corpus_chunks": active,
        "embedded_corpus_chunks": embedded,
        "urdu_shaping": "RAQM",
        "tts_model": settings.learn_studio_tts_model,
    }


async def process(job: dict) -> None:
    job_id = str(job["id"])
    project_id = str(job["project_id"])
    project = await repo.get_project_for_job(project_id)
    if not project:
        raise RuntimeError("project disappeared")

    if job["kind"] == "study_pack":
        owner_user_id = None
        fingerprint = artifact_fingerprint(
            project["topic"], project["language"], project["level"],
            project["target_minutes"],
        )
        corpus_version = settings.learn_studio_corpus_version
        if project.get("source_kind") == "pdf":
            await repo.set_stage(job_id, project_id, "extracting_document")
            await repo.update_document_extraction(project_id, status="extracting")
            try:
                payload = await asyncio.to_thread(
                    get_supabase().storage.from_(settings.learn_studio_media_bucket).download,
                    project["document_object_path"],
                )
                extracted = await asyncio.to_thread(
                    extract_pdf_sources,
                    payload,
                    document_id=str(project["document_id"]),
                    filename=project["document_name"],
                    focus=project["topic"],
                )
            except StudioPdfError as exc:
                await repo.update_document_extraction(
                    project_id, status="failed", error_code=exc.code,
                )
                await repo.finish_unsupported(
                    job_id, project_id, error_code=exc.code, error_message=str(exc),
                )
                return
            await repo.update_document_extraction(
                project_id, status="ready", page_count=extracted.page_count,
                source_rows=extracted.source_rows,
            )
            owner_user_id = str(project["user_id"])
            fingerprint = private_pdf_fingerprint(
                user_id=owner_user_id,
                content_hash=project["document_content_hash"],
                focus=project["topic"],
                lang=project["language"],
                level=project["level"],
                target_minutes=project["target_minutes"],
            )
            corpus_version = f"private-pdf-{project['document_content_hash'][:12]}"

        await repo.set_stage(job_id, project_id, "generating_lesson")
        if project.get("source_kind") == "pdf":
            result = await generate_study_pack_from_sources(
                topic=project["topic"], rows=extracted.source_rows,
                lang=project["language"], level=project["level"],
                target_minutes=project["target_minutes"], confidential=True,
                lesson_seed=fingerprint,
            )
        else:
            result = await generate_study_pack(
                topic=project["topic"], lang=project["language"],
                level=project["level"], target_minutes=project["target_minutes"],
            )
        if result is None:
            await repo.finish_unsupported(
                job_id,
                project_id,
                error_code="document_grounding_failed" if project.get("source_kind") == "pdf" else "insufficient_sources",
                error_message=(
                    "The uploaded PDF could not support a fully grounded lesson."
                    if project.get("source_kind") == "pdf"
                    else "Trusted LearnHub sources do not cover this topic yet."
                ),
            )
            return
        pack, sources = result
        await repo.set_stage(job_id, project_id, "validating")
        await repo.complete_study_pack(
            job_id=job_id, project_id=project_id,
            fingerprint=fingerprint,
            language=project["language"], level=project["level"],
            target_minutes=project["target_minutes"],
            pack=pack.model_dump(by_alias=True), source_snapshot=sources,
            corpus_version=corpus_version,
            prompt_version=settings.learn_studio_prompt_version,
            renderer_version=settings.learn_studio_renderer_version,
            owner_user_id=owner_user_id,
        )
        return

    if not project.get("study_pack"):
        raise RuntimeError("video job has no ready study pack")
    await repo.set_stage(job_id, project_id, "generating_audio")
    media = await render_study_pack_video(
        project_id,
        project["study_pack"],
        project["language"],
        on_rendering=lambda: repo.set_stage(job_id, project_id, "rendering"),
    )
    await repo.set_stage(job_id, project_id, "uploading")
    await repo.complete_video(job_id=job_id, project_id=project_id, **media)


async def main(*, check_only: bool = False) -> None:
    readiness = await preflight()
    if check_only:
        print("LearnHub Studio worker readiness: PASS")
        for name, value in readiness.items():
            print(f"  {name}: {value}")
        return
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    log.info("learn_studio_worker_started", worker_id=worker_id, **readiness)
    while True:
        cleanup = await repo.claim_cleanup()
        if cleanup:
            try:
                await asyncio.to_thread(
                    get_supabase().storage.from_(settings.learn_studio_media_bucket).remove,
                    cleanup["object_paths"],
                )
                await repo.complete_cleanup(str(cleanup["id"]))
            except Exception as exc:
                log.exception("learn_studio_cleanup_failed", cleanup_id=str(cleanup["id"]))
                await repo.fail_cleanup(cleanup, str(exc))
            continue
        job = await repo.claim_job(worker_id)
        if not job:
            await asyncio.sleep(settings.learn_studio_worker_poll_seconds)
            continue
        try:
            await process(job)
        except Exception as exc:
            log.exception("learn_studio_job_failed", job_id=str(job["id"]), kind=job["kind"])
            await repo.fail_job(job, str(exc))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate flags, AI keys, FFmpeg, database corpus, and storage, then exit.",
    )
    args = parser.parse_args()
    asyncio.run(main(check_only=args.check))
