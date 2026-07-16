"""AI reports data access: persist / fetch reports, concurrency-safe shared
get-or-create, period-aware usage counter, and retention pruning.

All writes run server-side with the service connection (bypasses RLS), so
user_id MUST always come from the verified JWT (require_user), never the client.

`content` is JSON-serialized before binding: asyncpg has no implicit dict->jsonb
codec, so we pass a JSON string and cast it with `::jsonb` in SQL.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

Executor = Any

# Retention: keep only the latest N confidential per-user reports per type (§9).
DEFAULT_RETENTION = 5

# Period -> date_trunc unit. Unknown periods fall back to the safest (widest)
# window so a misconfiguration never silently grants extra quota.
_PERIOD_UNITS = {"day": "day", "week": "week", "month": "month"}


async def insert_report(
    conn: Executor,
    *,
    user_id: Optional[str],
    report_type: str,
    subject: Optional[str],
    period_days: Optional[int],
    content: dict[str, Any],
    context_hash: str,
    lang: str = "en",
    verified: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    trading_date: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Insert a report row and return {id, created_at}."""
    result = await conn.execute(
        text(
            """
            INSERT INTO ai_reports
                (user_id, report_type, subject, period_days, trading_date,
                 content, context_hash, verified, provider, model, lang)
            VALUES
                (:uid, :report_type, :subject, :period_days, :trading_date,
                 CAST(:content AS jsonb), :context_hash, :verified, :provider, :model,
                 :lang)
            RETURNING id, created_at
            """
        ),
        {
            "uid": user_id,
            "lang": lang,
            "report_type": report_type,
            "subject": subject,
            "period_days": period_days,
            "trading_date": trading_date,
            "content": json.dumps(content),
            "context_hash": context_hash,
            "verified": verified,
            "provider": provider,
            "model": model,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_or_create_shared(
    conn: Executor,
    *,
    report_type: str,
    subject: Optional[str],
    trading_date: Optional[str],
    content: dict[str, Any],
    context_hash: str,
    lang: str = "en",
    verified: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Concurrency-safe shared-report get-or-create (§19.5).

    INSERT ... ON CONFLICT DO NOTHING against the partial unique index, then
    SELECT the winning row. Simultaneous requests for the same
    (report_type, subject, trading_date) dedupe to one generation.
    """
    await conn.execute(
        text(
            """
            INSERT INTO ai_reports
                (user_id, report_type, subject, trading_date,
                 content, context_hash, verified, provider, model, lang)
            VALUES
                (NULL, :report_type, :subject, :td,
                 CAST(:content AS jsonb), :context_hash, :verified, :provider, :model,
                 :lang)
            ON CONFLICT (report_type, subject, trading_date, lang)
                WHERE user_id IS NULL
            DO NOTHING
            """
        ),
        {
            "report_type": report_type,
            "subject": subject,
            "td": trading_date,
            "content": json.dumps(content),
            "context_hash": context_hash,
            "verified": verified,
            "provider": provider,
            "model": model,
            "lang": lang,
        },
    )
    result = await conn.execute(
        text(
            """
            SELECT id, user_id, report_type, subject, trading_date,
                   content, context_hash, verified, provider, model, created_at,
                   lang
            FROM ai_reports
            WHERE user_id IS NULL
              AND report_type = :report_type
              AND subject IS NOT DISTINCT FROM :subject
              AND trading_date IS NOT DISTINCT FROM :td
              AND lang = :lang
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"report_type": report_type, "subject": subject, "td": trading_date, "lang": lang},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_latest_report(
    conn: Executor,
    *,
    user_id: Optional[str],
    report_type: str,
    subject: Optional[str] = None,
    lang: str = "en",
) -> Optional[dict[str, Any]]:
    """Latest report for a (user_id, report_type, lang[, subject]).

    `lang` is part of the key, not a filter you may omit: the cached content is
    written in that language, so serving it to a reader who asked for another
    is a wrong answer, not a stale one.
    """
    result = await conn.execute(
        text(
            """
            SELECT id, user_id, report_type, subject, period_days, trading_date,
                   content, context_hash, verified, provider, model, created_at,
                   lang
            FROM ai_reports
            WHERE user_id IS NOT DISTINCT FROM :uid
              AND report_type = :report_type
              AND subject IS NOT DISTINCT FROM :subject
              AND lang = :lang
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"uid": user_id, "report_type": report_type, "subject": subject,
         "lang": lang},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_period_usage(conn: Executor, user_id: str, period: str) -> int:
    """Reports generated by a user in the current period (day/week/month)."""
    unit = _PERIOD_UNITS.get(period, "month")
    result = await conn.execute(
        text(
            """
            SELECT COALESCE(SUM(report_count), 0)::int AS used
            FROM ai_report_usage
            WHERE user_id = :uid
              AND usage_date >= date_trunc(:unit, (now() AT TIME ZONE 'utc'))::date
            """
        ),
        {"uid": user_id, "unit": unit},
    )
    val = result.scalar()
    return int(val) if val is not None else 0


async def increment_report_usage(conn: Executor, user_id: str) -> None:
    """Bump today's report counter for a user."""
    await conn.execute(
        text(
            """
            INSERT INTO ai_report_usage (user_id, usage_date, report_count)
            VALUES (:uid, (now() AT TIME ZONE 'utc')::date, 1)
            ON CONFLICT (user_id, usage_date) DO UPDATE SET
                report_count = ai_report_usage.report_count + 1,
                updated_at = now()
            """
        ),
        {"uid": user_id},
    )


async def prune_reports(
    conn: Executor,
    user_id: str,
    report_type: str,
    keep: int = DEFAULT_RETENTION,
) -> None:
    """Retention: keep only the latest N per (user_id, report_type).

    Scoped by `user_id = :uid`, so shared reports (user_id IS NULL) are never
    touched — they are cache-keyed by trading_date and exempt (§9).
    """
    await conn.execute(
        text(
            """
            DELETE FROM ai_reports
            WHERE user_id = :uid
              AND report_type = :report_type
              AND id NOT IN (
                  SELECT id FROM ai_reports
                  WHERE user_id = :uid
                    AND report_type = :report_type
                  ORDER BY created_at DESC, id DESC
                  LIMIT :keep
              )
            """
        ),
        {"uid": user_id, "report_type": report_type, "keep": keep},
    )
