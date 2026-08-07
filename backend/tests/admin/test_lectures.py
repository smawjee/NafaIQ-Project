"""LearnHub lecture management: validation, slug collisions, and the guarantee
that every mutation writes an audit row in the same transaction.

DB-free — the transaction context and the repo are monkeypatched, the same way
tests/admin/test_admin_guards.py does it.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.schemas.admin import LectureCreate, LectureUpdate
from app.services.admin.authz import AdminContext, RequestMeta

META = RequestMeta(request_id="req-1", ip="127.0.0.1")
ACTOR = AdminContext(user_id="admin-1", email="a@example.com", roles=["content_admin"])


@asynccontextmanager
async def _fake_begin():
    yield object()  # sentinel connection; repos are patched so it is never used


def _row(**over):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "slug": "psx-basics",
        "title": "PSX Basics",
        "subtitle": "",
        "category": "PSX Basics",
        "level": "Beginner",
        "duration": "5 min",
        "emoji": "📘",
        "accent": "#00d4aa",
        "type": "article",
        "video_url": None,
        "sections": [],
        "quiz": [],
        "status": "published",
        "sort_order": 100,
        "created_by": None,
        "updated_by": None,
        "created_at": None,
        "updated_at": None,
    }
    base.update(over)
    return base


class _Audit:
    """Collects audit calls so a test can assert one was written."""

    def __init__(self):
        self.calls = []

    async def __call__(self, conn, **kw):
        self.calls.append(kw)
        return 1


# --- Schema validation ------------------------------------------------------
def test_slug_must_be_kebab_case():
    with pytest.raises(Exception):
        LectureCreate(slug="Not A Slug", title="x")


def test_level_must_be_known():
    with pytest.raises(Exception):
        LectureCreate(slug="ok", title="x", level="Expert")


def test_status_must_be_known():
    with pytest.raises(Exception):
        LectureCreate(slug="ok", title="x", status="live")


def test_accent_must_be_a_hex_colour():
    with pytest.raises(Exception):
        LectureCreate(slug="ok", title="x", accent="teal")


# --- Create -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_rejects_video_without_url(monkeypatch):
    from app.services.admin import lectures

    monkeypatch.setattr(lectures, "begin", _fake_begin)
    with pytest.raises(HTTPException) as ei:
        await lectures.create_lecture(
            actor=ACTOR,
            meta=META,
            body=LectureCreate(slug="v", title="V", type="video"),
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_duplicate_slug(monkeypatch):
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    monkeypatch.setattr(lectures, "begin", _fake_begin)

    async def _existing(conn, slug):
        return _row()

    monkeypatch.setattr(lectures_repo, "get_by_slug", _existing)

    with pytest.raises(HTTPException) as ei:
        await lectures.create_lecture(
            actor=ACTOR, meta=META, body=LectureCreate(slug="psx-basics", title="Dupe")
        )
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_create_writes_an_audit_row(monkeypatch):
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    audit = _Audit()
    monkeypatch.setattr(lectures, "begin", _fake_begin)
    monkeypatch.setattr(lectures, "write_audit", audit)

    async def _none(conn, slug):
        return None

    async def _create(conn, *, data, actor_id):
        return _row(**{k: v for k, v in data.items() if k in _row()})

    monkeypatch.setattr(lectures_repo, "get_by_slug", _none)
    monkeypatch.setattr(lectures_repo, "create_lecture", _create)

    out = await lectures.create_lecture(
        actor=ACTOR, meta=META, body=LectureCreate(slug="psx-basics", title="PSX Basics")
    )
    assert out.slug == "psx-basics"
    assert len(audit.calls) == 1
    assert audit.calls[0]["action"] == "admin.lecture.create"
    assert audit.calls[0]["resource_type"] == "learnhub_lecture"


# --- Update -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_validates_against_the_merged_row(monkeypatch):
    """Switching an article to a video without supplying a URL must fail even
    though the patch alone carries no video_url."""
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    monkeypatch.setattr(lectures, "begin", _fake_begin)

    async def _get(conn, lecture_id):
        return _row(type="article", video_url=None)

    monkeypatch.setattr(lectures_repo, "get_lecture", _get)

    with pytest.raises(HTTPException) as ei:
        await lectures.update_lecture(
            actor=ACTOR, meta=META, lecture_id="x", body=LectureUpdate(type="video")
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_update_rejects_slug_taken_by_another_lecture(monkeypatch):
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    monkeypatch.setattr(lectures, "begin", _fake_begin)

    async def _get(conn, lecture_id):
        return _row(slug="original")

    async def _by_slug(conn, slug):
        return _row(id="22222222-2222-2222-2222-222222222222", slug=slug)

    monkeypatch.setattr(lectures_repo, "get_lecture", _get)
    monkeypatch.setattr(lectures_repo, "get_by_slug", _by_slug)

    with pytest.raises(HTTPException) as ei:
        await lectures.update_lecture(
            actor=ACTOR, meta=META, lecture_id="x", body=LectureUpdate(slug="taken")
        )
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_update_only_writes_the_fields_it_was_given(monkeypatch):
    """A partial edit must not blank the rest of the lecture."""
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    seen: dict = {}
    monkeypatch.setattr(lectures, "begin", _fake_begin)
    monkeypatch.setattr(lectures, "write_audit", _Audit())

    async def _get(conn, lecture_id):
        return _row()

    async def _update(conn, *, lecture_id, patch, actor_id):
        seen.update(patch)
        return _row(**patch)

    monkeypatch.setattr(lectures_repo, "get_lecture", _get)
    monkeypatch.setattr(lectures_repo, "update_lecture", _update)

    await lectures.update_lecture(
        actor=ACTOR, meta=META, lecture_id="x", body=LectureUpdate(status="archived")
    )
    assert seen == {"status": "archived"}


@pytest.mark.asyncio
async def test_update_with_no_fields_is_rejected(monkeypatch):
    from app.services.admin import lectures

    monkeypatch.setattr(lectures, "begin", _fake_begin)
    with pytest.raises(HTTPException) as ei:
        await lectures.update_lecture(
            actor=ACTOR, meta=META, lecture_id="x", body=LectureUpdate()
        )
    assert ei.value.status_code == 422


# --- Delete -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_audits_before_removing_the_row(monkeypatch):
    """The audit `before` payload must capture the lecture while it still
    exists, so the log says what was deleted."""
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    order: list[str] = []
    audit = _Audit()

    async def _audit(conn, **kw):
        order.append("audit")
        return await audit(conn, **kw)

    monkeypatch.setattr(lectures, "begin", _fake_begin)
    monkeypatch.setattr(lectures, "write_audit", _audit)

    async def _get(conn, lecture_id):
        return _row(title="Doomed")

    async def _delete(conn, lecture_id):
        order.append("delete")
        return True

    monkeypatch.setattr(lectures_repo, "get_lecture", _get)
    monkeypatch.setattr(lectures_repo, "delete_lecture", _delete)

    await lectures.delete_lecture(actor=ACTOR, meta=META, lecture_id="x", reason="obsolete")

    assert order == ["audit", "delete"]
    assert audit.calls[0]["action"] == "admin.lecture.delete"
    assert audit.calls[0]["before"]["title"] == "Doomed"
    assert audit.calls[0]["reason"] == "obsolete"


@pytest.mark.asyncio
async def test_delete_missing_lecture_is_404(monkeypatch):
    from app.services.admin import lectures
    from app.repositories.admin import lectures_repo

    monkeypatch.setattr(lectures, "begin", _fake_begin)

    async def _none(conn, lecture_id):
        return None

    monkeypatch.setattr(lectures_repo, "get_lecture", _none)

    with pytest.raises(HTTPException) as ei:
        await lectures.delete_lecture(actor=ACTOR, meta=META, lecture_id="x", reason=None)
    assert ei.value.status_code == 404


# --- Route authorization ----------------------------------------------------
def test_every_lecture_route_is_permission_gated():
    """A lecture route without require_permission would be reachable by any
    admin, including read-only analysts."""
    from app.api.admin import lectures as lectures_api

    for route in lectures_api.router.routes:
        names = {
            getattr(d.call, "__qualname__", "") for d in route.dependant.dependencies
        }
        assert any("require_permission" in n for n in names), (
            f"{route.path} [{route.methods}] is not permission-gated"
        )


def test_write_routes_require_learn_write():
    """Read permission must not be enough to mutate the catalogue."""
    from app.api.admin import lectures as lectures_api

    write_methods = {"POST", "PATCH", "DELETE"}
    found = 0
    for route in lectures_api.router.routes:
        if not (route.methods & write_methods):
            continue
        found += 1
        # require_permission("slug") closes over its slug; read it back so the
        # test asserts the actual permission, not just that one was declared.
        closure = [
            c.cell_contents
            for d in route.dependant.dependencies
            for c in (getattr(d.call, "__closure__", None) or ())
        ]
        assert "learn.write" in closure, f"{route.path} does not require learn.write"
    assert found == 3, "expected create, update and delete routes"
