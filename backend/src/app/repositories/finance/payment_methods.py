"""User payment-method data access."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.repositories.finance._common import table

Executor = Any


def _payment_method(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "created_at": str(row["created_at"]),
    }


async def list_payment_methods(conn: Executor, uid: str) -> list[dict[str, Any]]:
    methods = await table("user_payment_methods")
    result = await conn.execute(
        select(methods)
        .where(methods.c.user_id == uid)
        .order_by(methods.c.created_at.asc(), methods.c.label.asc())
    )
    return [_payment_method(r) for r in result.mappings().all()]


async def upsert_payment_method(conn: Executor, uid: str, label: str) -> dict[str, Any]:
    methods = await table("user_payment_methods")
    result = await conn.execute(
        pg_insert(methods)
        .values(user_id=uid, label=label)
        .on_conflict_do_update(
            constraint="user_payment_methods_user_label_unique",
            set_={"label": label},
        )
        .returning(methods)
    )
    return _payment_method(result.mappings().first())
