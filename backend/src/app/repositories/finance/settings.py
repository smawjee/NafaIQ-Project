"""Finance user-settings data access (user_settings)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def get_settings_row(conn: Executor, uid: str) -> Optional[dict[str, Any]]:
    # `plan` comes from profiles, the single authoritative source the permission
    # layer gates on — NOT the local user_settings.plan copy. That copy is set to
    # 'Free' once at insert and never updated, so it drifted: two users showed
    # Premium in profiles but Free here (audit 2026-07-22 §3.3). Sourcing it from
    # profiles makes the finance-settings display incapable of disagreeing with
    # the user's actual plan.
    result = await conn.execute(
        text(
            """
            SELECT s.monthly_income, s.currency, s.language,
                   COALESCE(p.plan, 'Free') AS plan
            FROM user_settings s
            LEFT JOIN profiles p ON p.id = s.user_id
            WHERE s.user_id = :uid
            """
        ),
        {"uid": uid},
    )
    row = result.mappings().first()
    if not row:
        return None
    return {
        "monthly_income": float(row["monthly_income"]),
        "currency": row["currency"],
        "language": row["language"],
        "plan": row["plan"],
    }


async def upsert_settings(
    conn: Executor,
    uid: str,
    *,
    monthly_income: Optional[float],
    currency: Optional[str],
    language: Optional[str],
) -> None:
    sets = []
    params: dict[str, Any] = {
        "uid": uid,
        "income": monthly_income,
        "cur": currency,
        "lang": language,
        "plan": None,
    }
    if monthly_income is not None:
        sets.append("monthly_income = :income")
    if currency is not None:
        sets.append("currency = :cur")
    if language is not None:
        sets.append("language = :lang")
    if not sets:
        return
    sets.append("updated_at = now()")
    update_clause = ", ".join(sets)
    await conn.execute(
        text(
            "INSERT INTO user_settings (user_id, monthly_income, currency, language, plan) "
            "VALUES (:uid, COALESCE(:income, 0), COALESCE(:cur, 'PKR'), COALESCE(:lang, 'en'), COALESCE(:plan, 'Free')) "
            f"ON CONFLICT (user_id) DO UPDATE SET {update_clause}"
        ),
        params,
    )
