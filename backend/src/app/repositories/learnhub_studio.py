"""SQL repository for LearnHub Studio projects, quotas, artifacts and jobs."""
from __future__ import annotations

import json
from typing import Literal

from sqlalchemy import text

from app.repositories.base import begin, connect

UsageKind = Literal["pack", "video"]

_CONSUME_PACK = text("""
INSERT INTO learnhub_studio_usage (user_id, day, pack_count, video_count, updated_at)
VALUES (CAST(:user_id AS uuid), (now() AT TIME ZONE 'Asia/Karachi')::date, 1, 0, now())
ON CONFLICT (user_id, day) DO UPDATE SET
  pack_count = learnhub_studio_usage.pack_count + 1, updated_at = now()
WHERE learnhub_studio_usage.pack_count < :limit
RETURNING pack_count
""")

_CONSUME_VIDEO = text("""
INSERT INTO learnhub_studio_usage (user_id, day, pack_count, video_count, updated_at)
VALUES (CAST(:user_id AS uuid), (now() AT TIME ZONE 'Asia/Karachi')::date, 0, 1, now())
ON CONFLICT (user_id, day) DO UPDATE SET
  video_count = learnhub_studio_usage.video_count + 1, updated_at = now()
WHERE learnhub_studio_usage.video_count < :limit
RETURNING video_count
""")


async def consume_usage(user_id: str, kind: UsageKind, limit: int) -> tuple[bool, int]:
    if limit <= 0:
        return False, 0
    statement = _CONSUME_PACK if kind == "pack" else _CONSUME_VIDEO
    async with begin() as conn:
        row = (await conn.execute(statement, {"user_id": user_id, "limit": limit})).fetchone()
    return (row is not None, int(row[0]) if row else limit)


async def create_project(
    *, user_id: str, topic: str, normalized_topic: str, language: str,
    level: str, target_minutes: int, fingerprint: str,
) -> dict:
    async with begin() as conn:
        cached = (await conn.execute(text("""
            SELECT id FROM learnhub_studio_artifacts
            WHERE fingerprint = :fingerprint AND status = 'ready'
              AND quality_status = 'approved'
        """), {"fingerprint": fingerprint})).fetchone()
        status = "ready" if cached else "queued"
        stage = "ready" if cached else "queued"
        row = (await conn.execute(text("""
            INSERT INTO learnhub_studio_projects
              (user_id, artifact_id, topic, normalized_topic, language, level,
               target_minutes, status, stage)
            VALUES (CAST(:user_id AS uuid), CAST(:artifact_id AS uuid), :topic,
                    :normalized_topic, :language, :level, :target_minutes,
                    :status, :stage)
            RETURNING *
        """), {
            "user_id": user_id, "artifact_id": str(cached[0]) if cached else None,
            "topic": topic, "normalized_topic": normalized_topic,
            "language": language, "level": level, "target_minutes": target_minutes,
            "status": status, "stage": stage,
        })).mappings().one()
        if not cached:
            await conn.execute(text("""
                INSERT INTO learnhub_generation_jobs (project_id, kind)
                VALUES (CAST(:project_id AS uuid), 'study_pack')
            """), {"project_id": str(row["id"])})
    return dict(row)


