"""LearnHub lecture management routes (thin)."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response

from app.schemas.admin import (
    LectureCreate,
    LectureDeleteRequest,
    LectureInfo,
    LectureUpdate,
)
from app.services.admin import lectures as lectures_service
from app.services.admin.authz import (
    AdminContext,
    RequestMeta,
    request_meta,
    require_permission,
)

router = APIRouter()


@router.get("/lectures", response_model=list[LectureInfo])
async def list_lectures(
    _: Annotated[AdminContext, Depends(require_permission("learn.read"))],
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    q: Optional[str] = Query(None, max_length=200),
) -> list[LectureInfo]:
    return await lectures_service.list_lectures(status=status, search=q)


@router.get("/lectures/{lecture_id}", response_model=LectureInfo)
async def get_lecture(
    lecture_id: str,
    _: Annotated[AdminContext, Depends(require_permission("learn.read"))],
) -> LectureInfo:
    return await lectures_service.get_lecture(lecture_id)


@router.post("/lectures", response_model=LectureInfo, status_code=201)
async def create_lecture(
    body: LectureCreate,
    ctx: Annotated[AdminContext, Depends(require_permission("learn.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> LectureInfo:
    return await lectures_service.create_lecture(actor=ctx, meta=meta, body=body)


@router.patch("/lectures/{lecture_id}", response_model=LectureInfo)
async def update_lecture(
    lecture_id: str,
    body: LectureUpdate,
    ctx: Annotated[AdminContext, Depends(require_permission("learn.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
) -> LectureInfo:
    return await lectures_service.update_lecture(
        actor=ctx, meta=meta, lecture_id=lecture_id, body=body
    )


@router.delete("/lectures/{lecture_id}", status_code=204)
async def delete_lecture(
    lecture_id: str,
    ctx: Annotated[AdminContext, Depends(require_permission("learn.write"))],
    meta: Annotated[RequestMeta, Depends(request_meta)],
    body: LectureDeleteRequest | None = None,
) -> Response:
    await lectures_service.delete_lecture(
        actor=ctx,
        meta=meta,
        lecture_id=lecture_id,
        reason=(body.reason if body else None),
    )
    return Response(status_code=204)
