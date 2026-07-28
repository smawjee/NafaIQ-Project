"""Error capture + bug report data access.

Two shapes on purpose: errors are machine-captured and grouped (one row per
distinct failure, plus the individual occurrences), while bug reports are
human-authored and individual.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

Executor = Any


# ---------------------------------------------------------------------------
# Error capture
# ---------------------------------------------------------------------------


async def record_error(
    conn: Executor,
    *,
    fingerprint: str,
    source: str,
    message: str,
    route: Optional[str],
    stack: Optional[str],
    status_code: Optional[int],
    user_id: Optional[str],
    app_version: Optional[str],
    user_agent: Optional[str],
) -> None:
    """Upsert the group and append the occurrence.

    The group upsert also RE-OPENS a resolved group when the error recurs: a bug
    marked fixed that starts happening again is not fixed, and silently leaving
    it green is how error trackers lose trust.
    """
    await conn.execute(
        text(
            """
            INSERT INTO app_error_groups
                (fingerprint, source, message, route, sample_stack, event_count,
                 first_seen, last_seen)
            VALUES (:fp, :source, :message, :route, :stack, 1, now(), now())
            ON CONFLICT (fingerprint) DO UPDATE SET
                event_count = app_error_groups.event_count + 1,
                last_seen   = now(),
                -- A recurrence invalidates a previous resolution.
                status      = CASE WHEN app_error_groups.status = 'resolved'
                                   THEN 'open' ELSE app_error_groups.status END,
                resolved_at = CASE WHEN app_error_groups.status = 'resolved'
                                   THEN NULL ELSE app_error_groups.resolved_at END
            """
        ),
        {
            "fp": fingerprint,
            "source": source,
            "message": message,
            "route": route,
            "stack": stack,
        },
    )
    await conn.execute(
        text(
            """
            INSERT INTO app_error_events
                (fingerprint, user_id, source, message, route, stack,
                 status_code, app_version, user_agent)
            VALUES (:fp, CAST(:uid AS uuid), :source, :message, :route, :stack,
                    :code, :ver, :ua)
            """
        ),
        {
            "fp": fingerprint,
            "uid": user_id,
            "source": source,
            "message": message,
            "route": route,
            "stack": stack,
            "code": status_code,
            "ver": app_version,
            "ua": user_agent,
        },
    )


async def list_error_groups(
    conn: Executor,
    *,
    status: Optional[str],
    source: Optional[str],
    since: Optional[datetime],
    query: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Groups newest-activity-first, with the distinct users each has affected.

    `users_affected` is the number that decides what to fix first — an error
    hitting 40 people matters more than one firing 400 times for a single user
    stuck in a retry loop.
    """
    where = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        where.append("g.status = :status")
        params["status"] = status
    if source:
        where.append("g.source = :source")
        params["source"] = source
    if since:
        where.append("g.last_seen >= :since")
        params["since"] = since
    if query:
        where.append("(g.message ILIKE :q ESCAPE '\\' OR g.route ILIKE :q ESCAPE '\\')")
        esc = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{esc}%"
    clause = " AND ".join(where)

    total = (
        await conn.execute(
            text(f"SELECT count(*) FROM app_error_groups g WHERE {clause}"), params
        )
    ).scalar() or 0

    rows = (
        await conn.execute(
            text(
                f"""
                SELECT g.fingerprint, g.source, g.message, g.route, g.status,
                       g.event_count, g.first_seen, g.last_seen, g.admin_note,
                       g.resolved_at,
                       (SELECT count(DISTINCT e.user_id)
                          FROM app_error_events e
                         WHERE e.fingerprint = g.fingerprint
                           AND e.user_id IS NOT NULL) AS users_affected
                  FROM app_error_groups g
                 WHERE {clause}
                 ORDER BY g.last_seen DESC
                 LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


async def get_error_group(conn: Executor, fingerprint: str) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                SELECT fingerprint, source, message, route, sample_stack, status,
                       event_count, first_seen, last_seen, admin_note, resolved_at
                  FROM app_error_groups WHERE fingerprint = :fp
                """
            ),
            {"fp": fingerprint},
        )
    ).mappings().first()
    return dict(row) if row else None


async def list_error_events(
    conn: Executor, *, fingerprint: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Recent occurrences, with the affected user's email where there is one."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT e.id, e.user_id, u.email AS user_email, e.route, e.stack,
                       e.status_code, e.app_version, e.user_agent, e.created_at
                  FROM app_error_events e
             LEFT JOIN auth.users u ON u.id = e.user_id
                 WHERE e.fingerprint = :fp
                 ORDER BY e.created_at DESC
                 LIMIT :limit
                """
            ),
            {"fp": fingerprint, "limit": limit},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def set_error_status(
    conn: Executor,
    *,
    fingerprint: str,
    status: str,
    admin_note: Optional[str],
    resolved_by: Optional[str],
) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                UPDATE app_error_groups
                   SET status = :status,
                       admin_note = COALESCE(:note, admin_note),
                       resolved_at = CASE WHEN :status = 'resolved' THEN now() ELSE NULL END,
                       resolved_by = CASE WHEN :status = 'resolved'
                                          THEN CAST(:by AS uuid) ELSE NULL END
                 WHERE fingerprint = :fp
             RETURNING fingerprint, status, admin_note, resolved_at
                """
            ),
            {"fp": fingerprint, "status": status, "note": admin_note, "by": resolved_by},
        )
    ).mappings().first()
    return dict(row) if row else None