async def create_pdf_project(
    *, project_id: str, document_id: str, user_id: str, topic: str,
    normalized_topic: str, language: str, level: str, target_minutes: int,
    original_name: str, object_path: str, size_bytes: int, content_hash: str,
    page_count: int, daily_limit: int,
) -> tuple[dict | None, int]:
    """Create the private document, project, and job in one quota-safe transaction."""
    async with begin() as conn:
        usage = (await conn.execute(
            _CONSUME_PACK, {"user_id": user_id, "limit": daily_limit}
        )).fetchone()
        if usage is None:
            return None, daily_limit
        row = (await conn.execute(text("""
            INSERT INTO learnhub_studio_projects
              (id, user_id, topic, normalized_topic, language, level,
               target_minutes, status, stage, source_kind)
            VALUES (CAST(:project_id AS uuid), CAST(:user_id AS uuid), :topic,
                    :normalized_topic, :language, :level, :target_minutes,
                    'queued', 'queued', 'pdf')
            RETURNING *
        """), {
            "project_id": project_id, "user_id": user_id, "topic": topic,
            "normalized_topic": normalized_topic, "language": language,
            "level": level, "target_minutes": target_minutes,
        })).mappings().one()
        await conn.execute(text("""
            INSERT INTO learnhub_studio_documents
              (id, project_id, user_id, original_name, object_path, mime_type,
               size_bytes, content_hash, page_count)
            VALUES (CAST(:document_id AS uuid), CAST(:project_id AS uuid),
                    CAST(:user_id AS uuid), :original_name, :object_path,
                    'application/pdf', :size_bytes, :content_hash, :page_count)
        """), {
            "document_id": document_id, "project_id": project_id,
            "user_id": user_id, "original_name": original_name,
            "object_path": object_path, "size_bytes": size_bytes,
            "content_hash": content_hash, "page_count": page_count,
        })
        await conn.execute(text("""
            INSERT INTO learnhub_generation_jobs (project_id, kind)
            VALUES (CAST(:project_id AS uuid), 'study_pack')
        """), {"project_id": project_id})
    return dict(row), int(usage[0])


async def list_projects(user_id: str, limit: int = 30) -> list[dict]:
    async with connect() as conn:
        rows = (await conn.execute(text("""
            SELECT p.*, a.study_pack, a.video_duration_seconds,
                   (a.video_object_path IS NOT NULL) AS video_ready,
                   d.original_name AS document_name, d.page_count AS document_page_count
            FROM learnhub_studio_projects p
            LEFT JOIN learnhub_studio_artifacts a ON a.id = p.artifact_id
            LEFT JOIN learnhub_studio_documents d ON d.project_id = p.id
            WHERE p.user_id = CAST(:user_id AS uuid)
            ORDER BY p.created_at DESC LIMIT :limit
        """), {"user_id": user_id, "limit": limit})).mappings().all()
    return [dict(row) for row in rows]


async def get_project(user_id: str, project_id: str) -> dict | None:
    async with connect() as conn:
        row = (await conn.execute(text("""
            SELECT p.*, a.study_pack, a.source_snapshot, a.quality_status,
                   a.video_duration_seconds, d.original_name AS document_name,
                   d.page_count AS document_page_count,
                   d.extracted_sources AS private_source_rows,
                   (a.video_object_path IS NOT NULL) AS video_ready
            FROM learnhub_studio_projects p
            LEFT JOIN learnhub_studio_artifacts a ON a.id = p.artifact_id
            LEFT JOIN learnhub_studio_documents d ON d.project_id = p.id
            WHERE p.id = CAST(:project_id AS uuid)
              AND p.user_id = CAST(:user_id AS uuid)
        """), {"user_id": user_id, "project_id": project_id})).mappings().first()
    return dict(row) if row else None


