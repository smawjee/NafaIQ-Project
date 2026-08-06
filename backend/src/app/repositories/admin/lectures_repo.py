"""LearnHub lecture data access.

`sections` and `quiz` are jsonb columns holding the same shapes the frontend
lesson renderer already understands, so a DB-backed lecture goes through the
identical components as the static catalogue.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

Executor = Any

# Selected explicitly rather than SELECT * so a future column cannot silently
# widen the API response.
_COLS = (
    "id, slug, title, subtitle, category, level, duration, emoji, accent, "
    "type, video_url, sections, quiz, status, sort_order, "
    "created_by, updated_by, created_at, updated_at"
)


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["id"] = str(d["id"])
    for k in ("created_by", "updated_by"):
        d[k] = str(d[k]) if d.get(k) else None
    return d


async def list_lectures(
    conn: Executor,
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict[str, Any]]:
    where = []
    params: dict[str, Any] = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if search:
        where.append("(title ILIKE :q OR slug ILIKE :q OR category ILIKE :q)")
        params["q"] = f"%{search}%"
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = (
        await conn.execute(
            text(
                f"SELECT {_COLS} FROM learnhub_lectures {clause} "
                "ORDER BY sort_order, created_at"
            ),
            params,
        )
    ).mappings().all()
    return [_row(r) for r in rows]


async def get_lecture(conn: Executor, lecture_id: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(f"SELECT {_COLS} FROM learnhub_lectures WHERE id = CAST(:id AS uuid)"),
            {"id": lecture_id},
        )
    ).mappings().first()
    return _row(row) if row else None


async def get_by_slug(conn: Executor, slug: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(f"SELECT {_COLS} FROM learnhub_lectures WHERE slug = :slug"),
            {"slug": slug},
        )
    ).mappings().first()
    return _row(row) if row else None


async def create_lecture(conn: Executor, *, data: dict[str, Any], actor_id: str) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                f"""
                INSERT INTO learnhub_lectures
                    (slug, title, subtitle, category, level, duration, emoji,
                     accent, type, video_url, sections, quiz, status, sort_order,
                     created_by, updated_by)
                VALUES
                    (:slug, :title, :subtitle, :category, :level, :duration, :emoji,
                     :accent, :type, :video_url,
                     CAST(:sections AS jsonb), CAST(:quiz AS jsonb),
                     :status, :sort_order,
                     CAST(:actor AS uuid), CAST(:actor AS uuid))
                RETURNING {_COLS}
                """
            ),
            {
                **data,
                "sections": json.dumps(data["sections"]),
                "quiz": json.dumps(data["quiz"]),
                "actor": actor_id,
            },
        )
    ).mappings().first()
    return _row(row)


async def update_lecture(
    conn: Executor, *, lecture_id: str, patch: dict[str, Any], actor_id: str
) -> Optional[dict[str, Any]]:
    """Partial update. Only the keys present in `patch` are written, so an edit
    of one field can never blank the rest."""
    if not patch:
        return await get_lecture(conn, lecture_id)

    sets = []
    params: dict[str, Any] = {"id": lecture_id, "actor": actor_id}
    for key, value in patch.items():
        if key in ("sections", "quiz"):
            sets.append(f"{key} = CAST(:{key} AS jsonb)")
            params[key] = json.dumps(value)
        else:
            sets.append(f"{key} = :{key}")
            params[key] = value
    sets.append("updated_by = CAST(:actor AS uuid)")
    sets.append("updated_at = now()")

    row = (
        await conn.execute(
            text(
                f"UPDATE learnhub_lectures SET {', '.join(sets)} "
                f"WHERE id = CAST(:id AS uuid) RETURNING {_COLS}"
            ),
            params,
        )
    ).mappings().first()
    return _row(row) if row else None


async def delete_lecture(conn: Executor, lecture_id: str) -> bool:
    result = await conn.execute(
        text("DELETE FROM learnhub_lectures WHERE id = CAST(:id AS uuid)"),
        {"id": lecture_id},
    )
    return (result.rowcount or 0) > 0
