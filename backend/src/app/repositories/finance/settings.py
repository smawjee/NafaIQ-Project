"""Finance user-settings data access (user_settings)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any


async def get_settings_row(conn: Executor, uid: str) -> Optional[dict[str, Any]]:
    result = await conn.execute(
        text("SELECT monthly_income, currency, language, plan FROM user_settings WHERE user_id = :uid"),
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