async def queue_video(
    user_id: str, project_id: str, daily_limit: int
) -> tuple[dict | None, bool, bool]:
    """Return (project, created, allowed), atomically quota-safe and idempotent."""
    async with begin() as conn:
        project = (await conn.execute(text("""
            SELECT p.* FROM learnhub_studio_projects p
            WHERE p.id = CAST(:project_id AS uuid)
              AND p.user_id = CAST(:user_id AS uuid) AND p.status = 'ready'
            FOR UPDATE
        """), {"project_id": project_id, "user_id": user_id})).mappings().first()
        if not project:
            return None, False, False
        existing = (await conn.execute(text("""
            SELECT id, status FROM learnhub_generation_jobs
            WHERE project_id=CAST(:project_id AS uuid) AND kind='video'
        """), {"project_id": project_id})).fetchone()
        if existing:
            if existing.status == "failed":
                await conn.execute(text("""
                    UPDATE learnhub_generation_jobs
                    SET status='queued', stage='queued', attempts=0, available_at=now(),
                        last_error=NULL, locked_at=NULL, locked_by=NULL, updated_at=now()
                    WHERE id=:job_id
                """), {"job_id": existing.id})
                await conn.execute(text("""
                    UPDATE learnhub_studio_projects
                    SET stage='video_queued', error_code=NULL, error_message=NULL, updated_at=now()
                    WHERE id=CAST(:project_id AS uuid)
                """), {"project_id": project_id})
                return dict(project), True, True
            return dict(project), False, True
        usage = (await conn.execute(_CONSUME_VIDEO, {
            "user_id": user_id, "limit": daily_limit,
        })).fetchone()
        if usage is None:
            return dict(project), False, False
        result = await conn.execute(text("""
            INSERT INTO learnhub_generation_jobs (project_id, kind, stage)
            VALUES (CAST(:project_id AS uuid), 'video', 'queued')
            ON CONFLICT (project_id, kind) DO NOTHING
            RETURNING id
        """), {"project_id": project_id})
        created = result.fetchone() is not None
        if created:
            await conn.execute(text("""
                UPDATE learnhub_studio_projects SET stage = 'video_queued', updated_at = now()
                WHERE id = CAST(:project_id AS uuid)
            """), {"project_id": project_id})
    return dict(project), created, True


async def record_quiz_attempt(
    *, user_id: str, project_id: str, correct: int, total: int, answers: list,
) -> int | None:
    async with begin() as conn:
        exists = (await conn.execute(text("""
            SELECT 1 FROM learnhub_studio_projects
            WHERE id = CAST(:project_id AS uuid) AND user_id = CAST(:user_id AS uuid)
            FOR UPDATE
        """), {"project_id": project_id, "user_id": user_id})).fetchone()
        if not exists:
            return None
        await conn.execute(text("""
            INSERT INTO learnhub_studio_quiz_attempts
              (project_id, user_id, correct, total, answers)
            VALUES (CAST(:project_id AS uuid), CAST(:user_id AS uuid), :correct,
                    :total, CAST(:answers AS jsonb))
        """), {"project_id": project_id, "user_id": user_id, "correct": correct,
                 "total": total, "answers": json.dumps(answers)})
        row = (await conn.execute(text("""
            UPDATE learnhub_studio_projects
            SET best_score = GREATEST(best_score, :correct), updated_at = now()
            WHERE id = CAST(:project_id AS uuid) RETURNING best_score
        """), {"project_id": project_id, "correct": correct})).fetchone()
    return int(row[0])


async def claim_job(worker_id: str) -> dict | None:
    async with begin() as conn:
        row = (await conn.execute(text("""
            WITH candidate AS (
              SELECT id FROM learnhub_generation_jobs
              WHERE (status = 'queued' AND available_at <= now())
                 OR (status = 'running' AND locked_at < now() - interval '10 minutes')
              ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE learnhub_generation_jobs j SET status = 'running',
              attempts = attempts + 1, locked_at = now(), locked_by = :worker_id,
              stage = CASE WHEN kind = 'study_pack' THEN 'retrieving_sources'
                           ELSE 'writing_storyboard' END,
              updated_at = now()
            FROM candidate WHERE j.id = candidate.id
            RETURNING j.*
        """), {"worker_id": worker_id})).mappings().first()
    return dict(row) if row else None


async def get_project_for_job(project_id: str) -> dict | None:
    async with connect() as conn:
        row = (await conn.execute(text("""
            SELECT p.*, a.study_pack, a.id AS existing_artifact_id,
                   d.id AS document_id, d.original_name AS document_name,
                   d.object_path AS document_object_path,
                   d.content_hash AS document_content_hash,
                   d.page_count AS document_page_count
            FROM learnhub_studio_projects p
            LEFT JOIN learnhub_studio_artifacts a ON a.id = p.artifact_id
            LEFT JOIN learnhub_studio_documents d ON d.project_id = p.id
            WHERE p.id = CAST(:project_id AS uuid)
        """), {"project_id": project_id})).mappings().first()
    return dict(row) if row else None


