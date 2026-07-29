"""Zakat data access: settings CRUD and records. All zakat-domain SQL lives
here. These functions manage their own session/transaction because the record
save needs insert-then-update-on-conflict rollback control.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.repositories.base import session

_SETTINGS_COLS = (
    "user_id, method, custom_rate_pct, nisab_source, nisab_value_pkr, "
    "include_cash, include_investments, include_receivables, notes, updated_at"
)
_ALLOWED_SETTINGS = {
    "method",
    "custom_rate_pct",
    "nisab_source",
    "nisab_value_pkr",
    "include_cash",
    "include_investments",
    "include_receivables",
    "notes",
}


def _settings(r: Any) -> dict[str, Any]:
    return {
        "user_id": r["user_id"],
        "method": r["method"],
        "custom_rate_pct": float(r["custom_rate_pct"]) if r["custom_rate_pct"] is not None else None,
        "nisab_source": r["nisab_source"],
        "nisab_value_pkr": float(r["nisab_value_pkr"]) if r["nisab_value_pkr"] is not None else None,
        "include_cash": bool(r["include_cash"]),
        "include_investments": bool(r["include_investments"]),
        "include_receivables": bool(r["include_receivables"]),
        "notes": r["notes"],
        "updated_at": str(r["updated_at"]) if r["updated_at"] else None,
    }


async def get_or_create_settings(user_id: str) -> dict[str, Any]:
    async with session() as sess:
        row = await sess.execute(
            text(f"SELECT {_SETTINGS_COLS} FROM user_zakat_settings WHERE user_id = :uid"),
            {"uid": user_id},
        )
        r = row.mappings().first()
        if r:
            return _settings(r)
        await sess.execute(
            text("INSERT INTO user_zakat_settings (user_id) VALUES (:uid)"),
            {"uid": user_id},
        )
        await sess.commit()
        row = await sess.execute(
            text(f"SELECT {_SETTINGS_COLS} FROM user_zakat_settings WHERE user_id = :uid"),
            {"uid": user_id},
        )
        return _settings(row.mappings().first())


async def update_settings(user_id: str, updates: dict[str, Any]) -> None:
    sets: list[str] = []
    params: dict[str, Any] = {"uid": user_id}
    for k, v in updates.items():
        if k not in _ALLOWED_SETTINGS:
            continue
        sets.append(f"{k} = :{k}")
        params[k] = v
    if not sets:
        return
    sets.append("updated_at = now()")
    async with session() as sess:
        await sess.execute(
            text(
                "INSERT INTO user_zakat_settings (user_id) VALUES (:uid) "
                "ON CONFLICT (user_id) DO NOTHING"
            ),
            {"uid": user_id},
        )
        await sess.execute(
            text(f"UPDATE user_zakat_settings SET {', '.join(sets)} WHERE user_id = :uid"),
            params,
        )
        await sess.commit()


async def list_records(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    async with session() as sess:
        rows = await sess.execute(
            text(
                "SELECT id, user_id, islamic_year, method, nisab_value_pkr, "
                "total_assets_pkr, total_deductions_pkr, net_zakatable_pkr, "
                "rate_pct, zakat_due_pkr, breakdown, calculated_at, created_at "
                "FROM user_zakat_records WHERE user_id = :uid "
                "ORDER BY islamic_year DESC, calculated_at DESC LIMIT :lim"
            ),
            {"uid": user_id, "lim": max(1, min(limit, 200))},
        )
        out: list[dict[str, Any]] = []
        for r in rows.mappings().all():
            try:
                breakdown = json.loads(r["breakdown"]) if r["breakdown"] else {}
            except (TypeError, ValueError):
                breakdown = {}
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "islamic_year": r["islamic_year"],
                    "method": r["method"],
                    "nisab_value_pkr": float(r["nisab_value_pkr"]),
                    "total_assets_pkr": float(r["total_assets_pkr"]),
                    "total_deductions_pkr": float(r["total_deductions_pkr"]),
                    "net_zakatable_pkr": float(r["net_zakatable_pkr"]),
                    "rate_pct": float(r["rate_pct"]),
                    "zakat_due_pkr": float(r["zakat_due_pkr"]),
                    "breakdown": breakdown,
                    "calculated_at": str(r["calculated_at"]),
                    "created_at": str(r["created_at"]),
                }
            )
    return out


async def save_record(
    user_id: str,
    *,
    islamic_year: str,
    method: str,
    nisab_value_pkr: float,
    total_assets_pkr: float,
    total_deductions_pkr: float,
    net_zakatable: float,
    zakat_due: float,
    rate_pct: float,
    breakdown: dict[str, Any],
) -> dict[str, Any]:
    """Insert a record; on unique conflict (user/year/method) update in place."""
    params = {
        "uid": user_id,
        "yr": islamic_year,
        "m": method,
        "nisa": nisab_value_pkr,
        "ta": total_assets_pkr,
        "td": total_deductions_pkr,
        "nz": net_zakatable,
        "r": rate_pct,
        "zd": zakat_due,
        "br": json.dumps(breakdown or {}),
    }
    async with session() as sess:
        try:
            row = await sess.execute(
                text(
                    "INSERT INTO user_zakat_records "
                    "(user_id, islamic_year, method, nisab_value_pkr, "
                    " total_assets_pkr, total_deductions_pkr, net_zakatable_pkr, "
                    " rate_pct, zakat_due_pkr, breakdown) "
                    "VALUES (:uid, :yr, :m, :nisa, :ta, :td, :nz, :r, :zd, "
                    "        CAST(:br AS JSONB)) "
                    "RETURNING id, calculated_at"
                ),
                params,
            )
            r = row.mappings().first()
            await sess.commit()
        except IntegrityError:
            await sess.rollback()
            row = await sess.execute(
                text(
                    "UPDATE user_zakat_records SET "
                    "  nisab_value_pkr = :nisa, total_assets_pkr = :ta, "
                    "  total_deductions_pkr = :td, net_zakatable_pkr = :nz, "
                    "  rate_pct = :r, zakat_due_pkr = :zd, "
                    "  breakdown = CAST(:br AS JSONB), "
                    "  calculated_at = now() "
                    "WHERE user_id = :uid AND islamic_year = :yr AND method = :m "
                    "RETURNING id, calculated_at"
                ),
                params,
            )
            r = row.mappings().first()
            await sess.commit()
    return {"id": r["id"], "calculated_at": str(r["calculated_at"])}
