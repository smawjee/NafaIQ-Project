"""Finance bills: business logic over finance_repo (incl. recurring roll-over)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import finance_repo as repo
from app.repositories.base import begin, connect
from app.schemas.finance import BillCreate, BillUpdate
from app.services.finance._common import as_date
from app.services.permissions import check_count_limit


async def list_bills(uid: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_bills(conn, uid)


async def create_bill(uid: str, body: BillCreate, user: dict) -> dict[str, Any]:
    async with begin() as conn:
        current = await repo.count_bills(conn, uid)
        check_count_limit(user, feature_key="max_bills", current=current, label="Bills")
        return await repo.insert_bill(
            conn,
            {
                "user_id": uid,
                "name": body.name.strip(),
                "amount": body.amount,
                "due_date": as_date(body.due_date),
                "status": body.status,
                "recurring": body.recurring,
            },
        )


async def update_bill(uid: str, bill_id: int, body: BillUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if "due_date" in values:
        values["due_date"] = as_date(values["due_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    async with begin() as conn:
        row = await repo.update_bill(conn, uid, bill_id, values)
    if not row:
        raise HTTPException(404, "Bill not found")
    return row


async def mark_bill_paid(uid: str, bill_id: int) -> dict[str, Any]:
    async with begin() as conn:
        row = await repo.mark_bill_paid(conn, uid, bill_id)
    if not row:
        raise HTTPException(404, "Bill not found")
    return row


async def delete_bill(uid: str, bill_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_bill(conn, uid, bill_id)
    if deleted is None:
        raise HTTPException(404, "Bill not found")
    return {"deleted": bill_id}