async def update_document_extraction(
    project_id: str, *, status: str, page_count: int | None = None,
    error_code: str | None = None, source_rows: list[dict] | None = None,
) -> None:
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_studio_documents
            SET extraction_status=:status,
                page_count=COALESCE(:page_count, page_count),
                extracted_sources=COALESCE(CAST(:source_rows AS jsonb), extracted_sources),
                error_code=:error_code, updated_at=now()
            WHERE project_id=CAST(:project_id AS uuid)
        """), {
            "project_id": project_id, "status": status,
            "page_count": page_count, "error_code": error_code,
            "source_rows": json.dumps(source_rows, ensure_ascii=False) if source_rows is not None else None,
        })


async def set_stage(job_id: str, project_id: str, stage: str) -> None:
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_generation_jobs SET stage=:stage, locked_at=now(), updated_at=now()
            WHERE id=CAST(:job_id AS uuid)
        """), {"job_id": job_id, "stage": stage})
        await conn.execute(text("""
            UPDATE learnhub_studio_projects SET stage=:stage,
              status=CASE WHEN status='queued' THEN 'generating' ELSE status END,
              updated_at=now() WHERE id=CAST(:project_id AS uuid)
        """), {"project_id": project_id, "stage": stage})


async def complete_study_pack(
    *, job_id: str, project_id: str, fingerprint: str, language: str, level: str,
    target_minutes: int, pack: dict, source_snapshot: list, corpus_version: str,
    prompt_version: str, renderer_version: str, owner_user_id: str | None = None,
) -> None:
    async with begin() as conn:
        artifact = (await conn.execute(text("""
            INSERT INTO learnhub_studio_artifacts
              (fingerprint, language, level, target_minutes, corpus_version,
               prompt_version, renderer_version, status, quality_status,
               study_pack, source_snapshot, owner_user_id)
            VALUES (:fingerprint, :language, :level, :target_minutes, :corpus_version,
                    :prompt_version, :renderer_version, 'ready', 'approved',
                    CAST(:pack AS jsonb), CAST(:sources AS jsonb), CAST(:owner_user_id AS uuid))
            ON CONFLICT (fingerprint) DO UPDATE SET
              study_pack=EXCLUDED.study_pack, source_snapshot=EXCLUDED.source_snapshot,
              status='ready', quality_status='approved', updated_at=now()
            RETURNING id
        """), {"fingerprint": fingerprint, "language": language, "level": level,
                 "target_minutes": target_minutes, "corpus_version": corpus_version,
                 "prompt_version": prompt_version, "renderer_version": renderer_version,
                 "owner_user_id": owner_user_id,
                 "pack": json.dumps(pack, ensure_ascii=False),
                 "sources": json.dumps(source_snapshot, ensure_ascii=False)})).fetchone()
        await conn.execute(text("""
            UPDATE learnhub_studio_projects SET artifact_id=:artifact_id,
              status='ready', stage='ready', error_code=NULL, error_message=NULL,
              updated_at=now() WHERE id=CAST(:project_id AS uuid)
        """), {"artifact_id": artifact[0], "project_id": project_id})
        await conn.execute(text("""
            UPDATE learnhub_generation_jobs SET status='completed', stage='ready',
              locked_at=NULL, locked_by=NULL, updated_at=now()
            WHERE id=CAST(:job_id AS uuid)
        """), {"job_id": job_id})


