"""LearnHub lecture management.

Every mutation is written in the same transaction as its audit row, so a
committed lecture change always has a record — the same rule the rest of the
admin surface follows.

Deleting is offered alongside archiving because the ask was explicitly "add or
remove a lecture", but archiving is the safer default: it hides the lecture
from learners, keeps the row, and is reversible.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.repositories.admin import lectures_repo
from app.repositories.base import begin, connect
from app.schemas.admin import LectureCreate, LectureInfo, LectureUpdate
from app.services.admin.audit import write_audit
from app.services.admin.authz import AdminContext, RequestMeta

# Fields worth recording in the audit before/after payload. The lesson body is
# deliberately excluded: sections/quiz are large enough to bloat the log, and
# what an auditor needs is *that* the body changed, not a full diff of it.
_AUDIT_FIELDS = (
    "slug",
    "title",
    "subtitle",
    "category",
    "level",
    "duration",
    "type",
    "status",
    "sort_order",
)


def _audit_view(row: dict[str, Any]) -> dict[str, Any]:
    view = {k: row.get(k) for k in _AUDIT_FIELDS}
    view["sections_count"] = len(row.get("sections") or [])
    view["quiz_count"] = len(row.get("quiz") or [])
    return view


async def list_lectures(
    *, status: Optional[str] = None, search: Optional[str] = None
) -> list[LectureInfo]:
    async with connect() as conn:
        rows = await lectures_repo.list_lectures(conn, status=status, search=search)
    return [LectureInfo(**r) for r in rows]


async def get_lecture(lecture_id: str) -> LectureInfo:
    async with connect() as conn:
        row = await lectures_repo.get_lecture(conn, lecture_id)
    if not row:
        raise HTTPException(404, "Lecture not found")
    return LectureInfo(**row)


async def create_lecture(
    *, actor: AdminContext, meta: RequestMeta, body: LectureCreate
) -> LectureInfo:
    data = body.model_dump(exclude={"reason"})
    _require_video_url(data.get("type"), data.get("video_url"))

    async with begin() as conn:
        # Checked before insert so the caller gets a 409 with a clear message
        # rather than a raw unique-violation 500.
        if await lectures_repo.get_by_slug(conn, data["slug"]):
            raise HTTPException(409, f"A lecture with slug '{data['slug']}' already exists")
        row = await lectures_repo.create_lecture(conn, data=data, actor_id=actor.user_id)
        await write_audit(
            conn,
            actor=actor,
            action="admin.lecture.create",
            resource_type="learnhub_lecture",
            resource_id=row["id"],
            before=None,
            after=_audit_view(row),
            reason=body.reason,
            meta=meta,
        )
    return LectureInfo(**row)


async def update_lecture(
    *, actor: AdminContext, meta: RequestMeta, lecture_id: str, body: LectureUpdate
) -> LectureInfo:
    patch = body.model_dump(exclude={"reason"}, exclude_unset=True)
    if not patch:
        raise HTTPException(422, "No fields to update")

    async with begin() as conn:
        current = await lectures_repo.get_lecture(conn, lecture_id)
        if not current:
            raise HTTPException(404, "Lecture not found")

        # Validate against the merged result, not the patch alone: switching a
        # lecture to "video" in one request and setting the URL in another must
        # not leave a video lecture with nothing to play.
        merged_type = patch.get("type", current["type"])
        merged_url = patch.get("video_url", current["video_url"])
        _require_video_url(merged_type, merged_url)

        new_slug = patch.get("slug")
        if new_slug and new_slug != current["slug"]:
            clash = await lectures_repo.get_by_slug(conn, new_slug)
            if clash:
                raise HTTPException(409, f"A lecture with slug '{new_slug}' already exists")

        row = await lectures_repo.update_lecture(
            conn, lecture_id=lecture_id, patch=patch, actor_id=actor.user_id
        )
        await write_audit(
            conn,
            actor=actor,
            action="admin.lecture.update",
            resource_type="learnhub_lecture",
            resource_id=lecture_id,
            before=_audit_view(current),
            after=_audit_view(row or {}),
            reason=body.reason,
            meta=meta,
        )
    return LectureInfo(**row)


async def delete_lecture(
    *, actor: AdminContext, meta: RequestMeta, lecture_id: str, reason: Optional[str]
) -> None:
    async with begin() as conn:
        current = await lectures_repo.get_lecture(conn, lecture_id)
        if not current:
            raise HTTPException(404, "Lecture not found")
        # The audit row is written first so the full `before` snapshot is
        # captured while the row still exists.
        await write_audit(
            conn,
            actor=actor,
            action="admin.lecture.delete",
            resource_type="learnhub_lecture",
            resource_id=lecture_id,
            before=_audit_view(current),
            after=None,
            reason=reason,
            meta=meta,
        )
        await lectures_repo.delete_lecture(conn, lecture_id)


def _require_video_url(lecture_type: Optional[str], video_url: Optional[str]) -> None:
    if lecture_type == "video" and not (video_url or "").strip():
        raise HTTPException(422, "A video lecture needs a video_url")