async def error_summary(conn: Executor) -> dict[str, Any]:
    """Headline counters for the admin overview."""
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    count(*) FILTER (WHERE status = 'open')                    AS open_groups,
                    count(*) FILTER (WHERE last_seen >= now() - interval '24 hours')
                                                                               AS active_24h,
                    COALESCE(sum(event_count) FILTER
                        (WHERE last_seen >= now() - interval '24 hours'), 0)   AS events_24h
                  FROM app_error_groups
                """
            )
        )
    ).mappings().first()
    return {k: int(v or 0) for k, v in dict(row).items()}


async def purge_old_events(conn: Executor, *, days: int) -> int:
    """Delete events past the retention window. Groups keep their counters."""
    result = await conn.execute(
        text("DELETE FROM app_error_events WHERE created_at < now() - make_interval(days => :d)"),
        {"d": days},
    )
    return result.rowcount or 0


async def recent_events_for_user(conn: Executor, *, user_id: str, limit: int = 10) -> list[dict]:
    """Errors this specific user hit — answers 'what did they actually see?'
    from their profile page."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT e.id, e.fingerprint, e.message, e.route, e.source,
                       e.status_code, e.created_at, g.status
                  FROM app_error_events e
             LEFT JOIN app_error_groups g ON g.fingerprint = e.fingerprint
                 WHERE e.user_id = CAST(:uid AS uuid)
                 ORDER BY e.created_at DESC
                 LIMIT :limit
                """
            ),
            {"uid": user_id, "limit": limit},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Bug reports
# ---------------------------------------------------------------------------


async def create_bug_report(
    conn: Executor,
    *,
    user_id: str,
    title: str,
    description: str,
    category: str,
    route: Optional[str],
    app_version: Optional[str],
    user_agent: Optional[str],
    error_fingerprint: Optional[str],
) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                INSERT INTO bug_reports
                    (user_id, title, description, category, route, app_version,
                     user_agent, error_fingerprint)
                VALUES (CAST(:uid AS uuid), :title, :description, :category, :route,
                        :ver, :ua, :fp)
             RETURNING id, title, description, category, status, route, created_at
                """
            ),
            {
                "uid": user_id,
                "title": title,
                "description": description,
                "category": category,
                "route": route,
                "ver": app_version,
                "ua": user_agent,
                "fp": error_fingerprint,
            },
        )
    ).mappings().first()
    return dict(row)


async def list_own_bug_reports(conn: Executor, *, user_id: str) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT id, title, description, category, status, admin_note,
                       created_at, resolved_at
                  FROM bug_reports
                 WHERE user_id = CAST(:uid AS uuid)
                 ORDER BY created_at DESC
                """
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def list_bug_reports(
    conn: Executor,
    *,
    status: Optional[str],
    category: Optional[str],
    query: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    where = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        where.append("b.status = :status")
        params["status"] = status
    if category:
        where.append("b.category = :category")
        params["category"] = category
    if query:
        where.append("(b.title ILIKE :q ESCAPE '\\' OR b.description ILIKE :q ESCAPE '\\')")
        esc = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{esc}%"
    clause = " AND ".join(where)

    total = (
        await conn.execute(text(f"SELECT count(*) FROM bug_reports b WHERE {clause}"), params)
    ).scalar() or 0

    rows = (
        await conn.execute(
            text(
                f"""
                SELECT b.id, b.user_id, u.email AS user_email, b.title, b.description,
                       b.category, b.route, b.app_version, b.user_agent, b.status,
                       b.admin_note, b.error_fingerprint, b.created_at, b.resolved_at
                  FROM bug_reports b
             LEFT JOIN auth.users u ON u.id = b.user_id
                 WHERE {clause}
                 ORDER BY b.created_at DESC
                 LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


async def set_bug_report_status(
    conn: Executor,
    *,
    report_id: int,
    status: str,
    admin_note: Optional[str],
    resolved_by: Optional[str],
) -> Optional[dict[str, Any]]:
    row = (
        await conn.execute(
            text(
                """
                UPDATE bug_reports
                   SET status = :status,
                       admin_note = COALESCE(:note, admin_note),
                       updated_at = now(),
                       resolved_at = CASE WHEN :status IN ('resolved', 'wont_fix')
                                          THEN now() ELSE NULL END,
                       resolved_by = CASE WHEN :status IN ('resolved', 'wont_fix')
                                          THEN CAST(:by AS uuid) ELSE NULL END
                 WHERE id = :id
             RETURNING id, status, admin_note, resolved_at
                """
            ),
            {"id": report_id, "status": status, "note": admin_note, "by": resolved_by},
        )
    ).mappings().first()
    return dict(row) if row else None


async def bug_report_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE status = 'open')          AS open_reports,
                       count(*) FILTER (WHERE status = 'investigating') AS investigating,
                       count(*) FILTER (WHERE created_at >= now() - interval '7 days')
                                                                        AS new_7d,
                       count(*)                                         AS total
                  FROM bug_reports
                """
            )
        )
    ).mappings().first()
    return {k: int(v or 0) for k, v in dict(row).items()}