async def finish_unsupported(
    job_id: str, project_id: str, *, error_code: str = "insufficient_sources",
    error_message: str = "Trusted LearnHub sources do not cover this topic yet.",
) -> None:
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_studio_projects SET status='unsupported', stage='unsupported',
              error_code=:error_code, error_message=:error_message, updated_at=now()
            WHERE id=CAST(:project_id AS uuid)
        """), {"project_id": project_id, "error_code": error_code,
                 "error_message": error_message})
        await conn.execute(text("""
            UPDATE learnhub_generation_jobs SET status='completed', stage='unsupported',
              locked_at=NULL, locked_by=NULL, updated_at=now()
            WHERE id=CAST(:job_id AS uuid)
        """), {"job_id": job_id})


async def fail_job(job: dict, message: str) -> None:
    terminal = int(job["attempts"]) >= int(job["max_attempts"])
    status = "failed" if terminal else "queued"
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_generation_jobs SET status=:status, stage=:stage,
              available_at=now() + make_interval(secs => :delay), last_error=:message,
              locked_at=NULL, locked_by=NULL, updated_at=now()
            WHERE id=CAST(:job_id AS uuid)
        """), {"status": status, "stage": status, "delay": 2 ** int(job["attempts"]),
                 "message": message[:500], "job_id": str(job["id"])})
        if terminal:
            if job["kind"] == "video":
                await conn.execute(text("""
                    UPDATE learnhub_studio_projects SET status='ready', stage='video_failed',
                      error_code='video_failed',
                      error_message='The lesson is ready, but its video could not be generated. You can retry.',
                      updated_at=now() WHERE id=CAST(:project_id AS uuid)
                """), {"project_id": str(job["project_id"])})
            else:
                await conn.execute(text("""
                    UPDATE learnhub_studio_projects SET status='failed', stage='failed',
                      error_code='generation_failed', error_message='Generation could not be completed.',
                      updated_at=now() WHERE id=CAST(:project_id AS uuid)
                """), {"project_id": str(job["project_id"])})


async def playback_paths(user_id: str, project_id: str) -> dict | None:
    async with connect() as conn:
        row = (await conn.execute(text("""
            SELECT a.video_object_path, a.caption_object_path,
                   a.thumbnail_object_path, a.video_duration_seconds
            FROM learnhub_studio_projects p JOIN learnhub_studio_artifacts a ON a.id=p.artifact_id
            WHERE p.id=CAST(:project_id AS uuid) AND p.user_id=CAST(:user_id AS uuid)
              AND a.video_object_path IS NOT NULL
        """), {"project_id": project_id, "user_id": user_id})).mappings().first()
    return dict(row) if row else None


async def delete_project(user_id: str, project_id: str) -> dict | None:
    """Delete an owned project and return private object paths for storage cleanup."""
    async with begin() as conn:
        row = (await conn.execute(text("""
            SELECT p.id, p.artifact_id, p.source_kind, d.object_path,
                   a.owner_user_id, a.video_object_path, a.caption_object_path,
                   a.thumbnail_object_path
            FROM learnhub_studio_projects p
            LEFT JOIN learnhub_studio_documents d ON d.project_id=p.id
            LEFT JOIN learnhub_studio_artifacts a ON a.id=p.artifact_id
            WHERE p.id=CAST(:project_id AS uuid)
              AND p.user_id=CAST(:user_id AS uuid)
            FOR UPDATE OF p
        """), {"project_id": project_id, "user_id": user_id})).mappings().first()
        if not row:
            return None
        await conn.execute(text("""
            DELETE FROM learnhub_studio_projects
            WHERE id=CAST(:project_id AS uuid) AND user_id=CAST(:user_id AS uuid)
        """), {"project_id": project_id, "user_id": user_id})
        delete_artifact = False
        if row["artifact_id"] and row["owner_user_id"]:
            references = (await conn.execute(text("""
                SELECT count(*) FROM learnhub_studio_projects
                WHERE artifact_id=CAST(:artifact_id AS uuid)
            """), {"artifact_id": str(row["artifact_id"])})).scalar_one()
            if int(references) == 0:
                await conn.execute(text("""
                    DELETE FROM learnhub_studio_artifacts
                    WHERE id=CAST(:artifact_id AS uuid)
                      AND owner_user_id=CAST(:user_id AS uuid)
                """), {"artifact_id": str(row["artifact_id"]), "user_id": user_id})
                delete_artifact = True
        paths = [
            value for value in (
                row["object_path"],
                row["video_object_path"] if delete_artifact else None,
                row["caption_object_path"] if delete_artifact else None,
                row["thumbnail_object_path"] if delete_artifact else None,
            ) if value
        ]
        cleanup_id = None
        if paths:
            cleanup_id = (await conn.execute(text("""
                INSERT INTO learnhub_studio_cleanup_jobs (object_paths)
                VALUES (CAST(:paths AS jsonb)) RETURNING id
            """), {"paths": json.dumps(paths)})).scalar_one()
    return {
        "cleanup_id": str(cleanup_id) if cleanup_id else None,
        "document_object_path": row["object_path"],
        "video_object_path": row["video_object_path"] if delete_artifact else None,
        "caption_object_path": row["caption_object_path"] if delete_artifact else None,
        "thumbnail_object_path": row["thumbnail_object_path"] if delete_artifact else None,
    }


