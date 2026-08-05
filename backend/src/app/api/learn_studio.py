"""Authenticated LearnHub Studio project, practice quiz and video APIs."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import require_user
from app.config import settings
from app.db.supabase import get_supabase
from app.middleware.rate_limit import limiter
from app.repositories import learnhub_studio as repo
from app.repositories import learnhub_usage
from app.services.learnhub.studio import (
    answer_studio_question,
    artifact_fingerprint,
    normalize_topic,
)
from app.services.learnhub.studio_pdf import StudioPdfError, inspect_pdf

router = APIRouter(tags=["learn-studio"])


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(..., min_length=3, max_length=160)
    lang: Literal["en", "ur"] = "en"
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    targetMinutes: int = Field(4, ge=3, le=5)


class QuizAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct: int = Field(..., ge=0, le=20)
    total: int = Field(..., ge=1, le=20)
    answers: list[Optional[int]] = Field(default_factory=list, max_length=20)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class StudioChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(..., min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)
    lang: Literal["en", "ur"] = "en"


def _require_enabled() -> None:
    if not settings.learn_studio_enabled or not settings.learnhub_rag_enabled:
        raise HTTPException(503, "LearnHub Studio is not enabled")


@router.get("/learn/studio/status")
@limiter.limit("60/minute")
async def studio_status(request: Request, user: dict = Depends(require_user)):
    return {
        "enabled": settings.learn_studio_enabled and settings.learnhub_rag_enabled,
        "packDailyLimit": settings.learn_studio_pack_daily_limit,
        "videoDailyLimit": settings.learn_studio_video_daily_limit,
        "pdfEnabled": True,
        "pdfMaxBytes": settings.learn_studio_pdf_max_bytes,
        "pdfMaxPages": settings.learn_studio_pdf_max_pages,
    }


def _project_payload(row: dict) -> dict:
    pack = deepcopy(row.get("study_pack")) if row.get("study_pack") else None
    if pack and pack.get("lesson"):
        lesson = pack["lesson"]
        lesson.update({
            "origin": "generated",
            "language": row["language"],
            "sources": row.get("source_snapshot") or [],
            "projectId": str(row["id"]),
            "videoStatus": "ready" if row.get("video_ready") else row.get("stage", "not_requested"),
            "rewardMode": "practice",
            "generatedAt": row["created_at"].isoformat() if row.get("created_at") else None,
            "sourceKind": row.get("source_kind", "topic"),
            "documentName": row.get("document_name"),
        })
    return {
        "id": str(row["id"]),
        "topic": row["topic"],
        "language": row["language"],
        "level": row["level"],
        "targetMinutes": row["target_minutes"],
        "sourceKind": row.get("source_kind", "topic"),
        "documentName": row.get("document_name"),
        "documentPageCount": row.get("document_page_count"),
        "status": row["status"],
        "stage": row["stage"],
        "errorCode": row.get("error_code"),
        "errorMessage": row.get("error_message"),
        "bestScore": row.get("best_score", 0),
        "studyPack": pack,
        "videoReady": bool(row.get("video_ready")),
        "videoDurationSeconds": row.get("video_duration_seconds"),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.post("/learn/studio/projects", status_code=202)
@limiter.limit("10/minute")
async def create_project(
    request: Request,
    body: CreateProjectRequest,
    user: dict = Depends(require_user),
):
    _require_enabled()
    allowed, used = await repo.consume_usage(
        user["user_id"], "pack", settings.learn_studio_pack_daily_limit
    )
    if not allowed:
        raise HTTPException(429, f"Daily study-pack limit reached ({used}).")
    normalized = normalize_topic(body.topic)
    row = await repo.create_project(
        user_id=user["user_id"], topic=body.topic.strip(), normalized_topic=normalized,
        language=body.lang, level=body.level, target_minutes=body.targetMinutes,
        fingerprint=artifact_fingerprint(body.topic, body.lang, body.level, body.targetMinutes),
    )
    full = await repo.get_project(user["user_id"], str(row["id"]))
    return _project_payload(full or row)


async def _upload_private_pdf(object_path: str, payload: bytes) -> None:
    def run() -> None:
        get_supabase().storage.from_(settings.learn_studio_media_bucket).upload(
            object_path,
            payload,
            {"content-type": "application/pdf", "upsert": "false"},
        )
    await asyncio.to_thread(run)


async def _remove_private_objects(paths: list[str | None]) -> None:
    existing = [path for path in paths if path]
    if not existing:
        return
    await asyncio.to_thread(
        get_supabase().storage.from_(settings.learn_studio_media_bucket).remove,
        existing,
    )


@router.post("/learn/studio/projects/pdf", status_code=202)
@limiter.limit("5/minute")
async def create_pdf_project(
    request: Request,
    file: UploadFile = File(...),
    topic: str = Form("", max_length=160),
    lang: Literal["en", "ur"] = Form("en"),
    level: Literal["beginner", "intermediate", "advanced"] = Form("beginner"),
    targetMinutes: int = Form(4, ge=3, le=5),
    user: dict = Depends(require_user),
):
    _require_enabled()
    payload = await file.read(settings.learn_studio_pdf_max_bytes + 1)
    try:
        inspection = await asyncio.to_thread(
            inspect_pdf, payload, file.filename, file.content_type,
        )
    except StudioPdfError as exc:
        if exc.code in {"pdf_too_large", "pdf_too_many_pages"}:
            status = 413
        elif exc.code in {"pdf_type_invalid", "pdf_extension_required"}:
            status = 415
        else:
            status = 400
        raise HTTPException(status, str(exc)) from exc

    project_id = str(uuid4())
    document_id = str(uuid4())
    object_path = f"documents/{user['user_id']}/{project_id}/source.pdf"
    focus = topic.strip()[:160] or Path(inspection.filename).stem[:160]
    await _upload_private_pdf(object_path, payload)
    try:
        row, used = await repo.create_pdf_project(
            project_id=project_id,
            document_id=document_id,
            user_id=user["user_id"],
            topic=focus,
            normalized_topic=normalize_topic(focus),
            language=lang,
            level=level,
            target_minutes=targetMinutes,
            original_name=inspection.filename,
            object_path=object_path,
            size_bytes=len(payload),
            content_hash=inspection.content_hash,
            page_count=inspection.page_count,
            daily_limit=settings.learn_studio_pack_daily_limit,
        )
    except Exception:
        await _remove_private_objects([object_path])
        raise
    if row is None:
        await _remove_private_objects([object_path])
        raise HTTPException(429, f"Daily study-pack limit reached ({used}).")
    full = await repo.get_project(user["user_id"], project_id)
    return _project_payload(full or row)


@router.get("/learn/studio/projects")
@limiter.limit("60/minute")
async def projects(request: Request, user: dict = Depends(require_user)):
    _require_enabled()
    rows = await repo.list_projects(user["user_id"])
    return {"projects": [_project_payload(row) for row in rows]}


@router.get("/learn/studio/projects/{project_id}")
@limiter.limit("120/minute")
async def project(request: Request, project_id: UUID, user: dict = Depends(require_user)):
    _require_enabled()
    row = await repo.get_project(user["user_id"], str(project_id))
    if not row:
        raise HTTPException(404, "Studio project not found")
    return _project_payload(row)


@router.delete("/learn/studio/projects/{project_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_project(
    request: Request, project_id: UUID, user: dict = Depends(require_user),
):
    _require_enabled()
    paths = await repo.delete_project(user["user_id"], str(project_id))
    if paths is None:
        raise HTTPException(404, "Studio project not found")
    cleanup_id = paths.pop("cleanup_id", None)
    try:
        await _remove_private_objects(list(paths.values()))
    except Exception:
        # The durable cleanup job remains queued for the media worker.
        return None
    if cleanup_id:
        await repo.complete_cleanup(cleanup_id)
    return None


@router.post("/learn/studio/projects/{project_id}/video", status_code=202)
@limiter.limit("10/minute")
async def create_video(
    request: Request, project_id: UUID, user: dict = Depends(require_user),
):
    _require_enabled()
    row, created, allowed = await repo.queue_video(
        user["user_id"], str(project_id), settings.learn_studio_video_daily_limit
    )
    if not row:
        raise HTTPException(404, "Ready Studio project not found")
    if not allowed:
        raise HTTPException(429, "Daily video-generation limit reached.")
    full = await repo.get_project(user["user_id"], str(project_id))
    return {**_project_payload(full or row), "videoQueued": created}


@router.post("/learn/studio/projects/{project_id}/quiz-attempts")
@limiter.limit("30/minute")
async def quiz_attempt(
    request: Request, project_id: UUID, body: QuizAttemptRequest,
    user: dict = Depends(require_user),
):
    _require_enabled()
    if body.correct > body.total or (body.answers and len(body.answers) != body.total):
        raise HTTPException(422, "Quiz score or answers are inconsistent")
    best = await repo.record_quiz_attempt(
        user_id=user["user_id"], project_id=str(project_id), correct=body.correct,
        total=body.total, answers=body.answers,
    )
    if best is None:
        raise HTTPException(404, "Studio project not found")
    return {"bestScore": best}


@router.post("/learn/studio/projects/{project_id}/chat")
@limiter.limit("10/minute")
async def studio_chat(
    request: Request, project_id: UUID, body: StudioChatRequest,
    user: dict = Depends(require_user),
):
    _require_enabled()
    row = await repo.get_project(user["user_id"], str(project_id))
    if not row or not row.get("study_pack"):
        raise HTTPException(404, "Ready Studio project not found")
    allowed, used = await learnhub_usage.check_and_increment(
        user["user_id"], settings.learn_ai_daily_limit
    )
    if not allowed:
        raise HTTPException(429, f"Daily LearnHub AI limit reached ({used}).")
    result = await answer_studio_question(
        pack=row["study_pack"], source_snapshot=row.get("source_snapshot") or [],
        question=body.message,
        history=[item.model_dump() for item in body.history], lang=body.lang,
        private_source_rows=row.get("private_source_rows") or [],
    )
    if result is None:
        return {"answer": None, "sources": []}
    return result.model_dump()


def _signed_url(path: str | None, expires: int = 900) -> str | None:
    if not path:
        return None
    result = get_supabase().storage.from_(settings.learn_studio_media_bucket).create_signed_url(path, expires)
    return result.get("signedURL") or result.get("signedUrl")


@router.get("/learn/studio/projects/{project_id}/video/playback")
@limiter.limit("60/minute")
async def video_playback(
    request: Request, project_id: UUID, user: dict = Depends(require_user),
):
    _require_enabled()
    paths = await repo.playback_paths(user["user_id"], str(project_id))
    if not paths:
        raise HTTPException(404, "Video is not ready")
    video, captions, poster = await asyncio.gather(
        asyncio.to_thread(_signed_url, paths["video_object_path"]),
        asyncio.to_thread(_signed_url, paths.get("caption_object_path")),
        asyncio.to_thread(_signed_url, paths.get("thumbnail_object_path")),
    )
    return {
        "url": video, "captionsUrl": captions, "posterUrl": poster,
        "durationSeconds": paths.get("video_duration_seconds"), "expiresIn": 900,
    }