async def complete_cleanup(cleanup_id: str) -> None:
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_studio_cleanup_jobs
            SET status='completed', updated_at=now()
            WHERE id=CAST(:cleanup_id AS uuid)
        """), {"cleanup_id": cleanup_id})


async def claim_cleanup() -> dict | None:
    async with begin() as conn:
        row = (await conn.execute(text("""
            WITH candidate AS (
              SELECT id FROM learnhub_studio_cleanup_jobs
              WHERE (status='queued' AND available_at <= now())
                 OR (status='running' AND updated_at < now() - interval '10 minutes')
              ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE learnhub_studio_cleanup_jobs c
            SET status='running', attempts=attempts+1, updated_at=now()
            FROM candidate WHERE c.id=candidate.id RETURNING c.*
        """))).mappings().first()
    return dict(row) if row else None


async def fail_cleanup(cleanup: dict, message: str) -> None:
    terminal = int(cleanup["attempts"]) >= 5
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_studio_cleanup_jobs
            SET status=:status, available_at=now()+make_interval(secs => :delay),
                last_error=:message, updated_at=now()
            WHERE id=CAST(:cleanup_id AS uuid)
        """), {
            "status": "failed" if terminal else "queued",
            "delay": min(300, 2 ** int(cleanup["attempts"])),
            "message": message[:500], "cleanup_id": str(cleanup["id"]),
        })


async def complete_video(
    *, job_id: str, project_id: str, video_path: str, captions_path: str,
    thumbnail_path: str, duration_seconds: int,
) -> None:
    async with begin() as conn:
        await conn.execute(text("""
            UPDATE learnhub_studio_artifacts a SET
              video_object_path=:video_path, caption_object_path=:captions_path,
              thumbnail_object_path=:thumbnail_path,
              video_duration_seconds=:duration, updated_at=now()
            FROM learnhub_studio_projects p
            WHERE p.id=CAST(:project_id AS uuid) AND a.id=p.artifact_id
        """), {"project_id": project_id, "video_path": video_path,
                 "captions_path": captions_path, "thumbnail_path": thumbnail_path,
                 "duration": duration_seconds})
        await conn.execute(text("""
            UPDATE learnhub_studio_projects SET stage='ready', updated_at=now()
            WHERE id=CAST(:project_id AS uuid)
        """), {"project_id": project_id})
        await conn.execute(text("""
            UPDATE learnhub_generation_jobs SET status='completed', stage='ready',
              locked_at=NULL, locked_by=NULL, updated_at=now()
            WHERE id=CAST(:job_id AS uuid)
        """), {"job_id": job_id})
